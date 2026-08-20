#!/usr/bin/env python3
"""Project MCP entry that adds deterministic A-share market ranking tools."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from eltdx import TdxClient
from eltdx.mcp import create_mcp_server
from eltdx.serialization import to_jsonable


ALLOWED_SORTS = {
    "代码",
    "现价",
    "成交额",
    "涨幅",
    "封单额",
    "开盘金额",
    "涨速",
    "短换手",
    "量涨速",
    "开盘抢筹",
    "2分钟金额",
    "开盘涨幅",
    "最高涨幅",
    "最低涨幅",
    "回撤",
    "攻击",
}

FULL_CODE_RE = re.compile(r"^(sh|sz)\d{6}$")


def _record_full_code(record: dict[str, Any]) -> str | None:
    exchange = str(record.get("exchange") or "").lower()
    if exchange not in {"sh", "sz"}:
        market_id = record.get("market_id")
        exchange = "sz" if market_id == 0 else "sh" if market_id == 1 else ""
    code = str(record.get("code") or "")
    full_code = f"{exchange}{code}"
    return full_code if FULL_CODE_RE.fullmatch(full_code) else None


def _filter_rank_payload(payload: dict[str, Any], count: int) -> dict[str, Any]:
    """Keep only unique Shanghai/Shenzhen A-share rows in server order."""

    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("market rank response is missing records")

    eligible: list[dict[str, Any]] = []
    seen: set[str] = set()
    rejected_count = 0
    for value in records:
        if not isinstance(value, dict):
            rejected_count += 1
            continue
        full_code = _record_full_code(value)
        if full_code is None or full_code in seen:
            rejected_count += 1
            continue
        seen.add(full_code)
        row = dict(value)
        row["full_code"] = full_code
        eligible.append(row)

    result = dict(payload)
    result.pop("raw_payload", None)
    result["records"] = eligible[:count]
    result["returned_count"] = min(len(eligible), count)
    result["filtered_out_count"] = rejected_count
    result["truncated_count"] = max(0, len(eligible) - count)
    return result


def _normalize_top20_codes(codes: list[str]) -> list[str]:
    if not isinstance(codes, list) or not 1 <= len(codes) <= 20:
        raise ValueError("codes must contain between 1 and 20 Shanghai/Shenzhen full codes")

    normalized: list[str] = []
    seen: set[str] = set()
    for value in codes:
        if not isinstance(value, str):
            raise TypeError("each code must be a string")
        code = value.strip().lower()
        if not FULL_CODE_RE.fullmatch(code):
            raise ValueError("each code must match sh600000 or sz000001")
        if code not in seen:
            normalized.append(code)
            seen.add(code)
    return normalized


def market_rank(
    sort_by: str = "开盘抢筹",
    start: int = 0,
    count: int = 80,
    ascending: bool = False,
    timeout: float = 8.0,
    host: str | None = None,
) -> dict[str, Any]:
    """Return one server-sorted Shanghai/Shenzhen A-share market page."""

    if sort_by not in ALLOWED_SORTS:
        raise ValueError("sort_by must be one of: " + ", ".join(sorted(ALLOWED_SORTS)))
    if isinstance(start, bool) or not isinstance(start, int) or not 0 <= start <= 65_535:
        raise ValueError("start must be an integer between 0 and 65535")
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 200:
        raise ValueError("count must be an integer between 1 and 200")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < float(timeout) <= 120:
        raise ValueError("timeout must be greater than 0 and no more than 120 seconds")
    if host is not None and not isinstance(host, str):
        raise TypeError("host must be a string or None")

    fetch_count = min(200, count + max(20, count // 2))
    with TdxClient(host=host, timeout=float(timeout), heartbeat_interval=None) as client:
        page = client.quotes.list_by_category(
            "沪深A股",
            sort_by=sort_by,
            start=start,
            count=fetch_count,
            ascending=ascending,
        )

    payload = _filter_rank_payload(to_jsonable(page), count)
    payload["scope"] = "沪深A股"
    payload["sort_by"] = sort_by
    payload["requested_count"] = count
    payload["server_requested_count"] = fetch_count
    payload["note"] = "服务端分类行情排序已在输出端强制保留沪深代码；仍须做流动性、状态、竞价、题材和风险复核。"
    return payload


def refresh_top20(
    codes: list[str],
    timeout: float = 8.0,
    host: str | None = None,
) -> dict[str, Any]:
    """Refresh one frozen top-20 candidate list in a separate real-time quote batch."""

    normalized = _normalize_top20_codes(codes)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < float(timeout) <= 120:
        raise ValueError("timeout must be greater than 0 and no more than 120 seconds")
    if host is not None and not isinstance(host, str):
        raise TypeError("host must be a string or None")

    requested_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with TdxClient(host=host, timeout=float(timeout), heartbeat_interval=None) as client:
        snapshots = list(client.quotes.get_snapshots(normalized) or [])
    retrieved_at = datetime.now().astimezone().isoformat(timespec="seconds")

    raw_records = to_jsonable(snapshots)
    if not isinstance(raw_records, list):
        raise ValueError("real-time quote response is not a record list")

    requested = set(normalized)
    records: list[dict[str, Any]] = []
    returned: set[str] = set()
    for value in raw_records:
        if not isinstance(value, dict):
            continue
        full_code = _record_full_code(value)
        if full_code is None or full_code not in requested or full_code in returned:
            continue
        row = dict(value)
        row["full_code"] = full_code
        records.append(row)
        returned.add(full_code)

    records.sort(key=lambda row: normalized.index(str(row["full_code"])))
    return {
        "requested_at": requested_at,
        "retrieved_at": retrieved_at,
        "requested_codes": normalized,
        "returned_count": len(records),
        "missing_codes": [code for code in normalized if code not in returned],
        "records": records,
        "note": "这是候选榜单冻结后的独立实时行情批次；后续过滤与排序只能使用本批次价格字段。",
    }


def create_server():
    """Create the stock-screening MCP server with eltdx tools plus market ranking."""

    base = create_mcp_server()
    base.tool(name="eltdx_market_rank")(market_rank)
    base.tool(name="eltdx_refresh_top20")(refresh_top20)
    return base


def main() -> int:
    create_server().run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
