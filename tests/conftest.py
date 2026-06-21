"""
Shared pytest fixtures for the PRESCRIPTION test suite.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from server.core.schemas import Medication, PatientInfo, PrescriptionSchema
from server.core.session import PrescriptionSession, ValidatedMedication


# ── Audio fixtures ──────────────────────────────────────────────────


@pytest.fixture()
def tmp_wav(tmp_path: Path) -> Path:
    """
    Return a valid 16kHz mono WAV file path populated with 0.5s of
    silence so STT and recorder tests have a concrete audio artefact.
    """
    path = tmp_path / "test_audio.wav"
    sample_rate = 16_000
    duration_s = 0.5
    n_samples = int(sample_rate * duration_s)
    silence = np.zeros(n_samples, dtype=np.int16)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(silence.tobytes())

    return path


# ── Session / prescription fixtures ────────────────────────────────


@pytest.fixture()
def minimal_prescription() -> PrescriptionSchema:
    """A minimal valid PrescriptionSchema with one medication."""
    return PrescriptionSchema(
        patient=PatientInfo(name="Ravi Kumar", age="35", gender="M"),
        diagnosis="Upper Respiratory Tract Infection",
        medications=[
            Medication(
                name="Azithromycin",
                dosage="500mg",
                frequency="Once a day",
                duration="5 days",
                instructions="Take after meals with water",
            )
        ],
        notes="Rest and stay hydrated.",
    )


@pytest.fixture()
def session_with_prescription(
    minimal_prescription: PrescriptionSchema,
) -> PrescriptionSession:
    """
    A PrescriptionSession that has been through parsing and validation
    stages, ready for PDF export tests.
    """
    session = PrescriptionSession()
    session.prescription = minimal_prescription
    session.validated_meds = [
        ValidatedMedication(
            name="Azithromycin",
            matched_name="Azithromycin 500mg",
            match_score=95,
            dosage="500mg",
            frequency="Once a day",
            duration="5 days",
            instructions="Take after meals with water",
            price="Rs. 120",
            manufacturer="Sun Pharma",
            pack_size="3 tabs",
        )
    ]
    return session


@pytest.fixture()
def session_long_instructions(
    minimal_prescription: PrescriptionSchema,
) -> PrescriptionSession:
    """
    Session where the instructions field exceeds 20 characters to
    verify the old [:20] truncation is gone.
    """
    long_instructions = (
        "Take one tablet at night after dinner for exactly 5 days "
        "without skipping any dose even if feeling better."
    )
    session = PrescriptionSession()
    session.prescription = minimal_prescription
    session.validated_meds = [
        ValidatedMedication(
            name="Paracetamol",
            matched_name="Paracetamol 650",
            match_score=88,
            dosage="650mg",
            frequency="TDS",
            duration="3 days",
            instructions=long_instructions,
            price="Rs. 30",
            manufacturer="Cipla",
        )
    ]
    return session
