import { NextResponse } from "next/server";

import { approvalDecisionSchema } from "@/lib/schemas";

import { runRepository } from "@/server/repositories/run-repository";

export const runtime = "nodejs";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const body = approvalDecisionSchema.parse(await request.json());
  const approval = await runRepository.resolveApprovalRequest(id, {
    status: "approved",
    resolvedAt: new Date(),
    resolutionNote: body.note,
  });

  await runRepository.updateRun(approval.runId, {
    status: "queued",
    lastHeartbeatAt: new Date(),
  });

  return NextResponse.json({ approval });
}
