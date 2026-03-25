import { NextResponse } from "next/server";

import { approvalDecisionSchema } from "@/lib/schemas";

import { runRepository } from "@/server/repositories/run-repository";

export const runtime = "nodejs";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const body = approvalDecisionSchema.parse(await request.json());
  const approval = await runRepository.resolveApprovalRequest(id, {
    status: "rejected",
    resolvedAt: new Date(),
    resolutionNote: body.note,
  });

  await runRepository.updateRun(approval.runId, {
    status: "failed",
    finishedAt: new Date(),
  });

  return NextResponse.json({ approval });
}
