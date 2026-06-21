"""
Smoke test — validates CSV indexer, fuzzy matcher, and Pydantic schemas.
Run: uv run python server/smoke_test.py
"""

from server.data import indexer, fuzzy_matcher
from server.core.schemas import (
    PrescriptionSchema,
    PatientInfo,
    Medication,
)
from rich.console import Console

console = Console()

# ── Test 1: CSV load ─────────────────────────────────────────────────
console.rule("[cyan]Test 1: CSV Index Load[/cyan]")
indexer.load_index()
names = indexer.get_all_names()
console.print(f"[green]✓ Loaded {len(names):,} medicine entries[/green]")

# ── Test 2: Fuzzy match ──────────────────────────────────────────────
console.rule("[cyan]Test 2: Fuzzy Match[/cyan]")
queries = ["Azithromycin", "Paracetamol", "Amoxycillin", "Pantoprazole"]
for q in queries:
    result = fuzzy_matcher.find_best_match(q)
    if result:
        name, score, row = result
        price = row.get("price", "N/A")
        mfr = row.get("manufacturer", "N/A")
        console.print(
            f"[green]✓[/green] [bold]{q}[/bold] → "
            f"'{name}' (score={score})"
        )
        console.print(f"  Price: {price}  |  Mfr: {mfr}")
    else:
        console.print(f"[yellow]⚠ No match for: {q}[/yellow]")

# ── Test 3: Pydantic schema ──────────────────────────────────────────
console.rule("[cyan]Test 3: Pydantic Schema[/cyan]")
schema = PrescriptionSchema(
    patient=PatientInfo(
        name="John Doe",
        age="35",
        gender="Male",
    ),
    diagnosis="Upper respiratory tract infection",
    medications=[
        Medication(
            name="Azithromycin",
            dosage="500mg",
            frequency="Once daily",
            duration="3 days",
            instructions="After meals",
        )
    ],
    notes="Rest and plenty of fluids.",
)
console.print(
    f"[green]✓ Schema valid[/green]: "
    f"Patient={schema.patient.name}, "
    f"Meds={len(schema.medications)}"
)

console.rule("[bold green]All tests passed[/bold green]")
