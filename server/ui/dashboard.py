"""
Rich CLI dashboard — all terminal UI panels, tables, and banners.
Keeps display logic completely separate from pipeline logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from server import config

if TYPE_CHECKING:
    from server.core.session import PrescriptionSession

console = Console()


def print_banner() -> None:
    """Display the application launch banner."""
    art = Text(justify="center")
    art.append("\n  ██████╗ ██╗  ██╗    \n", style="bold cyan")
    art.append("  ██╔══██╗╚██╗██╔╝    \n", style="bold cyan")
    art.append("  ██████╔╝ ╚███╔╝     \n", style="bold blue")
    art.append("  ██╔══██╗ ██╔██╗     \n", style="bold blue")
    art.append("  ██║  ██║██╔╝ ██╗    \n", style="bold magenta")
    art.append("  ╚═╝  ╚═╝╚═╝  ╚═╝    \n", style="bold magenta")

    subtitle = Text(
        "AI-Powered Voice Medical Prescription Assistant",
        style="bold white",
        justify="center",
    )
    version = Text("v0.1.0  |  Privacy-First", style="dim", justify="center")

    console.print(Panel(
        Align.center(art + subtitle + Text("\n") + version),
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()


def print_config_summary() -> None:
    """Display current provider config at startup."""
    table = Table(
        title="Active Configuration",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
        expand=False,
    )
    table.add_column("Setting", style="bold")
    table.add_column("Value", style="green")

    table.add_row("STT Engine", config.STT_PROVIDER)
    table.add_row("Whisper Model", config.WHISPER_MODEL)
    table.add_row("LLM Engine", config.LLM_PROVIDER)
    if config.LLM_PROVIDER == "ollama":
        table.add_row("LLM Model", config.OLLAMA_MODEL)
    else:
        table.add_row("LLM Model", config.GROQ_MODEL)
    table.add_row("Audio Rate", f"{config.AUDIO_SAMPLE_RATE} Hz")
    table.add_row("Fuzzy Threshold", str(config.FUZZY_SCORE_THRESHOLD))

    console.print(Align.center(table))
    console.print()


def print_transcript(transcript: str) -> None:
    """Display the STT transcript in a styled panel."""
    console.print(Panel(
        f"[italic]{transcript}[/italic]",
        title="[bold cyan]Transcript[/bold cyan]",
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print()


def print_prescription_table(
    session: "PrescriptionSession",
) -> None:
    """
    Display the full parsed + validated prescription as a Rich table.

    Args:
        session: Completed PrescriptionSession with validated_meds.
    """
    if session.prescription is None:
        console.print("[red]No prescription data to display.[/red]")
        return

    rx = session.prescription
    pat = rx.patient

    # ── Patient info panel ──────────────────────────────────────
    info_text = (
        f"[bold]Name:[/bold]      {pat.name}\n"
        f"[bold]Age:[/bold]       {pat.age or 'N/A'}\n"
        f"[bold]Gender:[/bold]    {pat.gender or 'N/A'}\n"
        f"[bold]Patient ID:[/bold]{pat.id or 'N/A'}\n"
        f"[bold]Diagnosis:[/bold] {rx.diagnosis}"
    )
    if rx.complaints:
        complaints_str = ", ".join(rx.complaints)
        info_text += f"\n[bold]Complaints:[/bold] {complaints_str}"
    if rx.investigations:
        investigations_str = ", ".join(rx.investigations)
        info_text += f"\n[bold]Investigations:[/bold] {investigations_str}"

    console.print(Panel(
        info_text,
        title="[bold blue]Patient[/bold blue]",
        border_style="blue",
    ))
    console.print()

    # ── Medications table ────────────────────────────────────────
    from server.core.session import translate_frequency

    table = Table(
        title="Prescribed Medications",
        show_header=True,
        header_style="bold white on blue",
        border_style="blue",
        row_styles=["", "dim"],
        expand=True,
    )
    table.add_column("#", style="bold cyan", width=3)
    table.add_column("Medicine (Matched)", style="bold green")
    table.add_column("Score", justify="center")
    table.add_column("Dosage")
    table.add_column("Frequency")
    table.add_column("Duration")

    for i, med in enumerate(session.validated_meds, 1):
        score_str = (
            f"[green]{med.match_score}[/green]"
            if med.match_score >= config.FUZZY_SCORE_THRESHOLD
            else f"[red]{med.match_score}[/red]"
        )
        table.add_row(
            str(i),
            med.matched_name or f"[red]{med.name}[/red]",
            score_str,
            med.dosage,
            translate_frequency(med.frequency),
            med.duration,
        )

    console.print(table)

    if rx.notes:
        console.print(Panel(
            f"[italic]{rx.notes}[/italic]",
            title="[bold]Notes[/bold]",
            border_style="yellow",
        ))
    console.print()


def print_session_summary(session: "PrescriptionSession") -> None:
    """Print a final timing and status summary panel."""
    status = (
        "[bold green]Complete[/bold green]"
        if session.is_complete()
        else "[bold yellow]No PDF[/bold yellow]"
    )
    summary = (
        f"Session ID  : {session.session_id}\n"
        f"Status      : {status}\n"
        f"Total Time  : {session.elapsed()}s\n"
        f"PDF         : {session.pdf_path or 'N/A'}"
    )
    console.print(Panel(
        summary,
        title="[bold cyan]Session Summary[/bold cyan]",
        border_style="cyan",
    ))
    console.print()


def print_error(title: str, message: str) -> None:
    """Display a formatted error panel."""
    console.print(Panel(
        f"[bold red]{message}[/bold red]",
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
    ))
    console.print()


def print_step(step: str, detail: str = "") -> None:
    """Print a pipeline step divider."""
    console.print(Rule(
        f"[bold cyan]{step}[/bold cyan]"
        + (f" [dim]- {detail}[/dim]" if detail else ""),
        style="blue",
    ))
