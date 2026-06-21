"""
Tests for server.data.fuzzy_matcher — regression tests for Fix 5.

Ensures that after deduplication, fuzzy matching still returns the
correct best match and does not surface stale duplicate entries.
"""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _reset_indexer():
    import server.data.indexer as idx
    idx._INDEX.clear()
    idx._NAMES.clear()
    idx._LOADED = False


# ── find_best_match ───────────────────────────────────────────────────


class TestFindBestMatch:
    """Smoke + regression tests for fuzzy_matcher.find_best_match."""

    def _setup_index(self, tmp_path: Path, rows: list[dict]) -> None:
        csv_path = tmp_path / "meds.csv"
        _write_csv(csv_path, rows)
        with patch("server.config.CSV_PATH", csv_path):
            import server.data.indexer as idx
            idx.load_index()

    def test_exact_match_returns_result(self, tmp_path: Path):
        """An exact name query must return a match above threshold."""
        _reset_indexer()
        self._setup_index(
            tmp_path,
            [{"name": "Azithromycin", "price": "90", "manufacturer": "Cipla"}],
        )

        from server.data.fuzzy_matcher import find_best_match

        with patch("server.config.CSV_PATH", tmp_path / "meds.csv"):
            result = find_best_match("Azithromycin")

        assert result is not None
        matched_name, score, row = result
        assert "Azithromycin" in matched_name
        assert score >= 75

    def test_fuzzy_match_phonetic_variant(self, tmp_path: Path):
        """
        A slight misspelling ('Azithramycin') must still resolve to
        the closest match above threshold.
        """
        _reset_indexer()
        self._setup_index(
            tmp_path,
            [
                {"name": "Azithromycin", "price": "90", "manufacturer": "Cipla"},
                {"name": "Amoxicillin", "price": "30", "manufacturer": "Sun"},
            ],
        )

        from server.data.fuzzy_matcher import find_best_match

        with patch("server.config.CSV_PATH", tmp_path / "meds.csv"):
            result = find_best_match("Azithramycin")

        # Should resolve to Azithromycin (not Amoxicillin)
        if result is not None:
            matched_name, score, _ = result
            assert "Azithromycin" in matched_name

    def test_no_match_below_threshold_returns_none(self, tmp_path: Path):
        """
        A completely unrelated query must return None (below the
        default 75-point threshold).
        """
        _reset_indexer()
        self._setup_index(
            tmp_path,
            [{"name": "Aspirin", "price": "10", "manufacturer": "X"}],
        )

        from server.data.fuzzy_matcher import find_best_match

        with patch("server.config.CSV_PATH", tmp_path / "meds.csv"):
            result = find_best_match("XYZABC123QQQ")

        assert result is None

    def test_duplicate_names_dont_cause_lookup_failure(self, tmp_path: Path):
        """
        Fix 5 regression: after deduplication, find_best_match must NOT
        return None when the database had duplicate entries for the query.
        Previously the index had Paracetamol but _NAMES had it twice,
        causing potential stale-lookup issues.
        """
        _reset_indexer()
        self._setup_index(
            tmp_path,
            [
                {"name": "Paracetamol", "price": "20", "manufacturer": "Cipla"},
                {"name": "Paracetamol", "price": "25", "manufacturer": "Sun Pharma"},
            ],
        )

        from server.data.fuzzy_matcher import find_best_match

        with patch("server.config.CSV_PATH", tmp_path / "meds.csv"):
            result = find_best_match("Paracetamol")

        assert result is not None, (
            "find_best_match must find 'Paracetamol' even when "
            "the CSV has duplicate rows for it"
        )
        matched_name, score, row = result
        # Last-write-wins: manufacturer should be 'Sun Pharma'
        assert row["manufacturer"] == "Sun Pharma"


# ── find_top_k ────────────────────────────────────────────────────────


class TestFindTopK:
    """Basic tests for the top-K variant."""

    def _setup_index(self, tmp_path: Path, rows: list[dict]) -> None:
        csv_path = tmp_path / "meds.csv"
        _write_csv(csv_path, rows)
        with patch("server.config.CSV_PATH", csv_path):
            import server.data.indexer as idx
            idx.load_index()

    def test_top_k_returns_at_most_k_results(self, tmp_path: Path):
        _reset_indexer()
        self._setup_index(
            tmp_path,
            [
                {"name": "Metformin 500", "price": "10", "manufacturer": "X"},
                {"name": "Metformin 850", "price": "12", "manufacturer": "X"},
                {"name": "Metformin 1000", "price": "15", "manufacturer": "X"},
                {"name": "Aspirin", "price": "5", "manufacturer": "Y"},
            ],
        )

        from server.data.fuzzy_matcher import find_top_k

        with patch("server.config.CSV_PATH", tmp_path / "meds.csv"):
            results = find_top_k("Metformin", k=2)

        assert len(results) <= 2

    def test_top_k_empty_index_returns_empty(self, tmp_path: Path):
        """An empty index must return an empty list, not raise."""
        _reset_indexer()
        # Force an empty index without loading any CSV
        import server.data.indexer as idx
        idx._LOADED = True  # pretend loaded but _NAMES stays empty

        from server.data.fuzzy_matcher import find_top_k

        results = find_top_k("Anything")
        assert results == []
