import zza50SeedSnapshot from "@/lib/data/market-constituents-zza50-seed.json";

const eastmoneyConstituentUrl = "https://datacenter.eastmoney.com/api/data/v1/get";
const constituentCacheMs = 24 * 60 * 60 * 1000;

const eastmoneyRequestHeaders = {
  Referer: "https://data.eastmoney.com/other/index/",
  "User-Agent": "Mozilla/5.0 (compatible; AShareHeatmap/1.0)",
  Accept: "application/json, text/plain, */*",
};

type Zza50SeedSnapshot = {
  market: "zza50";
  source: string;
  updatedAt: string;
  count: number;
  constituents: Array<{
    code: string;
    name: string;
  }>;
};

type EastmoneyConstituentRow = {
  SECUCODE?: string;
  SECURITY_NAME_ABBR?: string;
};

type EastmoneyConstituentResponse = {
  result?: {
    data?: EastmoneyConstituentRow[];
  };
};

export type Zza50ConstituentSnapshot = {
  market: "zza50";
  codes: string[];
  count: number;
  updatedAt: string;
  expiresAt: string;
  source: string;
  isSeed: boolean;
  stale: boolean;
};

export type Zza50ConstituentStatus = Zza50ConstituentSnapshot & {
  refreshError?: string;
};

const seedSnapshot = zza50SeedSnapshot as Zza50SeedSnapshot;

let zza50SnapshotCache: Zza50ConstituentSnapshot | null = createSeedSnapshot();
let zza50RefreshPromise: Promise<Zza50ConstituentSnapshot> | null = null;

function normalizeSecucode(value: string) {
  const match = value.trim().toUpperCase().match(/^(\d{6})\.(SH|SZ|BJ)$/);
  if (!match) {
    return null;
  }

  return `${match[1]}.${match[2]}`;
}

function dedupeCodes(codes: string[]) {
  return [...new Set(codes)];
}

function buildSnapshot(
  codes: string[],
  options: {
    updatedAt: string;
    source: string;
    isSeed: boolean;
    stale?: boolean;
    now?: number;
  }
): Zza50ConstituentSnapshot {
  const now = options.now ?? Date.now();
  const uniqueCodes = dedupeCodes(codes);

  return {
    market: "zza50",
    codes: uniqueCodes,
    count: uniqueCodes.length,
    updatedAt: options.updatedAt,
    expiresAt: new Date(now + constituentCacheMs).toISOString(),
    source: options.source,
    isSeed: options.isSeed,
    stale: options.stale ?? false,
  };
}

function createSeedSnapshot() {
  const snapshot = buildSnapshot(
    seedSnapshot.constituents.map((item) => item.code).filter((code): code is string => Boolean(normalizeSecucode(code))),
    {
      updatedAt: seedSnapshot.updatedAt,
      source: `${seedSnapshot.source}:seed`,
      isSeed: true,
      stale: true,
      now: 0,
    }
  );

  return {
    ...snapshot,
    expiresAt: new Date(0).toISOString(),
  };
}

function isSnapshotExpired(snapshot: Pick<Zza50ConstituentSnapshot, "expiresAt">, now = Date.now()) {
  return Number.isNaN(Date.parse(snapshot.expiresAt)) || Date.parse(snapshot.expiresAt) <= now;
}

function filterAllowedCodes(codes: string[], allowedCodes?: Set<string>) {
  if (!allowedCodes) {
    return codes;
  }

  return codes.filter((code) => allowedCodes.has(code));
}

function projectSnapshot(snapshot: Zza50ConstituentSnapshot, allowedCodes?: Set<string>): Zza50ConstituentSnapshot {
  const codes = filterAllowedCodes(snapshot.codes, allowedCodes);

  return {
    ...snapshot,
    codes,
    count: codes.length,
  };
}

async function fetchRemoteZza50Snapshot() {
  const params = new URLSearchParams({
    reportName: "RPT_INDEX_TS_COMPONENT",
    columns: "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,TYPE",
    quoteColumns: "f2,f3",
    quoteType: "0",
    source: "WEB",
    client: "WEB",
    filter: '(TYPE="5")',
    pageNumber: "1",
    pageSize: "200",
    sortColumns: "SECURITY_CODE",
    sortTypes: "-1",
  });
  const response = await fetch(`${eastmoneyConstituentUrl}?${params.toString()}`, {
    headers: eastmoneyRequestHeaders,
    next: { revalidate: 0 },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Eastmoney constituent request failed: ${response.status}`);
  }

  const payload = (await response.json()) as EastmoneyConstituentResponse;
  const rows = Array.isArray(payload.result?.data) ? payload.result.data : [];
  const codes = dedupeCodes(
    rows
      .map((row) => normalizeSecucode(String(row.SECUCODE ?? "")))
      .filter((code): code is string => Boolean(code))
  );

  if (codes.length < 40) {
    throw new Error(`Eastmoney constituent snapshot incomplete: ${codes.length}`);
  }

  return buildSnapshot(codes, {
    updatedAt: new Date().toISOString(),
    source: "eastmoney-datacenter:RPT_INDEX_TS_COMPONENT:TYPE=5",
    isSeed: false,
    stale: false,
  });
}

export async function refreshZza50ConstituentSnapshot(allowedCodes?: Set<string>) {
  if (!zza50RefreshPromise) {
    zza50RefreshPromise = fetchRemoteZza50Snapshot()
      .then((snapshot) => {
        zza50SnapshotCache = snapshot;
        return snapshot;
      })
      .finally(() => {
        zza50RefreshPromise = null;
      });
  }

  const snapshot = await zza50RefreshPromise;
  return projectSnapshot(snapshot, allowedCodes);
}

export async function getZza50ConstituentSnapshot(options?: {
  forceRefresh?: boolean;
  allowedCodes?: Set<string>;
}) {
  const forceRefresh = options?.forceRefresh ?? false;
  const allowedCodes = options?.allowedCodes;
  const cachedSnapshot = zza50SnapshotCache ?? createSeedSnapshot();

  if (!forceRefresh && !isSnapshotExpired(cachedSnapshot)) {
    return projectSnapshot(cachedSnapshot, allowedCodes);
  }

  try {
    return await refreshZza50ConstituentSnapshot(allowedCodes);
  } catch {
    const fallbackSnapshot = buildSnapshot(projectSnapshot(cachedSnapshot, allowedCodes).codes, {
      updatedAt: cachedSnapshot.updatedAt,
      source: cachedSnapshot.source,
      isSeed: cachedSnapshot.isSeed,
      stale: true,
    });
    zza50SnapshotCache = fallbackSnapshot;
    return {
      ...fallbackSnapshot,
      stale: true,
    };
  }
}

export async function getZza50ConstituentStatus(options?: {
  forceRefresh?: boolean;
  allowedCodes?: Set<string>;
}): Promise<Zza50ConstituentStatus> {
  const allowedCodes = options?.allowedCodes;
  let refreshError: string | undefined;

  if (options?.forceRefresh) {
    try {
      await refreshZza50ConstituentSnapshot(allowedCodes);
    } catch (error) {
      refreshError = error instanceof Error ? error.message : "Failed to refresh constituents";
    }
  }

  const snapshot = await getZza50ConstituentSnapshot({ allowedCodes });

  return {
    ...snapshot,
    refreshError,
  };
}
