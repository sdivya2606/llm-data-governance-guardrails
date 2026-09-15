"""
Comprehensive test suite for MMM guardrails.

Tests demonstrate the framework catching real hallucination patterns:
- Budget math violations
- Multi-year bucketization errors
- Reach/frequency impossibilities
- Attribution logic violations
- Incrementality hallucinations
"""

import pytest
from datetime import datetime
from guardrails.schema_validator import DataContractValidator, SchemaRegistry
from guardrails.exceptions import (
    DataContractViolation,
    HalluccinationDetected,
    SchemaNotFound,
)


class TestMediaMixMetrics:
    """Test core MMM budget and spend validation."""
    
    def test_valid_media_mix_record(self):
        """Valid media mix record should pass."""
        validator = DataContractValidator()
        data = {
            'year': 2024,
            'channel': 'paid_search',
            'spend': 50000,
            'impressions': 1000000,
            'annual_budget': 100000,
        }
        result = validator.validate(data, 'media_mix', 'test_1')
        assert result.passed
        assert result.errors == []
    
    def test_negative_spend_hallucination(self):
        """LLM hallucination: negative spend."""
        validator = DataContractValidator()
        data = {
            'year': 2024,
            'channel': 'paid_search',
            'spend': -50000,  # Impossible
            'impressions': 1000000,
            'annual_budget': 100000,
        }
        result = validator.validate(data, 'media_mix', 'test_negative_spend')
        assert not result.passed
        assert any('negative' in err.lower() for err in result.errors)
    
    def test_spend_exceeds_budget_hallucination(self):
        """LLM hallucination: spend > annual budget."""
        validator = DataContractValidator()
        data = {
            'year': 2024,
            'channel': 'paid_search',
            'spend': 150000,  # Exceeds budget
            'impressions': 1000000,
            'annual_budget': 100000,
        }
        result = validator.validate(data, 'media_mix', 'test_budget_exceed')
        assert not result.passed
        assert any('budget' in err.lower() for err in result.errors)
    
    def test_negative_impressions_hallucination(self):
        """LLM hallucination: negative impressions."""
        validator = DataContractValidator()
        data = {
            'year': 2024,
            'channel': 'display',
            'spend': 25000,
            'impressions': -500000,  # Impossible
            'annual_budget': 100000,
        }
        result = validator.validate(data, 'media_mix', 'test_neg_impr')
        assert not result.passed
        assert any('negative' in err.lower() for err in result.errors)
    
    def test_cpm_auto_calculation(self):
        """CPM should be auto-calculated if not provided."""
        validator = DataContractValidator()
        data = {
            'year': 2024,
            'channel': 'video',
            'spend': 10000,
            'impressions': 1000000,
            'annual_budget': 100000,
            'cpm': None,
        }
        result = validator.validate(data, 'media_mix', 'test_cpm')
        assert result.passed


class TestReachAndFrequency:
    """Test reach, frequency, and universe constraints."""
    
    def test_valid_reach_frequency(self):
        """Valid reach and frequency should pass."""
        validator = DataContractValidator()
        data = {
            'channel': 'social',
            'reach': 100000,
            'frequency': 2.5,
            'addressable_universe': 500000,
            'impressions': 250000,
        }
        result = validator.validate(data, 'reach_frequency', 'test_valid')
        assert result.passed
    
    def test_reach_exceeds_universe_hallucination(self):
        """LLM hallucination: reach > addressable universe."""
        validator = DataContractValidator()
        data = {
            'channel': 'display',
            'reach': 600000,  # Exceeds universe
            'frequency': 1.5,
            'addressable_universe': 500000,
            'impressions': 900000,
        }
        result = validator.validate(data, 'reach_frequency', 'test_reach_exceed')
        assert not result.passed
        assert any('reach' in err.lower() and 'universe' in err.lower() 
                   for err in result.errors)
    
    def test_frequency_less_than_one_hallucination(self):
        """LLM hallucination: frequency < 1 (impossible)."""
        validator = DataContractValidator()
        data = {
            'channel': 'email',
            'reach': 50000,
            'frequency': 0.5,  # Impossible: must reach at least once
            'addressable_universe': 100000,
            'impressions': 25000,
        }
        result = validator.validate(data, 'reach_frequency', 'test_freq_low')
        assert not result.passed
        assert any('frequency' in err.lower() for err in result.errors)
    
    def test_impressions_inconsistent_with_reach_frequency(self):
        """LLM hallucination: impressions don't match reach * frequency."""
        validator = DataContractValidator()
        data = {
            'channel': 'tv',
            'reach': 100000,
            'frequency': 3.0,
            'addressable_universe': 500000,
            'impressions': 50000,  # Should be ~300k, clearly wrong
        }
        result = validator.validate(data, 'reach_frequency', 'test_impr_mismatch')
        assert not result.passed
        assert any('inconsistent' in err.lower() for err in result.errors)


