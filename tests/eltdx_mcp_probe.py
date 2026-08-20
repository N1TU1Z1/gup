"""Protocol-level smoke probe for the local eltdx stdio MCP server."""

from __future__ import annotations

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client


EXPECTED_TOOLS = {
    "eltdx_quote",
    "eltdx_quote_depth",
    "eltdx_kline",
    "eltdx_minute",
    "eltdx_trades",
    "eltdx_call_auction",
    "eltdx_auction_0925",
    "eltdx_auction_data",
    "eltdx_stock_profile",
    "eltdx_shortline_indicators",
    "eltdx_stock_topics",
    "eltdx_topic_stocks",
    "eltdx_company_profile",
    "eltdx_hot_topics",
    "eltdx_finance_report",
    "eltdx_company_news",
    "eltdx_docs_index",
}


async def main() -> None:
    server = StdioServerParameters(command=".venv-eltdx/bin/eltdx-mcp")
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialized = await session.initialize()
            listed = await session.list_tools()
            quote = await session.call_tool(
                "eltdx_quote",
                {"codes": ["sh600519"], "timeout": 6},
                read_timeout_seconds=15,
            )
            f10 = await session.call_tool(
                "eltdx_company_profile",
                {"code": "600519", "timeout": 10},
                read_timeout_seconds=15,
            )

    names = {tool.name for tool in listed.tools}
    missing = EXPECTED_TOOLS - names
    print(f"server={initialized.server_info.name} version={initialized.server_info.version}")
    print(f"tools={len(names)}")
    print("tool_names=" + ",".join(sorted(names)))
    print(f"quote_is_error={quote.is_error} quote_blocks={len(quote.content)}")
    if quote.is_error:
        print("quote_error=" + " | ".join(str(block) for block in quote.content))
    print(f"f10_is_error={f10.is_error} f10_blocks={len(f10.content)}")
    if missing:
        raise SystemExit("missing_tools=" + ",".join(sorted(missing)))
    if quote.is_error or not quote.content:
        raise SystemExit("eltdx_quote call failed")
    if f10.is_error or not f10.content:
        raise SystemExit("eltdx_company_profile call failed")


if __name__ == "__main__":
    anyio.run(main)
