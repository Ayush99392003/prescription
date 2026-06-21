"""Prompts configuration for STT engine guidance.
"""

from __future__ import annotations

# Map of specialties to common drug names and clinical abbreviations
_SPECIALTY_MAP: dict[str, list[str]] = {
    "general": [
        "PO", "TDS", "BD", "OD", "HS", "SOS", "QID", "IM", "ID", "IV",
        "mg", "ml", "caps", "tabs", "syrup", "injection",
        "Paracetamol", "Pantoprazole", "Amoxicillin", "Cetirizine",
        "Ondansetron", "Omez", "Ibuprofen", "Azithromycin",
        "Levofloxacin", "Clonazepam"
    ],
    "pediatrics": [
        "PO", "TDS", "BD", "OD", "HS", "SOS", "syrup", "drops", "ml", "mg",
        "Ondem", "Paracetamol", "Amoxyclav", "Levolin", "Maxtra", "Zinc",
        "ORS", "Crocin", "Calpol", "Ibugesic Plus", "Meftal Spas"
    ],
    "dermatology": [
        "apply locally", "twice daily", "once daily", "HS", "cream",
        "ointment", "gel", "lotion", "soap",
        "Linezolid", "Levocetirizine", "Itraconazole", "Fluconazole",
        "Mupirocin", "Fusidic", "Clobetasol", "Ketoconazole",
        "Tacrolimus", "Hydrocortisone", "cellulitis", "varicose eczema"
    ],
    "cardiology": [
        "once daily", "OD", "BD", "HS", "mg", "tabs",
        "Atorvastatin", "Clopidogrel", "Aspirin", "Metoprolol",
        "Amlodipine", "Ramipril", "Telmisartan", "Rosuvastatin",
        "Losartan", "Carvedilol"
    ]
}


def get_initial_prompt(specialty: str) -> str:
    """Generate the initial prompt string for a clinic specialty.

    Args:
        specialty: The configured clinic specialty.

    Returns:
        Comma-separated string of medical terms to guide Whisper.
    """
    spec = specialty.lower().strip()
    words = _SPECIALTY_MAP.get(spec, _SPECIALTY_MAP["general"])
    return ", ".join(words)