class TestChannelAttribution:
    """Test attribution weight and revenue constraints."""
    
    def test_valid_attribution(self):
        """Valid attribution should pass."""
        validator = DataContractValidator()
        data = {
            'channel': 'paid_search',
            'attribution_weight': 0.35,
            'attributed_revenue': 350000,
            'total_revenue': 1000000,
        }
        result = validator.validate(data, 'channel_attribution', 'test_valid_attr')
        assert result.passed
    
    def test_attribution_weight_exceeds_100_hallucination(self):
        """LLM hallucination: attribution weight > 100%."""
        validator = DataContractValidator()
        data = {
            'channel': 'display',
            'attribution_weight': 1.25,  # Impossible: > 100%
            'attributed_revenue': 1250000,
            'total_revenue': 1000000,
        }
        result = validator.validate(data, 'channel_attribution', 'test_weight_exceed')
        assert not result.passed
        assert any('weight' in err.lower() and 'bounds' in err.lower() 
                   for err in result.errors)
    
    def test_attributed_revenue_exceeds_total_hallucination(self):
        """LLM hallucination: attributed revenue > total revenue."""
        validator = DataContractValidator()
        data = {
            'channel': 'social',
            'attribution_weight': 1.2,  # Signals hallucination
            'attributed_revenue': 1500000,  # Exceeds total
            'total_revenue': 1000000,
        }
        result = validator.validate(data, 'channel_attribution', 'test_attr_exceed')
        assert not result.passed


class TestIncrementalityMetrics:
    """Test incrementality and lift validation."""
    
    def test_valid_incrementality(self):
        """Valid incrementality test should pass."""
        validator = DataContractValidator()
        data = {
            'campaign_id': 'camp_001',
            'spend': 100000,
            'total_conversions': 5000,
            'incremental_conversions': 1000,
            'incremental_revenue': 250000,
            'test_group_size': 50000,
            'control_group_size': 50000,
        }
        result = validator.validate(data, 'incrementality', 'test_valid_lift')
        assert result.passed
    
    def test_incremental_conversions_exceed_total_hallucination(self):
        """LLM hallucination: incremental lift > total conversions (impossible)."""
        validator = DataContractValidator()
        data = {
            'campaign_id': 'camp_002',
            'spend': 100000,
            'total_conversions': 5000,
            'incremental_conversions': 6000,  # Exceeds total: impossible
            'incremental_revenue': 300000,
            'test_group_size': 50000,
            'control_group_size': 50000,
        }
        result = validator.validate(data, 'incrementality', 'test_lift_exceed')
        assert not result.passed
        assert any('incremental' in err.lower() and 'exceed' in err.lower() 
                   for err in result.errors)
    
    def test_incremental_revenue_inflated_hallucination(self):
        """LLM hallucination: incremental revenue unreasonably high vs spend."""
        validator = DataContractValidator()
        data = {
            'campaign_id': 'camp_003',
            'spend': 100000,
            'total_conversions': 5000,
            'incremental_conversions': 1000,
            'incremental_revenue': 2000000,  # ROAS 20x: unrealistic
            'test_group_size': 50000,
            'control_group_size': 50000,
        }
        result = validator.validate(data, 'incrementality', 'test_rev_inflated')
        assert not result.passed
        assert any('inflated' in err.lower() or 'ROAS' in err.upper() 
                   for err in result.errors)
    
    def test_test_group_too_small(self):
        """LLM hallucination: test group size too small for statistical validity."""
        validator = DataContractValidator()
        data = {
            'campaign_id': 'camp_004',
            'spend': 50000,
            'total_conversions': 500,
            'incremental_conversions': 50,
            'incremental_revenue': 50000,
            'test_group_size': 50,  # Too small
            'control_group_size': 50,
        }
        result = validator.validate(data, 'incrementality', 'test_small_group')
        assert not result.passed
        assert any('test group' in err.lower() or 'small' in err.lower() 
                   for err in result.errors)


