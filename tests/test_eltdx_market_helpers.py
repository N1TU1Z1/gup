"""Unit tests for the project market MCP validation boundary."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "stock-screener" / "scripts" / "eltdx_market_mcp.py"
SPEC = importlib.util.spec_from_file_location("eltdx_market_mcp", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class MarketMcpHelperTests(unittest.TestCase):
    def test_rank_payload_keeps_only_unique_shanghai_and_shenzhen_rows(self) -> None:
        payload = {
            "records": [
                {"exchange": "sz", "market_id": 0, "code": "000001"},
                {"exchange": "bj", "market_id": 2, "code": "920083"},
                {"exchange": "sh", "market_id": 1, "code": "600000"},
                {"exchange": "sh", "market_id": 1, "code": "600000"},
                {"exchange": "", "market_id": 9, "code": "123"},
            ],
            "raw_payload": "untrusted-wire-data",
        }

        result = MODULE._filter_rank_payload(payload, 80)

        self.assertEqual([row["full_code"] for row in result["records"]], ["sz000001", "sh600000"])
        self.assertEqual(result["filtered_out_count"], 3)
        self.assertEqual(result["returned_count"], 2)
        self.assertNotIn("raw_payload", result)

    def test_top20_codes_require_full_shanghai_or_shenzhen_codes(self) -> None:
        self.assertEqual(
            MODULE._normalize_top20_codes([" SH600000 ", "sz000001", "sh600000"]),
            ["sh600000", "sz000001"],
        )
        with self.assertRaises(ValueError):
            MODULE._normalize_top20_codes(["bj920083"])
        with self.assertRaises(ValueError):
            MODULE._normalize_top20_codes(["600000"])
        with self.assertRaises(ValueError):
            MODULE._normalize_top20_codes(["sh600000"] * 21)


if __name__ == "__main__":
    unittest.main()
