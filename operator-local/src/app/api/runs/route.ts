import { NextResponse } from "next/server";

import { createRunSchema } from "@/lib/schemas";

import { createRun, listRuns } from "@/server/services/run-service";

export const runtime = "nodejs";

export async function GET() {
  const runs = await listRuns();
  return NextResponse.json({ runs });
}

export async function POST(request: Request) {
  const json = await request.json();
  const input = createRunSchema.parse(json);
  const run = await createRun(input.prompt, input.workflowMode);

  return NextResponse.json({ run });
}