class TestMultiYearMMM:
    """Test multi-year MMM cohort bucketization and consistency."""
    
    def test_valid_multiyear_data(self):
        """Valid multi-year data should pass."""
        validator = DataContractValidator()
        data = {
            'cohort_year': 2024,
            'channel': 'paid_search',
            'spend_2022': 100000,
            'spend_2023': 110000,
            'spend_2024': 120000,
            'conversions_2022': 10000,
            'conversions_2023': 11000,
            'conversions_2024': 12000,
        }
        result = validator.validate(data, 'multi_year_mmm', 'test_valid_my')
        assert result.passed
    
    def test_negative_spend_multiyear(self):
        """LLM hallucination: negative spend in multi-year data."""
        validator = DataContractValidator()
        data = {
            'cohort_year': 2024,
            'channel': 'display',
            'spend_2022': -100000,  # Impossible
            'spend_2023': 110000,
            'spend_2024': 120000,
            'conversions_2022': 10000,
            'conversions_2023': 11000,
            'conversions_2024': 12000,
        }
        result = validator.validate(data, 'multi_year_mmm', 'test_neg_spend_my')
        assert not result.passed
    
    def test_yoy_conversion_growth_exceeds_spend_growth(self):
        """
        LLM hallucination: 2023 conversion growth 300% but spend only 5%.
        
        This is the classic multi-year MMM hallucination:
        "conversions grew massively but spend didn't"
        """
        validator = DataContractValidator()
        data = {
            'cohort_year': 2023,
            'channel': 'social',
            'spend_2022': 100000,
            'spend_2023': 105000,  # Only 5% growth
            'spend_2024': 110000,
            'conversions_2022': 1000,
            'conversions_2023': 4000,  # 300% growth: impossible without spend increase
            'conversions_2024': 4500,
        }
        result = validator.validate(data, 'multi_year_mmm', 'test_growth_mismatch')
        assert not result.passed
        assert any('growth' in err.lower() or 'bucketization' in err.lower() 
                   for err in result.errors)
    
    def test_2024_data_bucketed_into_2022(self):
        """
        LLM hallucination: 2024 data accidentally put into 2022 bucket.
        
        Signature: 2023 has conversions, but 2024 shows 0.
        """
        validator = DataContractValidator()
        data = {
            'cohort_year': 2022,
            'channel': 'paid_search',
            'spend_2022': 100000,
            'spend_2023': 110000,
            'spend_2024': 0,  # No spend in 2024: looks like bucketing error
            'conversions_2022': 10000,
            'conversions_2023': 11000,
            'conversions_2024': 0,  # Zero after data existed: hallucination
        }
        result = validator.validate(data, 'multi_year_mmm', 'test_bucketing_error')
        assert not result.passed
        assert any('bucketing' in err.lower() for err in result.errors)


class TestBatchValidation:
    """Test batch validation and reporting."""
    
    def test_batch_all_valid(self):
        """Batch with all valid records should show 100% pass rate."""
        validator = DataContractValidator()
        batch_data = [
            {
                'year': 2024,
                'channel': 'paid_search',
                'spend': 50000,
                'impressions': 1000000,
                'annual_budget': 100000,
            },
            {
                'year': 2024,
                'channel': 'display',
                'spend': 30000,
                'impressions': 500000,
                'annual_budget': 100000,
            },
        ]
        report = validator.validate_batch(batch_data, 'media_mix')
        assert report.passed_count == 2
        assert report.failed_count == 0
        assert report.failure_rate == 0.0
    
    def test_batch_mixed_valid_invalid(self):
        """Batch with mixed results should report correctly."""
        validator = DataContractValidator()
        batch_data = [
            {
                'year': 2024,
                'channel': 'paid_search',
                'spend': 50000,
                'impressions': 1000000,
                'annual_budget': 100000,
            },
            {
                'year': 2024,
                'channel': 'display',
                'spend': 150000,  # Exceeds budget
                'impressions': 500000,
                'annual_budget': 100000,
            },
        ]
        report = validator.validate_batch(batch_data, 'media_mix')
        assert report.passed_count == 1
        assert report.failed_count == 1
        assert report.failure_rate == 0.5
        assert len(report.failures) == 1


class TestAuditTrail:
    """Test audit trail logging."""
    
    def test_audit_trail_logs_validation(self):
        """Audit trail should log all validation attempts."""
        validator = DataContractValidator()
        data = {
            'year': 2024,
            'channel': 'paid_search',
            'spend': 50000,
            'impressions': 1000000,
            'annual_budget': 100000,
        }
        validator.validate(data, 'media_mix', 'audit_test_1')
        
        trail = validator.get_audit_trail()
        assert len(trail) == 1
        assert trail[0]['record_id'] == 'audit_test_1'
        assert trail[0]['passed'] is True
    
    def test_audit_trail_includes_failures(self):
        """Audit trail should log failed validations."""
        validator = DataContractValidator()
        data = {
            'year': 2024,
            'channel': 'paid_search',
            'spend': 150000,
            'impressions': 1000000,
            'annual_budget': 100000,
        }
        validator.validate(data, 'media_mix', 'audit_test_fail')
        
        trail = validator.get_audit_trail()
        assert len(trail) == 1
        assert trail[0]['passed'] is False
        assert trail[0]['error_message'] is not None


class TestSchemaRegistry:
    """Test schema registration and lookup."""
    
    def test_default_schemas_registered(self):
        """All default schemas should be in registry."""
        schemas = SchemaRegistry.list_schemas()
        assert 'media_mix' in schemas
        assert 'reach_frequency' in schemas
        assert 'incrementality' in schemas
        assert 'multi_year_mmm' in schemas
    
    def test_schema_not_found_error(self):
        """Requesting non-existent schema should raise error."""
        validator = DataContractValidator()
        data = {'test': 'data'}
        with pytest.raises(SchemaNotFound):
            validator.validate(data, 'nonexistent_schema')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
