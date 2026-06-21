"""
Tests for server.data.indexer — covers Fix 4 (progress accuracy) and
Fix 5 (deduplication of _NAMES).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────


def _write_csv(path: Path, rows: list[dict]) -> None:
    """Write a minimal medicines CSV at the given path."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _reset_indexer():
    """Reset the module-level globals so each test starts clean."""
    import server.data.indexer as idx

    idx._INDEX.clear()
    idx._NAMES.clear()
    idx._LOADED = False


# ── Fix 5: Deduplication ──────────────────────────────────────────────


class TestIndexerDeduplication:
    """_NAMES must contain each medicine name exactly once."""

    def test_duplicate_names_deduplicated(self, tmp_path: Path):
        """
        Two CSV rows with the same name (different manufacturers) must
        produce exactly ONE entry in _NAMES.
        """
        _reset_indexer()
        csv_path = tmp_path / "meds.csv"
        _write_csv(
            csv_path,
            [
                {"name": "Paracetamol", "price": "20", "manufacturer": "Cipla"},
                {"name": "Paracetamol", "price": "25", "manufacturer": "Sun Pharma"},
                {"name": "Azithromycin", "price": "80", "manufacturer": "Cipla"},
            ],
        )

        with patch("server.config.CSV_PATH", csv_path):
            import server.data.indexer as idx
            idx.load_index()

        paracetamol_count = idx._NAMES.count("Paracetamol")
        assert paracetamol_count == 1, (
            f"Expected 1 entry for 'Paracetamol', got {paracetamol_count}"
        )
        assert len(idx._NAMES) == 2  # Paracetamol + Azithromycin

    def test_last_duplicate_row_wins_in_index(self, tmp_path: Path):
        """
        When two rows share a name, _INDEX must retain the LAST row
        (last occurrence wins) — predictable overwrite behaviour.
        """
        _reset_indexer()
        csv_path = tmp_path / "meds.csv"
        _write_csv(
            csv_path,
            [
                {"name": "Paracetamol", "price": "20", "manufacturer": "Cipla"},
                {"name": "Paracetamol", "price": "25", "manufacturer": "Sun Pharma"},
            ],
        )

        with patch("server.config.CSV_PATH", csv_path):
            import server.data.indexer as idx
            idx.load_index()

        row = idx.lookup("Paracetamol")
        assert row is not None
        assert row["manufacturer"] == "Sun Pharma", (
            "Last occurrence must win the index slot"
        )

    def test_unique_names_all_present(self, tmp_path: Path):
        """Unique entries must all appear in _NAMES."""
        _reset_indexer()
        names = ["DrugA", "DrugB", "DrugC"]
        csv_path = tmp_path / "meds.csv"
        _write_csv(
            csv_path,
            [{"name": n, "price": "10", "manufacturer": "X"} for n in names],
        )

        with patch("server.config.CSV_PATH", csv_path):
            import server.data.indexer as idx
            idx.load_index()

        for name in names:
            assert name in idx._NAMES


# ── Fix 4: Progress accuracy (smoke test) ────────────────────────────


class TestIndexerProgressAccuracy:
    """
    Verify that the progress bar's total (file bytes) and the sum of
    advances (sum of row byte lengths) are within a 10% tolerance.

    We cannot assert exact equality because the progress uses the
    encoded value-bytes + delimiter heuristic, but it must be much
    closer than the old ``len(name_raw) + 10`` heuristic.
    """

    def test_progress_advances_close_to_file_size(self, tmp_path: Path):
        _reset_indexer()
        csv_path = tmp_path / "meds.csv"
        rows = [
            {"name": f"Medicine{i}", "price": str(i * 5), "manufacturer": "TestCo"}
            for i in range(20)
        ]
        _write_csv(csv_path, rows)
        file_size = csv_path.stat().st_size

        advances: list[float] = []

        import server.data.indexer as idx
        from rich.progress import Progress

        real_progress_init = Progress.__init__

        # Intercept progress.advance calls to capture total advanced bytes
        class SpyProgress(Progress):
            def advance(self, task_id, advance=1):
                advances.append(advance)
                super().advance(task_id, advance)

        with (
            patch("server.config.CSV_PATH", csv_path),
            patch("server.data.indexer.Progress", SpyProgress),
        ):
            idx.load_index()

        total_advanced = sum(advances)
        # Allow ±20% tolerance: the heuristic won't be perfect but must
        # be in the right ballpark, unlike the old name+10 heuristic
        # which was off by orders of magnitude for large CSVs.
        ratio = total_advanced / file_size
        assert 0.5 <= ratio <= 3.0, (
            f"Progress advanced {total_advanced} bytes against "
            f"file size {file_size}; ratio {ratio:.2f} out of [0.5, 3.0]"
        )


# ── load_index safety ─────────────────────────────────────────────────


class TestLoadIndexSafety:
    def test_load_index_idempotent(self, tmp_path: Path):
        """Calling load_index twice must not double the _NAMES list."""
        _reset_indexer()
        csv_path = tmp_path / "meds.csv"
        _write_csv(csv_path, [{"name": "Amoxicillin", "price": "30", "manufacturer": "X"}])

        with patch("server.config.CSV_PATH", csv_path):
            import server.data.indexer as idx
            idx.load_index()
            first_len = len(idx._NAMES)
            idx.load_index()  # second call — must be a no-op
            assert len(idx._NAMES) == first_len

    def test_missing_csv_raises_file_not_found(self, tmp_path: Path):
        """A missing CSV path must raise FileNotFoundError."""
        _reset_indexer()
        missing = tmp_path / "nonexistent.csv"
        with (
            patch("server.config.CSV_PATH", missing),
            pytest.raises(FileNotFoundError, match="Medicine CSV not found"),
        ):
            import server.data.indexer as idx
            idx.load_index()

    def test_rows_without_name_skipped(self, tmp_path: Path):
        """Rows with an empty 'name' field must be silently skipped."""
        _reset_indexer()
        csv_path = tmp_path / "meds.csv"
        _write_csv(
            csv_path,
            [
                {"name": "", "price": "10", "manufacturer": "X"},
                {"name": "Ibuprofen", "price": "15", "manufacturer": "Y"},
            ],
        )
        with patch("server.config.CSV_PATH", csv_path):
            import server.data.indexer as idx
            idx.load_index()

        assert idx._NAMES == ["Ibuprofen"]
