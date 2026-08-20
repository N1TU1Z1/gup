export const marketKeys = ["all", "sse", "szse", "hs300", "zza50", "zza500", "cyb", "kcb"] as const;
export type MarketKey = (typeof marketKeys)[number];

export const metricKeys = ["1", "2", "3", "4", "5", "6"] as const;
export type MetricKey = (typeof metricKeys)[number];

export const heatmapPeriodKeys = ["day", "week", "month", "year"] as const;
export type HeatmapPeriodKey = (typeof heatmapPeriodKeys)[number];

type MarketDataSource = "direct" | "fallback";
type ExchangeCode = "SH" | "SZ";

export type HeatmapStockNode = {
  code: string;
  name: string;
  boardName: string;
  subBoardName: string;
  value: number;
  exchange: ExchangeCode;
  price: number;
  changePct: number;
  turnoverAmount: number;
};

export type HeatmapBoardNode = {
  code: string;
  name: string;
  value: number;
  stockCount: number;
  children: HeatmapStockNode[];
};

export type TreemapResponse = {
  market: MarketKey;
  period: HeatmapPeriodKey;
  updatedAt: string;
  stockCount: number;
  boardCount: number;
  summary: {
    advanceCount: number;
    flatCount: number;
    declineCount: number;
    turnoverAmount: number;
    turnoverPreviousAmount: number;
    turnoverDelta: number;
    indexChangePct?: number;
  };
  nodes: HeatmapBoardNode[];
  source: MarketDataSource;
};

export type QuoteValue = {
  price: number;
  changePct: number;
  turnoverAmount: number;
};

export type QuotesResponse = {
  market: MarketKey;
  metric?: MetricKey;
  period: HeatmapPeriodKey;
  updatedAt: string;
  quotes: Record<string, QuoteValue>;
  source: MarketDataSource;
};

export type MarketOverviewItem = {
  market: MarketKey;
  changePct: number;
  stockCount: number;
  updatedAt: string;
};

export type MarketOverviewResponse = {
  period: HeatmapPeriodKey;
  updatedAt: string;
  markets: MarketOverviewItem[];
  source: MarketDataSource;
};

export function isMarketKey(value: string): value is MarketKey {
  return marketKeys.includes(value as MarketKey);
}

export function isMetricKey(value: string): value is MetricKey {
  return metricKeys.includes(value as MetricKey);
}

export function isHeatmapPeriodKey(value: string): value is HeatmapPeriodKey {
  return heatmapPeriodKeys.includes(value as HeatmapPeriodKey);
}

export function periodFromMetricKey(_metric: MetricKey): HeatmapPeriodKey {
  return "day";
}
