import { NextRequest, NextResponse } from "next/server";

import { getMarketConstituentStatus, isMarketKey } from "@/lib/market-heatmap";

export const maxDuration = 60;

export async function GET(request: NextRequest) {
  const marketParam = request.nextUrl.searchParams.get("market") ?? "zza50";
  const refreshParam = request.nextUrl.searchParams.get("refresh");
  const forceRefresh = refreshParam === "1" || refreshParam === "true";

  if (!isMarketKey(marketParam)) {
    return NextResponse.json(
      {
        success: false,
        message: `Invalid market: ${marketParam}`,
      },
      { status: 400 }
    );
  }

  try {
    const status = await getMarketConstituentStatus({
      market: marketParam,
      forceRefresh,
    });

    if (!status) {
      return NextResponse.json(
        {
          success: false,
          message: `No constituent status available for market: ${marketParam}`,
        },
        { status: 404 }
      );
    }

    const response = NextResponse.json({
      success: true,
      ...status,
    });
    response.headers.set("Cache-Control", "public, s-maxage=10, stale-while-revalidate=30");
    return response;
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        message: error instanceof Error ? error.message : "Failed to load constituent status",
      },
      { status: 502 }
    );
  }
}
