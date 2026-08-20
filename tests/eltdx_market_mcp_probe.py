"""Protocol probe for the project eltdx market-scanner MCP entry."""

from __future__ import annotations

from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER = PROJECT_ROOT / "stock-screener" / "scripts" / "eltdx_market_mcp.py"


async def main() -> None:
    params = StdioServerParameters(
        command=str(PROJECT_ROOT / ".venv-eltdx" / "bin" / "python"),
        args=[str(SERVER)],
        cwd=str(PROJECT_ROOT),
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialized = await session.initialize()
            listed = await session.list_tools()
            ranked = await session.call_tool(
                "eltdx_market_rank",
                {"sort_by": "开盘抢筹", "count": 10, "timeout": 8},
                read_timeout_seconds=15,
            )
            refreshed = await session.call_tool(
                "eltdx_refresh_top20",
                {"codes": ["sh600519", "sz000001"], "timeout": 8},
                read_timeout_seconds=15,
            )

    names = {tool.name for tool in listed.tools}
    print(f"server={initialized.server_info.name} version={initialized.server_info.version}")
    print(
        f"tools={len(names)} market_rank={'eltdx_market_rank' in names} "
        f"refresh_top20={'eltdx_refresh_top20' in names}"
    )
    print(f"rank_is_error={ranked.is_error} rank_blocks={len(ranked.content)}")
    print(f"refresh_is_error={refreshed.is_error} refresh_blocks={len(refreshed.content)}")
    if "eltdx_market_rank" not in names:
        raise SystemExit("missing eltdx_market_rank")
    if "eltdx_refresh_top20" not in names:
        raise SystemExit("missing eltdx_refresh_top20")
    if ranked.is_error or not ranked.content:
        raise SystemExit("eltdx_market_rank call failed")
    if refreshed.is_error or not refreshed.content:
        raise SystemExit("eltdx_refresh_top20 call failed")


if __name__ == "__main__":
    anyio.run(main)
