"""
Session state manager. Tracks one prescription session lifecycle
from audio capture through to PDF export.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from server.core.schemas import PrescriptionSchema


@dataclass
class ValidatedMedication:
    """A medication enriched with database-validated info."""

    name: str
    matched_name: Optional[str] = None
    match_score: int = 0
    price: Optional[str] = None
    manufacturer: Optional[str] = None
    pack_size: Optional[str] = None
    dosage: str = "Not specified"
    frequency: str = "Not specified"
    duration: str = "Not specified"
    instructions: str = ""


@dataclass
class PrescriptionSession:
    """
    Holds all artefacts produced during one prescription session.
    Acts as the data bus between pipeline stages.
    """

    session_id: str = field(
        default_factory=lambda: str(int(time.time()))
    )
    audio_path: Optional[str] = None
    transcript: Optional[str] = None
    raw_llm_output: Optional[str] = None
    prescription: Optional[PrescriptionSchema] = None
    validated_meds: list[ValidatedMedication] = field(
        default_factory=list
    )
    pdf_path: Optional[str] = None
    started_at: float = field(default_factory=time.time)

    def elapsed(self) -> float:
        """Return seconds elapsed since the session started."""
        return round(time.time() - self.started_at, 2)

    def is_complete(self) -> bool:
        """True when a PDF has been successfully generated."""
        return self.pdf_path is not None


FREQUENCY_MAP = {
    "od": "Once daily",
    "qd": "Once daily",
    "bd": "Twice daily",
    "bid": "Twice daily",
    "tds": "3 times a day",
    "tid": "3 times a day",
    "qds": "4 times a day",
    "qid": "4 times a day",
    "hs": "At bedtime (nightly)",
    "sos": "As needed (emergency)",
    "prn": "As needed",
}


def translate_frequency(freq: str) -> str:
    """Translate standard frequency shorthand to simpler terms."""
    if not freq:
        return "Not specified"
    clean = freq.strip().lower()
    return FREQUENCY_MAP.get(clean, freq)
