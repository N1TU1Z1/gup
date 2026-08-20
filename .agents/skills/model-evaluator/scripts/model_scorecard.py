#!/usr/bin/env python3
"""Read the model_performance view without mutating the SQLite ledger."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB = Path(__file__).resolve().parents[4] / "持仓" / "holdings.sqlite3"


def load_scorecard(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.is_file():
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'view' AND name = 'model_performance'"
        ).fetchone()
        if exists is None:
            raise RuntimeError(
                "缺少 model_performance 视图，请先应用 "
                "持仓/migrations/migration_003_investment_model.sql"
            )
        rows = connection.execute(
            "SELECT * FROM model_performance "
            "ORDER BY settled_samples DESC, model_version, horizon_trade_days"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def render_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "暂无已结算模型样本。"
    columns = list(rows[0])
    widths = {
        column: max(len(column), *(len("N/A" if row[column] is None else str(row[column])) for row in rows))
        for column in columns
    }
    header = " | ".join(column.ljust(widths[column]) for column in columns)
    divider = "-+-".join("-" * widths[column] for column in columns)
    body = [
        " | ".join(("N/A" if row[column] is None else str(row[column])).ljust(widths[column]) for column in columns)
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def main() -> int:
    parser = argparse.ArgumentParser(description="只读输出投资模型绩效记分卡")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 台账路径")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    args = parser.parse_args()

    rows = load_scorecard(args.db.resolve())
    if args.format == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print(render_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
