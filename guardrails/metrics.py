"""
MMM and Incrementality metric validators using Pydantic.

These schemas enforce business constraints on media mix modeling data,
catching hallucinations like:
- Budget allocated > total annual spend
- Reach > addressable universe
- Incremental lift > total conversions
- Negative spend or impressions
- Multi-year cohort misalignment
"""

from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import datetime


class MediaMixMetrics(BaseModel):
    """Core MMM metrics with budget and spend constraints."""

    year: int
    channel: str
    spend: float
    impressions: int
    annual_budget: float
    cpm: Optional[float] = None

    @field_validator('spend')
    @classmethod
    def spend_non_negative(cls, v):
        if v < 0:
            raise ValueError(f"Spend cannot be negative. Got: {v}")
        return v

    @field_validator('impressions')
    @classmethod
    def impressions_non_negative(cls, v):
        if v < 0:
            raise ValueError(f"Impressions cannot be negative. Got: {v}")
        return v

    @field_validator('annual_budget')
    @classmethod
    def budget_non_negative(cls, v):
        if v < 0:
            raise ValueError(f"Annual budget cannot be negative. Got: {v}")
        return v

    @model_validator(mode='after')
    def check_budget_and_cpm(self):
        if self.spend > self.annual_budget:
            raise ValueError(
                f"Spend ({self.spend}) exceeds annual budget ({self.annual_budget})"
            )

        if self.cpm is None and self.impressions > 0 and self.spend > 0:
            self.cpm = (self.spend / self.impressions) * 1000

        return self


class ReachAndFrequency(BaseModel):
    """Reach and frequency constraints for media channels."""

    channel: str
    reach: int
    frequency: float
    addressable_universe: int
    impressions: int

    @field_validator('reach')
    @classmethod
    def reach_non_negative(cls, v):
        if v < 0:
            raise ValueError(f"Reach cannot be negative. Got: {v}")
        return v

    @field_validator('frequency')
    @classmethod
    def frequency_min_one(cls, v):
        if v < 1:
            raise ValueError(f"Frequency must be >= 1. Got: {v}")
        return v

    @field_validator('addressable_universe', 'impressions')
    @classmethod
    def non_negative(cls, v):
        if v < 0:
            raise ValueError(f"Value cannot be negative. Got: {v}")
        return v

    @model_validator(mode='after')
    def check_reach_and_impressions(self):
        if self.reach > self.addressable_universe:
            raise ValueError(
                f"Reach ({self.reach}) exceeds addressable universe "
                f"({self.addressable_universe})"
            )

        expected_impressions = self.reach * self.frequency
        tolerance = expected_impressions * 0.05
        if abs(self.impressions - expected_impressions) > tolerance:
            raise ValueError(
                f"Impressions ({self.impressions}) inconsistent with "
                f"reach*frequency ({expected_impressions}). "
                f"Likely bucketization error or hallucination."
            )

        return self


class ChannelAttribution(BaseModel):
    """Channel attribution weights and contribution metrics."""

    channel: str
    attribution_weight: float
    attributed_revenue: float
    total_revenue: float

    @field_validator('attributed_revenue')
    @classmethod
    def attributed_non_negative(cls, v):
        if v < 0:
            raise ValueError(f"Attributed revenue cannot be negative. Got: {v}")
        return v

    @field_validator('total_revenue')
    @classmethod
    def total_non_negative(cls, v):
        if v < 0:
            raise ValueError(f"Total revenue cannot be negative. Got: {v}")
        return v

    @model_validator(mode='after')
    def check_weight_and_revenue(self):
        if not (0 <= self.attribution_weight <= 1):
            raise ValueError(
                f"Attribution weight out of bounds: must be 0-1. "
                f"Got: {self.attribution_weight}"
            )

        if self.attributed_revenue > self.total_revenue:
            raise ValueError(
                f"Attributed revenue ({self.attributed_revenue}) exceeds "
                f"total revenue ({self.total_revenue}). "
                f"Channel contribution likely hallucinated."
            )

        return self


class IncrementalityMetrics(BaseModel):
    """Incrementality and lift validation for campaigns."""

    campaign_id: str
    spend: float
    total_conversions: int
    incremental_conversions: int
    incremental_revenue: float
    test_group_size: int
    control_group_size: int

    @field_validator(
        'spend',
        'incremental_revenue',
        'total_conversions',
        'incremental_conversions',
        'test_group_size',
        'control_group_size',
    )
    @classmethod
    def non_negative(cls, v):
        if v < 0:
            raise ValueError(f"Value cannot be negative. Got: {v}")
        return v

    @model_validator(mode='after')
    def check_lift_and_sample_sizes(self):
        if self.incremental_conversions > self.total_conversions:
            raise ValueError(
                f"Incremental conversions ({self.incremental_conversions}) "
                f"exceed total conversions ({self.total_conversions}). "
                f"Impossible result - likely LLM hallucination."
            )

        if self.incremental_revenue > (self.spend * 10):
            raise ValueError(
                f"Incremental revenue ({self.incremental_revenue}) seems inflated "
                f"vs spend ({self.spend}). ROAS > 10x - hallucination likely."
            )

        if self.test_group_size < 100:
            raise ValueError(
                f"Test group size ({self.test_group_size}) too small for "
                f"statistical validity. Minimum 100 recommended."
            )

        if self.control_group_size < 100:
            raise ValueError(
                f"Control group size ({self.control_group_size}) too small for "
                f"statistical validity. Minimum 100 recommended."
            )

        return self


class MultiYearMMM(BaseModel):
    """Multi-year MMM cohort validation."""

    cohort_year: int
    channel: str
    spend_2022: float
    spend_2023: float
    spend_2024: float
    conversions_2022: int
    conversions_2023: int
    conversions_2024: int

    @field_validator('spend_2022', 'spend_2023', 'spend_2024')
    @classmethod
    def spend_non_negative(cls, v):
        if v < 0:
            raise ValueError(f"Spend cannot be negative. Got: {v}")
        return v

    @field_validator('conversions_2022', 'conversions_2023', 'conversions_2024')
    @classmethod
    def conversions_non_negative(cls, v):
        if v < 0:
            raise ValueError(f"Conversions cannot be negative. Got: {v}")
        return v

    @model_validator(mode='after')
    def check_yoy_growth_and_bucketing(self):
        if self.conversions_2022 > 0 and self.spend_2022 > 0:
            conv_growth = (
                self.conversions_2023 - self.conversions_2022
            ) / self.conversions_2022
            spend_growth = (self.spend_2023 - self.spend_2022) / self.spend_2022

            if conv_growth >= 3.0 and spend_growth < 0.5:
                raise ValueError(
                    f"2023 conversions ({self.conversions_2023}) show "
                    f"{conv_growth * 100:.0f}% growth but spend only grew "
                    f"{spend_growth * 100:.0f}%. "
                    f"Multi-year bucketization error or hallucination."
                )

        if self.conversions_2023 > 100 and self.conversions_2024 == 0:
            raise ValueError(
                f"2024 conversions are 0 but 2023 had {self.conversions_2023}. "
                f"Possible data bucketing error - 2024 data may be in wrong year."
            )

        return self


class MMMAuditTrail(BaseModel):
    """Audit trail for MMM validation results."""

    timestamp: datetime
    metric_type: str
    record_id: str
    passed: bool
    error_message: Optional[str] = None
    data_snapshot: dict
