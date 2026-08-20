# 本地 eltdx 验证

本项目使用隔离环境 `.venv-eltdx`，不要调用系统自带的 Python 3.9。

## 依赖检查

```bash
.venv-eltdx/bin/python --version
.venv-eltdx/bin/python -m pip check
```

## 通达信 7709 行情直连

```bash
.venv-eltdx/bin/eltdx-smoke --timeout 6 --no-heartbeat --code sh600519
```

## 通达信 TQLEX / F10

```bash
.venv-eltdx/bin/eltdx-f10-smoke --code 600519 --timeout 10
```

## MCP 协议与真实工具调用

```bash
.venv-eltdx/bin/python tests/eltdx_mcp_probe.py
```

探针会执行 MCP `initialize`、`tools/list`，然后实际调用行情工具
`eltdx_quote` 和 F10 工具 `eltdx_company_profile`。网络受限的沙箱内可能出现
`unable to connect to any 7709 host`；需允许该进程访问外部行情服务器。

## MCP 启动命令

基础 `eltdx-mcp` 不包含项目扩展的排行榜与前20实时刷新工具。股票筛选客户端应使用项目入口：

```text
/Users/wucong/个人/GP/gup/.venv-eltdx/bin/python /Users/wucong/个人/GP/gup/stock-screener/scripts/eltdx_market_mcp.py
```

该服务使用 stdio，不监听 HTTP 端口，并额外提供 `eltdx_market_rank` 与 `eltdx_refresh_top20`。后者只接受1至20个沪深完整代码，用于榜单预排序后的独立实时行情批次。

## 本地纯单元测试

```bash
.venv-eltdx/bin/python -m unittest tests.test_eltdx_market_helpers tests.test_market_heatmap_helpers
```
