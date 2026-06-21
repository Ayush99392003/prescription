"""
FastAPI session REST routes — one endpoint per pipeline stage.

Each stage maps 1:1 to the stages in server.main so the same business
logic is reused without duplication.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from server import config
from server.core.session import ValidatedMedication
from server.data import fuzzy_matcher, indexer
from server.export.pdf_generator import generate_pdf
from server.web import session_store
from server.web.schemas import (
    ErrorResponse,
    ExportResponse,
    MedicationOut,
    ParseResponse,
    PatientOut,
    SessionCreatedResponse,
    SessionStatusResponse,
    TranscribeResponse,
    ValidateResponse,
)

router = APIRouter(prefix="/api/session", tags=["session"])


# ── Helpers ───────────────────────────────────────────────────────────


def _get_or_404(sid: str):
    """Return session or raise 404."""
    session = session_store.get(sid)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{sid}' not found or expired."
        )
    return session


def _med_out(med: ValidatedMedication) -> MedicationOut:
    """Convert a ValidatedMedication dataclass to the API model."""
    return MedicationOut(
        name=med.name,
        matched_name=med.matched_name,
        match_score=med.match_score,
        dosage=med.dosage,
        frequency=med.frequency,
        duration=med.duration,
        instructions=med.instructions,
        price=med.price,
        manufacturer=med.manufacturer,
    )


def _get_llm():
    """Instantiate the configured LLM provider."""
    name = config.LLM_PROVIDER.lower()
    if name == "ollama":
        from server.llm.ollama_provider import OllamaProvider  # noqa: PLC0415
        return OllamaProvider()
    if name == "groq":
        from server.llm.groq_provider import GroqProvider  # noqa: PLC0415
        return GroqProvider()
    raise HTTPException(
        status_code=500,
        detail=f"Unknown LLM_PROVIDER: '{name}'",
    )


def _get_stt():
    """Instantiate the configured STT provider."""
    name = config.STT_PROVIDER.lower()
    if name == "faster_whisper":
        from server.voice.faster_whisper_stt import FasterWhisperSTT  # noqa: PLC0415
        return FasterWhisperSTT()
    if name == "openai_whisper":
        from server.voice.openai_whisper_stt import OpenAIWhisperSTT  # noqa: PLC0415
        return OpenAIWhisperSTT()
    raise HTTPException(
        status_code=500,
        detail=f"Unknown STT_PROVIDER: '{name}'",
    )


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post(
    "/start",
    response_model=SessionCreatedResponse,
    summary="Create a new prescription session",
)
def start_session() -> SessionCreatedResponse:
    """
    Create a new PrescriptionSession and return its ID.
    The browser must store this ID to call subsequent endpoints.
    """
    session = session_store.create()
    return SessionCreatedResponse(
        session_id=session.session_id,
        started_at=session.started_at,
    )


@router.get(
    "/{sid}",
    response_model=SessionStatusResponse,
    summary="Get full session state",
)
def get_session(sid: str) -> SessionStatusResponse:
    """Return a complete snapshot of the current session state."""
    session = _get_or_404(sid)
    rx = session.prescription

    patient = None
    diagnosis = None
    notes = None
    if rx is not None:
        patient = PatientOut(
            name=rx.patient.name,
            age=rx.patient.age,
            gender=rx.patient.gender,
            id=rx.patient.id,
        )
        diagnosis = rx.diagnosis
        notes = rx.notes

    return SessionStatusResponse(
        session_id=session.session_id,
        elapsed=session.elapsed(),
        has_audio=session.audio_path is not None,
        has_transcript=session.transcript is not None,
        has_prescription=rx is not None,
        has_pdf=session.pdf_path is not None,
        transcript=session.transcript,
        patient=patient,
        diagnosis=diagnosis,
        medications=[_med_out(m) for m in session.validated_meds],
        notes=notes,
        pdf_path=session.pdf_path,
    )


@router.post(
    "/{sid}/upload",
    response_model=TranscribeResponse,
    summary="Upload a WAV file and transcribe it",
)
async def upload_and_transcribe(
    sid: str,
    file: UploadFile,
) -> TranscribeResponse:
    """
    Accept a WAV blob from the browser's MediaRecorder, save it, then
    run the STT provider synchronously and return the transcript.

    Combines upload + transcription in one call so the browser only
    needs a single round-trip.
    """
    session = _get_or_404(sid)

    # Save the uploaded audio to the output directory
    audio_path = str(
        config.OUTPUT_DIR / f"audio_{session.session_id}.wav"
    )
    content = await file.read()
    Path(audio_path).write_bytes(content)
    session.audio_path = audio_path

    # Run STT
    stt = _get_stt()
    if not stt.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"STT provider '{config.STT_PROVIDER}' is not available.",
        )
    try:
        session.transcript = stt.transcribe(audio_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return TranscribeResponse(
        session_id=sid,
        transcript=session.transcript,
    )


@router.post(
    "/{sid}/parse",
    response_model=ParseResponse,
    summary="Run LLM parsing on the transcript",
)
def parse_transcript(sid: str) -> ParseResponse:
    """
    Send the stored transcript to the configured LLM provider and
    return the structured prescription data.
    """
    session = _get_or_404(sid)
    if session.transcript is None:
        raise HTTPException(
            status_code=400,
            detail="No transcript found. Upload audio first.",
        )

    llm = _get_llm()
    if not llm.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider '{config.LLM_PROVIDER}' is not available.",
        )

    try:
        session.prescription = llm.parse_prescription(session.transcript)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    rx = session.prescription
    return ParseResponse(
        session_id=sid,
        patient=PatientOut(
            name=rx.patient.name,
            age=rx.patient.age,
            gender=rx.patient.gender,
            id=rx.patient.id,
        ),
        diagnosis=rx.diagnosis,
        medications=[
            MedicationOut(name=m.name, dosage=m.dosage,
                          frequency=m.frequency, duration=m.duration,
                          instructions=m.instructions)
            for m in rx.medications
        ],
        notes=rx.notes,
    )


@router.post(
    "/{sid}/validate",
    response_model=ValidateResponse,
    summary="Fuzzy-match medications against the medicines database",
)
def validate_medications(sid: str) -> ValidateResponse:
    """
    Cross-reference each extracted medication against the Indian
    medicines dataset using rapidfuzz.
    """
    session = _get_or_404(sid)
    if session.prescription is None:
        raise HTTPException(
            status_code=400,
            detail="No prescription to validate. Run /parse first.",
        )

    try:
        indexer.load_index()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    session.validated_meds = []
    for med in session.prescription.medications:
        result = fuzzy_matcher.find_best_match(med.name)
        vm = ValidatedMedication(
            name=med.name,
            dosage=med.dosage,
            frequency=med.frequency,
            duration=med.duration,
            instructions=med.instructions,
        )
        if result is not None:
            matched_name, score, row = result
            vm.matched_name = matched_name
            vm.match_score = score
            vm.price = row.get("price")
            vm.manufacturer = row.get("manufacturer")
            vm.pack_size = row.get("pack_size")
        else:
            vm.match_score = 0
        session.validated_meds.append(vm)

    return ValidateResponse(
        session_id=sid,
        medications=[_med_out(m) for m in session.validated_meds],
    )


@router.post(
    "/{sid}/export",
    response_model=ExportResponse,
    summary="Generate and save the PDF prescription",
)
def export_pdf(sid: str) -> ExportResponse:
    """
    Generate the PDF from the validated session data and return the
    download URL.
    """
    session = _get_or_404(sid)
    if session.prescription is None:
        raise HTTPException(
            status_code=400,
            detail="No prescription data. Run /parse first.",
        )
    if not session.validated_meds:
        raise HTTPException(
            status_code=400,
            detail="No validated medications. Run /validate first.",
        )

    try:
        session.pdf_path = generate_pdf(session)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ExportResponse(
        session_id=sid,
        pdf_url=f"/api/session/{sid}/pdf",
    )


@router.get(
    "/{sid}/pdf",
    summary="Download the generated PDF",
    response_class=FileResponse,
)
def download_pdf(sid: str) -> FileResponse:
    """Stream the generated PDF to the browser."""
    session = _get_or_404(sid)
    if session.pdf_path is None:
        raise HTTPException(
            status_code=404,
            detail="PDF not yet generated. Call /export first.",
        )
    if not Path(session.pdf_path).exists():
        raise HTTPException(
            status_code=404,
            detail="PDF file missing from disk.",
        )
    return FileResponse(
        path=session.pdf_path,
        media_type="application/pdf",
        filename=f"prescription_{sid}.pdf",
    )
