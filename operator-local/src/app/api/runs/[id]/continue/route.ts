import { NextResponse } from "next/server";

import { continueRun } from "@/server/agent/orchestrator";

export const runtime = "nodejs";

export async function POST(_: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  try {
    const run = await continueRun(id);

    return NextResponse.json({ run });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Run continuation failed.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
