import { NextResponse } from "next/server";

import { db } from "@/lib/db";
import { getEnv } from "@/lib/env";
import { getProviderReadiness } from "@/server/services/provider-readiness";

export const runtime = "nodejs";

export async function GET() {
  const env = getEnv();
  const runCount = await db.run.count();
  const providerReadiness = await getProviderReadiness();

  return NextResponse.json({
    ok: true,
    time: new Date().toISOString(),
    openaiConfigured: Boolean(env.OPENAI_API_KEY),
    plannerProvider: env.OPERATOR_PLANNER_PROVIDER,
    providerReadiness,
    runCount,
  });
}
