import { NextResponse } from "next/server";

import { db } from "@/lib/db";
import { getEnv } from "@/lib/env";

export const runtime = "nodejs";

export async function GET() {
  const env = getEnv();
  const runCount = await db.run.count();

  return NextResponse.json({
    ok: true,
    time: new Date().toISOString(),
    openaiConfigured: Boolean(env.OPENAI_API_KEY),
    runCount,
  });
}
