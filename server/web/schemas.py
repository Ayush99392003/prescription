"""
Pydantic response models for the FastAPI web layer.
Keeps API contracts explicit and auto-generates OpenAPI docs.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class SessionCreatedResponse(BaseModel):
    """Returned by POST /api/session/start."""

    session_id: str
    started_at: float


class MedicationOut(BaseModel):
    """Single medication row for the API response."""

    name: str
    matched_name: Optional[str] = None
    match_score: int = 0
    dosage: str = "Not specified"
    frequency: str = "Not specified"
    duration: str = "Not specified"
    instructions: str = ""
    price: Optional[str] = None
    manufacturer: Optional[str] = None


class PatientOut(BaseModel):
    """Patient demographic data for the API response."""

    name: str
    age: Optional[str] = None
    gender: Optional[str] = None
    id: Optional[str] = None


class SessionStatusResponse(BaseModel):
    """Full session state snapshot returned by GET /api/session/{sid}."""

    session_id: str
    elapsed: float
    has_audio: bool
    has_transcript: bool
    has_prescription: bool
    has_pdf: bool
    transcript: Optional[str] = None
    patient: Optional[PatientOut] = None
    complaints: list[str] = []
    diagnosis: Optional[str] = None
    medications: list[MedicationOut] = []
    investigations: list[str] = []
    notes: Optional[str] = None
    pdf_path: Optional[str] = None


class TranscribeResponse(BaseModel):
    """Returned after Stage 2 completes."""

    session_id: str
    transcript: str


class ParseResponse(BaseModel):
    """Returned after Stage 3 completes."""

    session_id: str
    patient: PatientOut
    complaints: list[str]
    diagnosis: str
    medications: list[MedicationOut]
    investigations: list[str]
    notes: str


class ValidateResponse(BaseModel):
    """Returned after Stage 4 completes."""

    session_id: str
    medications: list[MedicationOut]


class ExportResponse(BaseModel):
    """Returned after Stage 6 (PDF export) completes."""

    session_id: str
    pdf_url: str


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    detail: str


# ── New models for state-driven UI ───────────────────────────────────


class MedicationEditIn(BaseModel):
    """A single medication row submitted from the editor form."""

    name: str
    dosage: str = "Not specified"
    frequency: str = "Not specified"
    duration: str = "Not specified"
    instructions: str = ""


class SessionUpdateRequest(BaseModel):
    """
    Request body for PATCH /api/session/{sid}/update.
    Doctor-edited fields from the Rx Editor screen.
    """

    patient_name: Optional[str] = None
    patient_age: Optional[str] = None
    patient_gender: Optional[str] = None
    patient_id: Optional[str] = None
    complaints: Optional[list[str]] = None
    diagnosis: Optional[str] = None
    medications: Optional[list[MedicationEditIn]] = None
    investigations: Optional[list[str]] = None
    notes: Optional[str] = None


class MedicineSearchResult(BaseModel):
    """A single autocomplete candidate returned from the search API."""

    name: str
    score: int
    price: Optional[str] = None
    manufacturer: Optional[str] = None


class MedicineSearchResponse(BaseModel):
    """Wrapper returned by GET /api/medicines/search."""

    query: str
    results: list[MedicineSearchResult]
