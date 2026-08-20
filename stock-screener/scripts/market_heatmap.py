#!/usr/bin/env python3
"""沪深 A 股全量快照、SQLite 归档与本地热力图服务。"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

from eltdx import TdxClient
from eltdx.f10 import F10Client


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "market_heatmap.sqlite3"
QUOTE_BATCH_SIZE = 80
FINANCE_BATCH_SIZE = 100
INDUSTRY_REPRESENTATIVE_COUNT = 3
INDUSTRY_MAPPING_TTL = timedelta(days=30)


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    completed_at TEXT,
    capture_stage TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'complete', 'failed')),
    source TEXT NOT NULL DEFAULT 'eltdx-7709',
    universe_count INTEGER NOT NULL DEFAULT 0,
    quoted_count INTEGER NOT NULL DEFAULT 0,
    valid_quote_count INTEGER NOT NULL DEFAULT 0,
    finance_count INTEGER NOT NULL DEFAULT 0,
    industry_count INTEGER NOT NULL DEFAULT 0,
    failed_batches INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_runs_date_time
ON scan_runs(trade_date, captured_at DESC);

CREATE TABLE IF NOT EXISTS industry_map (
    industry_raw INTEGER PRIMARY KEY,
    industry_name TEXT NOT NULL,
    source_code TEXT,
    source_date TEXT,
    sample_size INTEGER NOT NULL DEFAULT 0,
    agreement_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS securities (
    full_code TEXT PRIMARY KEY,
    exchange TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    board TEXT,
    category TEXT NOT NULL,
    industry_raw INTEGER,
    industry_name TEXT,
    province_raw INTEGER,
    ipo_date TEXT,
    finance_updated_date TEXT,
    is_st INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_securities_industry
ON securities(industry_name, full_code);

CREATE TABLE IF NOT EXISTS market_snapshots (
    run_id INTEGER NOT NULL REFERENCES scan_runs(id) ON DELETE CASCADE,
    full_code TEXT NOT NULL REFERENCES securities(full_code),
    quote_time_raw INTEGER,
    last_price REAL,
    pre_close_price REAL,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    change_pct REAL,
    volume_hand REAL,
    amount REAL,
    open_amount_yuan REAL,
    inside_volume_hand REAL,
    outside_volume_hand REAL,
    circulating_shares REAL,
    total_shares REAL,
    circulating_market_cap REAL,
    total_market_cap REAL,
    turnover_rate REAL,
    eps REAL,
    net_profit_yuan REAL,
    operating_cash_flow_yuan REAL,
    quote_valid INTEGER NOT NULL DEFAULT 0,
    data_quality TEXT NOT NULL,
    PRIMARY KEY (run_id, full_code)
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_run_valid
ON market_snapshots(run_id, quote_valid, full_code);
"""


@dataclass(slots=True)
class ScanResult:
    run_id: int
    trade_date: str
    captured_at: str
    capture_stage: str
    universe_count: int
    quoted_count: int
    valid_quote_count: int
    finance_count: int
    industry_count: int
    failed_batches: int


def _connect_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(industry_map)")}
    if "sample_size" not in columns:
        connection.execute("ALTER TABLE industry_map ADD COLUMN sample_size INTEGER NOT NULL DEFAULT 0")
    if "agreement_count" not in columns:
        connection.execute("ALTER TABLE industry_map ADD COLUMN agreement_count INTEGER NOT NULL DEFAULT 0")
    connection.commit()
    return connection


