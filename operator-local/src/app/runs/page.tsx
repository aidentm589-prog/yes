import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { RunStatusPill } from "@/components/run-status-pill";
import { SectionCard } from "@/components/section-card";
import { formatDateTime, truncate } from "@/lib/utils";
import { listRuns } from "@/server/services/run-service";

export const revalidate = 0;

export default async function RunsPage() {
  const runs = await listRuns();

  return (
    <AppShell currentPath="/runs">
      <SectionCard eyebrow="History" title="Run history">
        <div className="space-y-4">
          {runs.map((run) => (
            <Link
              key={run.id}
              href={`/runs/${run.id}`}
              className="grid gap-4 rounded-[1.4rem] border border-slate-200 bg-[#fcfbf6] px-5 py-5 transition hover:border-slate-300 hover:bg-white md:grid-cols-[1fr_auto]"
            >
              <div>
                <p className="mb-2 text-xs uppercase tracking-[0.24em] text-slate-500">
                  {run.workflowMode.replaceAll("_", " ")}
                </p>
                <p className="text-lg font-medium text-slate-950">{truncate(run.goal, 170)}</p>
                <p className="mt-2 text-sm text-slate-600">
                  Created {formatDateTime(run.createdAt)} · Steps {run.stepCount}/{run.maxSteps}
                </p>
              </div>
              <div className="flex items-start justify-between gap-3 md:flex-col md:items-end">
                <RunStatusPill status={run.status} />
                <span className="text-sm text-slate-500">{run.model}</span>
              </div>
            </Link>
          ))}
        </div>
      </SectionCard>
    </AppShell>
  );
}
