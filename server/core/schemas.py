"""
Pydantic schemas — the canonical data structures for the pipeline.
Every LLM provider output MUST be validated against these models.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Medication(BaseModel):
    """A single prescribed medication entry."""

    name: str = Field(
        ...,
        description="Medicine brand/generic name as spoken",
    )
    dosage: str = Field(
        default="Not specified",
        description="e.g. '500mg', '10ml'",
    )
    frequency: str = Field(
        default="Not specified",
        description="e.g. 'twice a day', 'OD', 'TDS'",
    )
    duration: str = Field(
        default="Not specified",
        description="e.g. '5 days', '2 weeks'",
    )
    instructions: str = Field(
        default="",
        description="Special notes e.g. 'after meals'",
    )


class PatientInfo(BaseModel):
    """Basic patient demographic data."""

    name: str = Field(default="Unknown Patient")
    age: Optional[str] = Field(default=None)
    gender: Optional[str] = Field(default=None)
    id: Optional[str] = Field(
        default=None,
        description="Patient ID or MRN if mentioned",
    )


class PrescriptionSchema(BaseModel):
    """
    Top-level schema. Every LLM provider MUST return data
    parseable into this model.
    """

    patient: PatientInfo = Field(
        default_factory=PatientInfo
    )
    complaints: list[str] = Field(
        default_factory=list,
        description="Chief complaints or symptoms reported by the patient",
    )
    diagnosis: str = Field(
        default="Not specified",
        description="Primary diagnosis",
    )
    medications: list[Medication] = Field(
        default_factory=list
    )
    investigations: list[str] = Field(
        default_factory=list,
        description="Diagnostic tests, lab investigations, or scans ordered",
    )
    notes: str = Field(
        default="",
        description="Additional doctor notes or advice",
    )
