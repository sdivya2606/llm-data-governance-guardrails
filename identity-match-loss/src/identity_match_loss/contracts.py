"""Pydantic data contracts for synthetic Acxiom-style and Epsilon-style files.

A record that breaks a rule is flagged and returned with its errors,
not passed downstream.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from pydantic import BaseModel, field_validator, model_validator

AX_ID = re.compile(r"^AX\d{7}$")
EP_ID = re.compile(r"^CID\d{7}$")


class AcxiomStyleRecord(BaseModel):
    acxiom_id: str
    email_sha256: str = ""
    state: str
    auto_intender_decile: int
    travel_propensity_decile: int

    @field_validator("acxiom_id")
    @classmethod
    def _id(cls, v):
        if not AX_ID.match(v):
            raise ValueError("acxiom_id must look like AX1234567")
        return v

    @field_validator("auto_intender_decile", "travel_propensity_decile")
    @classmethod
    def _decile(cls, v):
        if not 1 <= v <= 10:
            raise ValueError("decile must be between 1 and 10")
        return v


class EpsilonStyleRecord(BaseModel):
    core_id: str
    email_sha256_1: str
    email_sha256_2: str = ""
    email_count: int
    opt_out_flag: str
    activate: str = "N"  # downstream activation request

    @field_validator("core_id")
    @classmethod
    def _id(cls, v):
        if not EP_ID.match(v):
            raise ValueError("core_id must look like CID1234567")
        return v

    @field_validator("opt_out_flag", "activate")
    @classmethod
    def _yn(cls, v):
        if v not in ("Y", "N"):
            raise ValueError("must be Y or N")
        return v

    @model_validator(mode="after")
    def _rules(self):
        actual = int(bool(self.email_sha256_1)) + int(bool(self.email_sha256_2))
        if self.email_count != actual:
            raise ValueError("email_count must equal the number of non-blank emails")
        if self.opt_out_flag == "Y" and self.activate == "Y":
            raise ValueError("opted-out record must not be activated")
        return self


def validate_file(path: str | Path, model: type[BaseModel]):
    """Return (valid_rows, flagged) where flagged is [(row_number, errors)]."""
    valid, flagged = [], []
    with open(path, newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            try:
                valid.append(model(**row))
            except Exception as e:  # pydantic ValidationError
                flagged.append((i, [err["msg"] for err in getattr(e, "errors", lambda: [])()] or [str(e)]))
    return valid, flagged
