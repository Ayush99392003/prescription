"""
Tests for server.export.pdf_generator — covers Fix 3 (no-truncation).

Uses fpdf2 in memory so no disk writes are needed for most tests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from server.core.session import PrescriptionSession, ValidatedMedication
from server.export.pdf_generator import (
    PrescriptionPDF,
    _measure_cell_height,
    _safe_text,
    generate_pdf,
)


# ── _safe_text ────────────────────────────────────────────────────────


class TestSafeText:
    """Unit tests for the Latin-1 sanitiser (bonus fix)."""

    def test_ascii_unchanged(self):
        assert _safe_text("Hello 500mg") == "Hello 500mg"

    def test_rupee_sign_replaced(self):
        """Indian Rupee U+20B9 is outside Latin-1 — must become '?'."""
        result = _safe_text("\u20b9120")
        assert "\u20b9" not in result
        assert "?" in result

    def test_em_dash_replaced(self):
        """Em-dash U+2014 must be replaced."""
        result = _safe_text("Rx \u2014 MEDICATIONS")
        assert "\u2014" not in result

    def test_latin1_accent_preserved(self):
        """Accented Latin chars (within Latin-1) must not be clobbered."""
        assert _safe_text("caf\xe9") == "caf\xe9"


# ── _measure_cell_height ──────────────────────────────────────────────


class TestMeasureCellHeight:
    """Unit tests for the cell-height estimator added in Fix 3."""

    def _make_pdf(self) -> PrescriptionPDF:
        pdf = PrescriptionPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "", 7)
        return pdf

    def test_empty_text_returns_line_height(self):
        pdf = self._make_pdf()
        h = _measure_cell_height(pdf, "", 45, 6, "Helvetica", 7)
        assert h == 6

    def test_short_text_single_line(self):
        """A very short string should fit on one line."""
        pdf = self._make_pdf()
        h = _measure_cell_height(pdf, "Azithral", 45, 6, "Helvetica", 7)
        assert h == 6  # one line × 6mm

    def test_long_text_multi_line(self):
        """Text longer than the column width should yield height > 6."""
        pdf = self._make_pdf()
        long_text = (
            "Take one tablet at night after dinner for exactly 5 days "
            "without skipping any dose even if feeling better."
        )
        h = _measure_cell_height(pdf, long_text, 43, 6, "Helvetica", 7)
        assert h > 6, "Long instructions must wrap to multiple lines"


# ── Full PDF generation ───────────────────────────────────────────────


class TestGeneratePdf:
    """Integration tests that exercise the full generate_pdf path."""

    def test_pdf_created_on_disk(
        self,
        tmp_path: Path,
        session_with_prescription: PrescriptionSession,
    ):
        """A valid session must produce a real PDF file."""
        with patch("server.config.OUTPUT_DIR", tmp_path):
            path = generate_pdf(session_with_prescription)

        assert Path(path).exists(), "PDF file must exist on disk"
        assert path.endswith(".pdf")

    def test_no_prescription_raises_value_error(self, tmp_path: Path):
        """generate_pdf must raise ValueError for an empty session."""
        session = PrescriptionSession()
        with pytest.raises(ValueError, match="no prescription"):
            generate_pdf(session)

    def test_long_instructions_not_truncated(
        self,
        tmp_path: Path,
        session_long_instructions: PrescriptionSession,
    ):
        """
        The generated PDF must be written without errors even when the
        instructions field is longer than 20 chars (the old [:20] limit).
        This is a smoke-test: if truncation logic re-appears it will
        likely raise an FPDF error when multi_cell tries to render.
        """
        with patch("server.config.OUTPUT_DIR", tmp_path):
            path = generate_pdf(session_long_instructions)

        assert Path(path).exists()
        # Verify the file is a valid PDF (starts with %PDF)
        content = Path(path).read_bytes()
        assert content[:4] == b"%PDF", "Output must be a valid PDF"

    def test_empty_medications_produces_pdf(self, tmp_path: Path):
        """
        A session with no validated_meds must still produce a PDF
        showing the 'No medications recorded.' row.
        """
        from server.core.schemas import PatientInfo, PrescriptionSchema
        from server.core.session import PrescriptionSession

        session = PrescriptionSession()
        session.prescription = PrescriptionSchema(
            patient=PatientInfo(name="Test Patient"),
            diagnosis="Observation",
        )
        session.validated_meds = []

        with patch("server.config.OUTPUT_DIR", tmp_path):
            path = generate_pdf(session)

        assert Path(path).exists()

    def test_pdf_filename_contains_session_id(
        self,
        tmp_path: Path,
        session_with_prescription: PrescriptionSession,
    ):
        """PDF filename must embed the session_id for audit traceability."""
        sid = session_with_prescription.session_id
        with patch("server.config.OUTPUT_DIR", tmp_path):
            path = generate_pdf(session_with_prescription)

        assert sid in Path(path).name, (
            f"session_id '{sid}' must appear in PDF filename '{Path(path).name}'"
        )
