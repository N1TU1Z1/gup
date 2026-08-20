"""Unit tests for heatmap metadata refresh rules."""

from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "stock-screener" / "scripts" / "market_heatmap.py"
SPEC = importlib.util.spec_from_file_location("market_heatmap", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class IndustryMappingRefreshTests(unittest.TestCase):
    def test_new_database_contains_industry_validation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = MODULE._connect_db(Path(directory) / "heatmap.sqlite3")
            try:
                columns = {row["name"] for row in database.execute("PRAGMA table_info(industry_map)")}
            finally:
                database.close()
        self.assertIn("sample_size", columns)
        self.assertIn("agreement_count", columns)

    def test_missing_or_single_sample_mapping_requires_refresh(self) -> None:
        today = date(2026, 8, 14)
        self.assertTrue(MODULE._industry_mapping_needs_refresh(None, today))
        self.assertTrue(
            MODULE._industry_mapping_needs_refresh(
                {"source_date": "2026-08-14", "sample_size": 1},
                today,
            )
        )

    def test_verified_mapping_uses_thirty_day_ttl(self) -> None:
        today = date(2026, 8, 14)
        self.assertFalse(
            MODULE._industry_mapping_needs_refresh(
                {"source_date": "2026-08-01", "sample_size": 3},
                today,
            )
        )
        self.assertTrue(
            MODULE._industry_mapping_needs_refresh(
                {"source_date": "2026-07-15", "sample_size": 3},
                today,
            )
        )


if __name__ == "__main__":
    unittest.main()
