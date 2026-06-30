"""
Unit tests for tiered fuzzy matching based on specialty.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import patch


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _reset_indexer():
    import server.data.indexer as idx
    idx._INDEX.clear()
    idx._NAMES.clear()
    idx._SPECIALTY_INDEX.clear()
    idx._SPECIALTY_NAMES.clear()
    idx._LOADED = False


def test_tiered_matching(tmp_path: Path):
    """Verify tiered fuzzy matching searches specialty first,
    then falls back.
    """
    _reset_indexer()

    # Create dummy meds.csv
    csv_rows = [
        {"name": "Atorva 10", "price": "100", "manufacturer": "Cipla"},
        {"name": "Calpol 250", "price": "20", "manufacturer": "GSK"},
        {"name": "Dermacream", "price": "50", "manufacturer": "Glenmark"},
    ]
    csv_path = tmp_path / "meds.csv"
    _write_csv(csv_path, csv_rows)

    # Create dummy specialty_medicines.json
    specialty_data = {
        "cardiology": [
            {"name": "Atorva 10", "price": "100", "manufacturer": "Cipla"}
        ],
        "pediatrics": [
            {"name": "Calpol 250", "price": "20", "manufacturer": "GSK"}
        ],
    }
    json_path = tmp_path / "specialty_medicines.json"
    _write_json(json_path, specialty_data)

    from server.data.fuzzy_matcher import find_best_match

    # Mock config paths to point to our temp files
    with (
        patch("server.config.CSV_PATH", csv_path),
        patch("server.data.indexer.Path.exists", return_value=True),
    ):
        # Test Case 1: Match within specialty
        res = find_best_match("Atorva", specialty="cardiology")
        assert res is not None
        matched_name, score, row = res
        assert matched_name == "Atorva 10"
        assert row["manufacturer"] == "Cipla"

        # Test Case 2: Match fallback (exists globally but not in cardo)
        res = find_best_match("Calpol", specialty="cardiology")
        assert res is not None
        matched_name, score, row = res
        assert matched_name == "Calpol 250"
        assert row["manufacturer"] == "GSK"

        # Test Case 3: Match with correct specialty directly
        res = find_best_match("Calpol", specialty="pediatrics")
        assert res is not None
        matched_name, score, row = res
        assert matched_name == "Calpol 250"
        assert row["manufacturer"] == "GSK"
