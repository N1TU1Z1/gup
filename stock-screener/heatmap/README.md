# 沪深 A 股本地热力图

基于 [wenyuanw/a-share-heatmap](https://github.com/wenyuanw/a-share-heatmap) 的 MIT 脚手架，数据层已替换为本地 `eltdx + SQLite`：先扫描沪深 A 股全量母池，再按行业、市值和当日涨跌绘制 Canvas 树图。

## 本地运行

要求：项目根目录已有 `.venv-eltdx`，Node.js 22+，pnpm 11+。

```bash
pnpm install
pnpm scan
pnpm dev
```

打开 <http://127.0.0.1:3000>。

生产方式：

```bash
pnpm build
pnpm start --hostname 127.0.0.1 --port 3000
```

## 数据归档

- 数据库：`../../data/market_heatmap.sqlite3`
- `scan_runs`：每次扫描的交易日、抓取时间、时段、覆盖数和失败批次
- `securities`：代码、名称、板块、行业、上市日与财务更新时间
- `market_snapshots`：行情、涨跌、成交额、股本、市值、换手和基础财务字段
- `industry_map`：通达信行业编号到中文行业名的本地缓存；每个编号最多使用3只有效代表股交叉校验，并保存样本数与一致数，30天后重新确认

每次 `pnpm scan` 都新增批次，不覆盖旧快照。页面读取最近一次完整批次；`pnpm scan:summary` 可查看最新覆盖统计。可用 `MARKET_HEATMAP_DB=/绝对路径/文件.sqlite3` 指定另一份复盘数据库。

当前版本只展示单日快照，不把单日数据冒充 5 日、20 日或年内区间；沪深 300、中证 A50/A500 也不会在缺少官方成分数据时用市值排名伪造。

## 验证

```bash
pnpm typecheck
pnpm build
```

原项目版权与许可见 [LICENSE](./LICENSE)。
