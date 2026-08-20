import { existsSync } from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import {
  marketKeys,
  type HeatmapBoardNode,
  type HeatmapPeriodKey,
  type HeatmapStockNode,
  type MarketKey,
  type MarketOverviewItem,
  type MarketOverviewResponse,
  type MetricKey,
  type QuotesResponse,
  type QuoteValue,
  type TreemapResponse,
} from "@/lib/market-heatmap-types";

export {
  heatmapPeriodKeys,
  isHeatmapPeriodKey,
  isMarketKey,
  isMetricKey,
  marketKeys,
  metricKeys,
  periodFromMetricKey,
  type HeatmapBoardNode,
  type HeatmapPeriodKey,
  type HeatmapStockNode,
  type MarketKey,
  type MarketOverviewItem,
  type MarketOverviewResponse,
  type MetricKey,
  type QuotesResponse,
  type QuoteValue,
  type TreemapResponse,
} from "@/lib/market-heatmap-types";

type RunRow = {
  id: number;
  captured_at: string;
};

type StockRow = {
  code: string;
  name: string;
  exchange: string;
  industry_name: string | null;
  last_price: number;
  change_pct: number;
  amount: number | null;
  circulating_market_cap: number | null;
  total_market_cap: number | null;
};

const flatThreshold = 0.1;

function databasePath() {
  const configured = process.env.MARKET_HEATMAP_DB?.trim();
  return configured
    ? path.resolve(configured)
    : path.resolve(process.cwd(), "..", "..", "data", "market_heatmap.sqlite3");
}

function openDatabase() {
  const target = databasePath();
  if (!existsSync(target)) {
    throw new Error(`未找到市场快照数据库：${target}。请先执行 pnpm scan。`);
  }
  return new DatabaseSync(target, { readOnly: true });
}

function latestRun(database: DatabaseSync): RunRow {
  const run = database
    .prepare(
      "SELECT id, captured_at FROM scan_runs WHERE status='complete' ORDER BY captured_at DESC, id DESC LIMIT 1"
    )
    .get() as RunRow | undefined;
  if (!run) {
    throw new Error("SQLite 中没有已完成的全市场扫描，请先执行 pnpm scan。");
  }
  return run;
}

function marketCondition(market: MarketKey) {
  if (market === "sse") return "s.full_code LIKE 'sh%'";
  if (market === "szse") return "s.full_code LIKE 'sz%'";
  if (market === "cyb") return "(s.code LIKE '300%' OR s.code LIKE '301%')";
  if (market === "kcb") return "(s.code LIKE '688%' OR s.code LIKE '689%')";
  if (market === "hs300" || market === "zza50" || market === "zza500") return "1=0";
  return "1=1";
}

function readStocks(database: DatabaseSync, runId: number, market: MarketKey): StockRow[] {
  return database
    .prepare(
      `
        SELECT
          s.code,
          s.name,
          UPPER(s.exchange) AS exchange,
          COALESCE(NULLIF(s.industry_name, ''), '未分类') AS industry_name,
          m.last_price,
          m.change_pct,
          m.amount,
          m.circulating_market_cap,
          m.total_market_cap
        FROM market_snapshots m
        JOIN securities s ON s.full_code=m.full_code
        WHERE m.run_id=? AND m.quote_valid=1 AND ${marketCondition(market)}
      `
    )
    .all(runId) as StockRow[];
}

function stockValue(stock: StockRow) {
  const cap = stock.circulating_market_cap ?? stock.total_market_cap ?? 0;
  if (Number.isFinite(cap) && cap > 0) return cap;
  const amount = stock.amount ?? 0;
  return Number.isFinite(amount) && amount > 0 ? amount : 1;
}

