"""
PDF prescription generator using fpdf2.
Produces a clean, printable A4 document with clinic branding.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fpdf import FPDF
from rich.console import Console

from server import config

if TYPE_CHECKING:
    from server.core.session import PrescriptionSession

console = Console()


def _safe_text(value: str) -> str:
    """
    Sanitise a string for fpdf2's built-in Latin-1 fonts.

    Replaces any character outside the Latin-1 range (e.g. the Indian
    Rupee sign U+20B9) with '?' so the PDF is never aborted by a
    FPDFUnicodeEncodingException.

    Args:
        value: Raw text to sanitise.

    Returns:
        Latin-1-safe string.
    """
    return value.encode("latin-1", errors="replace").decode("latin-1")


class PrescriptionPDF(FPDF):
    """
    Custom FPDF subclass for prescription documents.
    Adds header and footer automatically on every page.
    """

    def header(self) -> None:
        """Render clinic header on every page."""
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(30, 80, 160)
        self.cell(0, 10, config.CLINIC_NAME, align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_font("Helvetica", "", 9)
        self.set_text_color(80, 80, 80)
        self.cell(0, 5, config.CLINIC_ADDRESS, align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, f"Tel: {config.CLINIC_PHONE}", align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_draw_color(30, 80, 160)
        self.set_line_width(0.5)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(6)

    def footer(self) -> None:
        """Render page number at the bottom of every page."""
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def generate_pdf(session: "PrescriptionSession") -> str:
    """
    Generate a prescription PDF from a completed session.

    Args:
        session: A PrescriptionSession with validated_meds and
                 prescription populated.

    Returns:
        Absolute path to the saved PDF file.

    Raises:
        ValueError: If session has no prescription data.
        RuntimeError: On PDF write failure.
    """
    if session.prescription is None:
        raise ValueError(
            "Session has no prescription — cannot generate PDF."
        )

    pdf = PrescriptionPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    rx = session.prescription
    now = datetime.datetime.now().strftime("%d %b %Y  %H:%M")

    # ── Doctor / Date block ─────────────────────────────────────
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(95, 6, f"Dr: {config.DOCTOR_NAME}", new_x="RIGHT", new_y="TOP")
    pdf.cell(95, 6, f"Date: {now}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"Reg: {config.DOCTOR_REG}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ── Patient block ───────────────────────────────────────────
    pdf.set_fill_color(235, 242, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 80, 160)
    pdf.cell(0, 7, "  PATIENT INFORMATION", fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pat = rx.patient
    pdf.cell(60, 6, f"Name: {pat.name}")
    pdf.cell(60, 6, f"Age: {pat.age or 'N/A'}")
    pdf.cell(0, 6, f"Gender: {pat.gender or 'N/A'}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Patient ID: {pat.id or 'N/A'}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ── Diagnosis ───────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 80, 160)
    pdf.set_fill_color(235, 242, 255)
    pdf.cell(0, 7, "  DIAGNOSIS", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 6, rx.diagnosis)
    pdf.ln(4)

    # ── Medications table ────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 80, 160)
    pdf.set_fill_color(235, 242, 255)
    pdf.cell(0, 7, "  Rx - MEDICATIONS", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    _draw_med_table(pdf, session)
    pdf.ln(6)

    # ── Notes ────────────────────────────────────────────────────
    if rx.notes:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 80, 160)
        pdf.cell(0, 6, "Notes:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 5, rx.notes)
        pdf.ln(4)

    # ── Doctor signature ─────────────────────────────────────────
    pdf.ln(10)
    pdf.set_draw_color(30, 80, 160)
    pdf.line(130, pdf.get_y(), 200, pdf.get_y())
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.set_x(130)
    pdf.cell(70, 5, "Doctor's Signature", align="C")

    # ── Save ─────────────────────────────────────────────────────
    out_path = (
        config.OUTPUT_DIR
        / f"prescription_{session.session_id}.pdf"
    )
    try:
        pdf.output(str(out_path))
    except Exception as exc:
        raise RuntimeError(
            f"Failed to write PDF: {exc}"
        ) from exc

    console.print(
        f"[green]✓ PDF saved →[/green] [bold]{out_path}[/bold]"
    )
    return str(out_path)


def _draw_med_table(
    pdf: PrescriptionPDF,
    session: "PrescriptionSession",
) -> None:
    """Render the medications table with validated pricing data."""
    # Column widths (mm) — must sum to 190 (A4 - margins)
    col_w = {
        "Medicine": 45,
        "Dosage": 22,
        "Frequency": 28,
        "Duration": 22,
        "Instructions": 43,
        "Price": 18,
        "Manufacturer": 22,
    }
    headers = list(col_w.keys())
    widths = list(col_w.values())

    # ── Header row ─────────────────────────────────────────────
    pdf.set_fill_color(30, 80, 160)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 7)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()

    # ── Data rows ───────────────────────────────────────────────
    # Row height used for short fixed columns; long-text columns
    # use multi_cell which handles wrapping automatically.
    row_h = 6
    pdf.set_text_color(30, 30, 30)
    pdf.set_font("Helvetica", "", 7)
    fill = False

    for med in session.validated_meds:
        bg = (245, 248, 255) if fill else (255, 255, 255)
        pdf.set_fill_color(*bg)

        # Calculate the natural multi_cell height for long columns
        # so all short cells in the same row can match it.
        med_name = med.matched_name or med.name
        instructions = med.instructions or ""

        # Measure wrapped height for the two long columns
        name_h = _measure_cell_height(
            pdf, med_name, col_w["Medicine"], row_h, "Helvetica", 7
        )
        inst_h = _measure_cell_height(
            pdf, instructions, col_w["Instructions"], row_h, "Helvetica", 7
        )
        actual_h = max(row_h, name_h, inst_h)

        x_start = pdf.get_x()
        y_start = pdf.get_y()

        col_idx = 0
        for col_name, w in col_w.items():
            x = x_start + sum(widths[:col_idx])
            pdf.set_xy(x, y_start)

            if col_name in ("Medicine", "Instructions"):
                text = _safe_text(
                    med_name if col_name == "Medicine" else instructions
                )
                pdf.multi_cell(
                    w, row_h, text,
                    border=1, fill=True,
                    max_line_height=pdf.font_size,
                )
            else:
                # Short column: fixed cell, padded to actual_h
                val_map = {
                    "Dosage": med.dosage,
                    "Frequency": med.frequency,
                    "Duration": med.duration,
                    "Price": med.price or "N/A",
                    "Manufacturer": (med.manufacturer or "N/A")[:16],
                }
                pdf.cell(
                    w, actual_h,
                    _safe_text(str(val_map[col_name])),
                    border=1, fill=True,
                )

            col_idx += 1

        pdf.set_xy(x_start, y_start + actual_h)
        pdf.ln(0)
        fill = not fill

    if not session.validated_meds:
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 6, "No medications recorded.", border=1)
        pdf.ln()


def _measure_cell_height(
    pdf: PrescriptionPDF,
    text: str,
    width: float,
    line_h: float,
    font_family: str,
    font_size: int,
) -> float:
    """
    Estimate the rendered height of a multi_cell for a given text.

    Uses character-count heuristic: chars_per_line = width / avg_char_w.

    Args:
        pdf: The active FPDF instance.
        text: Text to measure.
        width: Cell width in mm.
        line_h: Height per line in mm.
        font_family: Font family name.
        font_size: Font size in pt.

    Returns:
        Estimated total height in mm.
    """
    if not text:
        return line_h
    # Approximate character width at this size/font
    avg_char_w = pdf.get_string_width("m") or (font_size * 0.4)
    chars_per_line = max(1, int(width / avg_char_w))
    import math
    lines = math.ceil(len(text) / chars_per_line)
    return lines * line_h