def _chunks(items: Sequence[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield list(items[index : index + size])


def _capture_stage(moment: datetime) -> str:
    current = moment.time()
    if current < time(9, 15):
        return "准备态"
    if current < time(9, 25):
        return "竞价进行中"
    if current < time(9, 30):
        return "竞价定格"
    if current < time(15, 0):
        return "盘中快照"
    return "收盘快照"


def _is_st_name(name: str) -> bool:
    normalized = name.upper().replace(" ", "")
    return "ST" in normalized or "退" in normalized


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _retry(callable_: Any, attempts: int = 2) -> Any:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return callable_()
        except Exception as exc:  # 同源仅重试一次
            last_error = exc
    assert last_error is not None
    raise last_error


def _fetch_quote_batches(client: TdxClient, codes: list[str], workers: int) -> tuple[dict[str, Any], list[str]]:
    batches = list(_chunks(codes, QUOTE_BATCH_SIZE))
    quotes: dict[str, Any] = {}
    errors: list[str] = []

    def fetch(batch: list[str]) -> list[Any]:
        result = _retry(lambda: client.quotes.get_snapshots(batch))
        return list(result or [])

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(fetch, batch): batch for batch in batches}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            batch = futures[future]
            try:
                for quote in future.result():
                    quotes[quote.full_code] = quote
            except Exception as exc:
                errors.append(f"{batch[0]}..{batch[-1]}: {exc}")
            if completed % 12 == 0 or completed == len(batches):
                print(f"行情批次 {completed}/{len(batches)}，已返回 {len(quotes)} 只", flush=True)
    return quotes, errors


def _fetch_finance_batches(
    client: TdxClient,
    codes: list[str],
    workers: int,
) -> tuple[dict[str, Any], list[str]]:
    records: dict[str, Any] = {}
    errors: list[str] = []
    batches = list(_chunks(codes, FINANCE_BATCH_SIZE))

    def fetch(batch: list[str]) -> list[Any]:
        response = _retry(lambda: client.get_finance_batch(batch, refresh=True))
        return list(response.records)

    with ThreadPoolExecutor(max_workers=min(max(1, workers), 6)) as executor:
        futures = {executor.submit(fetch, batch): batch for batch in batches}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            batch = futures[future]
            try:
                for record in future.result():
                    records[record.full_code] = record
            except Exception as exc:
                errors.append(f"{batch[0]}..{batch[-1]}: {exc}")
            if completed % 10 == 0 or completed == len(batches):
                print(f"财务批次 {completed}/{len(batches)}，已返回 {len(records)} 只", flush=True)
    return records, errors


def _industry_name(f10: F10Client, code: str) -> str | None:
    response = _retry(lambda: f10.stock_score(code))
    for result_set in response.result_sets:
        for row in result_set.rows:
            value = row.get("N012")
            if isinstance(value, str):
                name = " ".join(value.strip().split())[:40]
                if name:
                    return name
    return None


def _load_industry_map(connection: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    return {
        int(row["industry_raw"]): {
            "industry_name": str(row["industry_name"]),
            "source_date": row["source_date"],
            "sample_size": int(row["sample_size"] or 0),
            "agreement_count": int(row["agreement_count"] or 0),
        }
        for row in connection.execute(
            "SELECT industry_raw, industry_name, source_date, sample_size, agreement_count FROM industry_map"
        )
    }


def _industry_mapping_needs_refresh(cached: dict[str, Any] | None, today: date) -> bool:
    if cached is None or int(cached.get("sample_size") or 0) < 2:
        return True
    source_date = cached.get("source_date")
    try:
        resolved_date = date.fromisoformat(str(source_date))
    except (TypeError, ValueError):
        return True
    return today - resolved_date >= INDUSTRY_MAPPING_TTL


def _resolve_industries(
    connection: sqlite3.Connection,
    securities: list[Any],
    quotes: dict[str, Any],
    finances: dict[str, Any],
    workers: int,
    timeout: float,
) -> dict[int, str]:
    cached_mapping = _load_industry_map(connection)
    mapping = {raw: str(value["industry_name"]) for raw, value in cached_mapping.items()}
    representatives: dict[int, list[str]] = {}
    fallback_representatives: dict[int, list[str]] = {}
    security_by_code = {item.full_code: item for item in securities}

    def add_representative(target: dict[int, list[str]], raw: int, full_code: str) -> None:
        codes = target.setdefault(raw, [])
        if full_code not in codes and len(codes) < INDUSTRY_REPRESENTATIVE_COUNT:
            codes.append(full_code)

    for full_code, finance in finances.items():
        raw = int(finance.industry_raw)
        add_representative(fallback_representatives, raw, full_code)
        security = security_by_code.get(full_code)
        quote = quotes.get(full_code)
        if (
            security is not None
            and quote is not None
            and quote.last_price > 0
            and not _is_st_name(security.name)
            and finance.ipo_date is not None
        ):
            add_representative(representatives, raw, full_code)

    today = date.today()
    refresh_raws = sorted(
        raw
        for raw in fallback_representatives
        if _industry_mapping_needs_refresh(cached_mapping.get(raw), today)
    )
    if not refresh_raws:
        return mapping

    print(f"行业映射待校验 {len(refresh_raws)} 类，使用最多3只F10代表股交叉确认", flush=True)

    def resolve(raw: int) -> tuple[int, str, list[str], int, int]:
        codes = representatives.get(raw) or fallback_representatives[raw]
        resolved: list[tuple[str, str]] = []
        f10 = F10Client(timeout=timeout)
        for code in codes:
            try:
                name = _industry_name(f10, code)
            except Exception:
                name = None
            if name:
                resolved.append((code, name))

        if not resolved:
            existing = cached_mapping.get(raw)
            return raw, str(existing["industry_name"]) if existing else f"行业{raw}", [], 0, 0

        counts = Counter(name for _, name in resolved)
        name, agreement_count = counts.most_common(1)[0]
        existing = cached_mapping.get(raw)
        if agreement_count == 1 and len(resolved) > 1 and existing:
            existing_name = str(existing["industry_name"])
            if existing_name in counts:
                name = existing_name
                agreement_count = counts[existing_name]
        return raw, name, [code for code, _ in resolved], len(resolved), agreement_count

    now_text = datetime.now().astimezone().isoformat(timespec="seconds")
    with ThreadPoolExecutor(max_workers=min(max(1, workers), 8)) as executor:
        futures = [executor.submit(resolve, raw) for raw in refresh_raws]
        for future in as_completed(futures):
            raw, name, source_codes, sample_size, agreement_count = future.result()
            mapping[raw] = name
            if sample_size == 0:
                continue
            connection.execute(
                """
                INSERT INTO industry_map(
                    industry_raw, industry_name, source_code, source_date,
                    sample_size, agreement_count, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(industry_raw) DO UPDATE SET
                    industry_name=excluded.industry_name,
                    source_code=excluded.source_code,
                    source_date=excluded.source_date,
                    sample_size=excluded.sample_size,
                    agreement_count=excluded.agreement_count,
                    updated_at=excluded.updated_at
                """,
                (
                    raw,
                    name,
                    ",".join(source_codes),
                    today.isoformat(),
                    sample_size,
                    agreement_count,
                    now_text,
                ),
            )
    connection.commit()
    return mapping


def run_scan(
    db_path: Path,
    *,
    trade_date: str | None,
    workers: int,
    timeout: float,
    tdx_host: str | None,
) -> ScanResult:
    started = datetime.now().astimezone()
    selected_date = trade_date or started.date().isoformat()
    stage = _capture_stage(started)
    captured_at = started.isoformat(timespec="seconds")
    connection = _connect_db(db_path)
    cursor = connection.execute(
        """
        INSERT INTO scan_runs(trade_date, captured_at, capture_stage, status, note)
        VALUES (?, ?, ?, 'running', ?)
        """,
        (selected_date, captured_at, stage, "沪深A股全量代码表→批量行情→批量财务→F10行业映射"),
    )
    run_id = int(cursor.lastrowid)
    connection.commit()

    try:
        with TdxClient(
            host=tdx_host,
            timeout=timeout,
            pool_size=max(2, min(workers, 12)),
            heartbeat_interval=None,
        ) as client:
            securities = [
                item
                for market in ("sh", "sz")
                for item in client.get_codes_all(market, refresh=True)
                if item.category == "a_share"
            ]
            securities.sort(key=lambda item: item.full_code)
            codes = [item.full_code for item in securities]
            print(f"沪深A股母池 {len(codes)} 只，阶段：{stage}", flush=True)
            quotes, quote_errors = _fetch_quote_batches(client, codes, workers)
            finances, finance_errors = _fetch_finance_batches(client, codes, workers)

        industries = _resolve_industries(
            connection,
            securities,
            quotes,
            finances,
            workers,
            timeout,
        )
        now_text = datetime.now().astimezone().isoformat(timespec="seconds")

        security_rows: list[tuple[Any, ...]] = []
        snapshot_rows: list[tuple[Any, ...]] = []
        valid_quote_count = 0

        for security in securities:
            full_code = security.full_code
            quote = quotes.get(full_code)
            finance = finances.get(full_code)
            industry_raw = int(finance.industry_raw) if finance is not None else None
            industry_name = industries.get(industry_raw, "未分类") if industry_raw is not None else "未分类"
            security_rows.append(
                (
                    full_code,
                    security.exchange,
                    security.code,
                    security.name,
                    security.board,
                    security.category,
                    industry_raw,
                    industry_name,
                    int(finance.province_raw) if finance is not None else None,
                    _date_text(finance.ipo_date) if finance is not None else None,
                    _date_text(finance.updated_date) if finance is not None else None,
                    int(_is_st_name(security.name)),
                    now_text,
                )
            )

            last_price = _finite(quote.last_price) if quote is not None else None
            pre_close = _finite(quote.pre_close_price) if quote is not None else None
            quote_valid = bool(last_price and last_price > 0 and pre_close and pre_close > 0)
            if quote_valid:
                valid_quote_count += 1
            quality: list[str] = []
            if quote is None:
                quality.append("quote_missing")
            elif not quote_valid:
                quality.append("inactive_or_unlisted")
            if finance is None:
                quality.append("finance_missing")
            if not quality:
                quality.append("ok")

            change_pct = ((last_price / pre_close - 1.0) * 100.0) if quote_valid else None
            circulating_shares = _finite(finance.circulating_shares) if finance is not None else None
            total_shares = _finite(finance.total_shares) if finance is not None else None
            circulating_cap = (
                last_price * circulating_shares
                if quote_valid and circulating_shares and circulating_shares > 0
                else None
            )
            total_cap = last_price * total_shares if quote_valid and total_shares and total_shares > 0 else None
            volume_hand = _finite(quote.total_hand) if quote is not None else None
            turnover_rate = (
                volume_hand * 10000.0 / circulating_shares
                if volume_hand is not None and circulating_shares and circulating_shares > 0
                else None
            )

            snapshot_rows.append(
                (
                    run_id,
                    full_code,
                    int(quote.time_raw) if quote is not None else None,
                    last_price,
                    pre_close,
                    _finite(quote.open_price) if quote is not None else None,
                    _finite(quote.high_price) if quote is not None else None,
                    _finite(quote.low_price) if quote is not None else None,
                    change_pct,
                    volume_hand,
                    _finite(quote.amount) if quote is not None else None,
                    _finite(quote.open_amount_yuan) if quote is not None else None,
                    _finite(quote.inside_dish) if quote is not None else None,
                    _finite(quote.outer_disc) if quote is not None else None,
                    circulating_shares,
                    total_shares,
                    circulating_cap,
                    total_cap,
                    turnover_rate,
                    _finite(finance.eps_raw) if finance is not None else None,
                    _finite(finance.net_profit_yuan) if finance is not None else None,
                    _finite(finance.jing_ying_xian_jin_liu_raw_float * 1000.0) if finance is not None else None,
                    int(quote_valid),
                    ",".join(quality),
                )
            )

        with connection:
            connection.executemany(
                """
                INSERT INTO securities(
                    full_code, exchange, code, name, board, category,
                    industry_raw, industry_name, province_raw, ipo_date,
                    finance_updated_date, is_st, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(full_code) DO UPDATE SET
                    exchange=excluded.exchange,
                    code=excluded.code,
                    name=excluded.name,
                    board=excluded.board,
                    category=excluded.category,
                    industry_raw=excluded.industry_raw,
                    industry_name=excluded.industry_name,
                    province_raw=excluded.province_raw,
                    ipo_date=excluded.ipo_date,
                    finance_updated_date=excluded.finance_updated_date,
                    is_st=excluded.is_st,
                    updated_at=excluded.updated_at
                """,
                security_rows,
            )
            connection.executemany(
                """
                INSERT INTO market_snapshots(
                    run_id, full_code, quote_time_raw, last_price, pre_close_price,
                    open_price, high_price, low_price, change_pct, volume_hand,
                    amount, open_amount_yuan, inside_volume_hand, outside_volume_hand,
                    circulating_shares, total_shares, circulating_market_cap,
                    total_market_cap, turnover_rate, eps, net_profit_yuan,
                    operating_cash_flow_yuan, quote_valid, data_quality
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                snapshot_rows,
            )
            failed_batches = len(quote_errors) + len(finance_errors)
            connection.execute(
                """
                UPDATE scan_runs SET
                    completed_at=?, status='complete', universe_count=?, quoted_count=?,
                    valid_quote_count=?, finance_count=?, industry_count=?, failed_batches=?, error=?
                WHERE id=?
                """,
                (
                    now_text,
                    len(securities),
                    len(quotes),
                    valid_quote_count,
                    len(finances),
                    len({name for name in industries.values()}),
                    failed_batches,
                    "\n".join(quote_errors + finance_errors) or None,
                    run_id,
                ),
            )

        return ScanResult(
            run_id=run_id,
            trade_date=selected_date,
            captured_at=captured_at,
            capture_stage=stage,
            universe_count=len(securities),
            quoted_count=len(quotes),
            valid_quote_count=valid_quote_count,
            finance_count=len(finances),
            industry_count=len({name for name in industries.values()}),
            failed_batches=len(quote_errors) + len(finance_errors),
        )
    except Exception as exc:
        with connection:
            connection.execute(
                "UPDATE scan_runs SET completed_at=?, status='failed', error=? WHERE id=?",
                (datetime.now().astimezone().isoformat(timespec="seconds"), str(exc), run_id),
            )
        raise
    finally:
        connection.close()


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _latest_complete_run(connection: sqlite3.Connection) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM scan_runs WHERE status='complete' ORDER BY captured_at DESC, id DESC LIMIT 1"
    ).fetchone()


def _get_run(connection: sqlite3.Connection, run_id: int | None) -> sqlite3.Row | None:
    if run_id is None:
        return _latest_complete_run(connection)
    return connection.execute(
        "SELECT * FROM scan_runs WHERE id=? AND status='complete'",
        (run_id,),
    ).fetchone()


def _summary(connection: sqlite3.Connection, run_id: int) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN m.quote_valid=1 THEN 1 ELSE 0 END) AS valid,
            SUM(CASE WHEN m.quote_valid=1 AND m.change_pct>0.005 THEN 1 ELSE 0 END) AS rising,
            SUM(CASE WHEN m.quote_valid=1 AND m.change_pct<-0.005 THEN 1 ELSE 0 END) AS falling,
            SUM(CASE WHEN m.quote_valid=1 AND ABS(m.change_pct)<=0.005 THEN 1 ELSE 0 END) AS flat,
            SUM(CASE WHEN s.is_st=1 THEN 1 ELSE 0 END) AS st_count,
            SUM(CASE WHEN m.quote_valid=1 THEN COALESCE(m.amount, 0) ELSE 0 END) AS total_amount,
            COUNT(DISTINCT CASE WHEN m.quote_valid=1 THEN s.industry_name END) AS industries
        FROM market_snapshots m
        JOIN securities s ON s.full_code=m.full_code
        WHERE m.run_id=?
        """,
        (run_id,),
    ).fetchone()
    return _row_dict(row)


def print_summary(db_path: Path, run_id: int | None) -> None:
    with _connect_db(db_path) as connection:
        run = _get_run(connection, run_id)
        if run is None:
            raise SystemExit("没有可用扫描批次")
        print(json.dumps({"run": _row_dict(run), "summary": _summary(connection, int(run["id"]))}, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="沪深A股全量快照与SQLite热力图")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="执行一次全市场基数扫描")
    scan_parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    scan_parser.add_argument("--trade-date", help="归档交易日，默认本地当天")
    scan_parser.add_argument("--workers", type=int, default=8)
    scan_parser.add_argument("--timeout", type=float, default=12.0)
    scan_parser.add_argument("--tdx-host", help="可选的7709服务器地址")

    summary_parser = subparsers.add_parser("summary", help="输出扫描摘要")
    summary_parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    summary_parser.add_argument("--run-id", type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "scan":
        result = run_scan(
            args.db,
            trade_date=args.trade_date,
            workers=max(1, min(args.workers, 16)),
            timeout=max(1.0, min(args.timeout, 120.0)),
            tdx_host=args.tdx_host,
        )
        print(json.dumps({"status": "complete", **asdict(result)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "summary":
        print_summary(args.db, args.run_id)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