function boardCode(name: string) {
  let hash = 2166136261;
  for (let index = 0; index < name.length; index += 1) {
    hash ^= name.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `board-${(hash >>> 0).toString(16)}`;
}

function buildNodes(stocks: StockRow[]): HeatmapBoardNode[] {
  const grouped = new Map<string, HeatmapStockNode[]>();
  for (const stock of stocks) {
    const boardName = stock.industry_name || "未分类";
    const current = grouped.get(boardName) ?? [];
    current.push({
      code: stock.code,
      name: stock.name,
      boardName,
      subBoardName: boardName,
      value: stockValue(stock),
      exchange: stock.exchange === "SH" ? "SH" : "SZ",
      price: stock.last_price,
      changePct: stock.change_pct,
      turnoverAmount: stock.amount ?? 0,
    });
    grouped.set(boardName, current);
  }

  return Array.from(grouped.entries())
    .map(([name, children]) => {
      children.sort((left, right) => right.value - left.value);
      return {
        code: boardCode(name),
        name,
        value: children.reduce((sum, stock) => sum + stock.value, 0),
        stockCount: children.length,
        children,
      };
    })
    .sort((left, right) => right.value - left.value);
}

function summarize(stocks: StockRow[]) {
  let advanceCount = 0;
  let flatCount = 0;
  let declineCount = 0;
  let turnoverAmount = 0;
  let weightedChange = 0;
  let totalValue = 0;

  for (const stock of stocks) {
    if (stock.change_pct > flatThreshold) advanceCount += 1;
    else if (stock.change_pct < -flatThreshold) declineCount += 1;
    else flatCount += 1;

    turnoverAmount += stock.amount ?? 0;
    const value = stockValue(stock);
    weightedChange += value * stock.change_pct;
    totalValue += value;
  }

  return {
    advanceCount,
    flatCount,
    declineCount,
    turnoverAmount,
    turnoverPreviousAmount: 0,
    turnoverDelta: 0,
    indexChangePct: totalValue > 0 ? weightedChange / totalValue : 0,
  };
}

function assertDaily(period: HeatmapPeriodKey) {
  if (period !== "day") {
    throw new Error("本地 SQLite 当前保存单日快照，仅支持当日涨跌。");
  }
}

export async function getMarketConstituentStatus(_options?: {
  market?: MarketKey;
  forceRefresh?: boolean;
}): Promise<Record<string, unknown> | null> {
  return null;
}

export async function getTreemapData(
  market: MarketKey,
  period: HeatmapPeriodKey = "day"
): Promise<TreemapResponse> {
  assertDaily(period);
  const database = openDatabase();
  try {
    const run = latestRun(database);
    const stocks = readStocks(database, run.id, market);
    const nodes = buildNodes(stocks);
    return {
      market,
      period,
      updatedAt: run.captured_at,
      stockCount: stocks.length,
      boardCount: nodes.length,
      summary: summarize(stocks),
      nodes,
      source: "direct",
    };
  } finally {
    database.close();
  }
}

export async function getQuoteData(
  market: MarketKey,
  period: HeatmapPeriodKey = "day",
  metric?: MetricKey
): Promise<QuotesResponse> {
  assertDaily(period);
  const database = openDatabase();
  try {
    const run = latestRun(database);
    const quotes: Record<string, QuoteValue> = {};
    for (const stock of readStocks(database, run.id, market)) {
      quotes[stock.code] = {
        price: stock.last_price,
        changePct: stock.change_pct,
        turnoverAmount: stock.amount ?? 0,
      };
    }
    return {
      market,
      period,
      metric,
      updatedAt: run.captured_at,
      quotes,
      source: "direct",
    };
  } finally {
    database.close();
  }
}

export async function getOverviewData(
  period: HeatmapPeriodKey = "day"
): Promise<MarketOverviewResponse> {
  assertDaily(period);
  const database = openDatabase();
  try {
    const run = latestRun(database);
    const markets: MarketOverviewItem[] = [];
    for (const market of marketKeys) {
      const stocks = readStocks(database, run.id, market);
      markets.push({
        market,
        changePct: summarize(stocks).indexChangePct,
        stockCount: stocks.length,
        updatedAt: run.captured_at,
      });
    }
    return {
      period,
      updatedAt: run.captured_at,
      markets,
      source: "direct",
    };
  } finally {
    database.close();
  }
}
