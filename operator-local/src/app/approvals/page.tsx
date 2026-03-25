import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { ApprovalActions } from "@/components/approval-actions";
import { RunStatusPill } from "@/components/run-status-pill";
import { SectionCard } from "@/components/section-card";
import { formatDateTime, truncate } from "@/lib/utils";
import { runRepository } from "@/server/repositories/run-repository";

export const revalidate = 0;

export default async function ApprovalsPage() {
  const approvals = await runRepository.listPendingApprovals();

  return (
    <AppShell currentPath="/approvals">
      <SectionCard eyebrow="Review" title="Pending approvals">
        <div className="space-y-4">
          {approvals.length ? (
            approvals.map((approval) => (
              <div key={approval.id} className="rounded-[1.4rem] border border-amber-200 bg-amber-50 p-5">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-amber-950">{approval.reason}</p>
                    <p className="text-xs text-amber-700">{formatDateTime(approval.requestedAt)}</p>
                  </div>
                  <RunStatusPill status={approval.run.status} />
                </div>
                <p className="mb-3 text-sm text-amber-900">{truncate(approval.run.goal, 150)}</p>
                <pre className="mb-4 overflow-x-auto rounded-[1rem] bg-white/80 p-3 text-xs text-amber-950">
                  {JSON.stringify(approval.actionPayload, null, 2)}
                </pre>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <Link href={`/runs/${approval.runId}`} className="text-sm font-medium text-amber-900 underline">
                    Open run detail
                  </Link>
                  <ApprovalActions approvalId={approval.id} />
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-600">No approvals are currently waiting on you.</p>
          )}
        </div>
      </SectionCard>
    </AppShell>
  );
}
