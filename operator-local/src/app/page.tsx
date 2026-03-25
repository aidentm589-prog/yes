import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { RunStatusPill } from "@/components/run-status-pill";
import { SectionCard } from "@/components/section-card";
import { TaskComposer } from "@/components/task-composer";
import { formatRelativeTime, truncate } from "@/lib/utils";
import { getEnv } from "@/lib/env";
import { ensureDefaultSettings } from "@/server/services/settings-service";
import { listRuns } from "@/server/services/run-service";

export const revalidate = 0;

export default async function HomePage() {
  const [runs, settings] = await Promise.all([listRuns(), ensureDefaultSettings()]);
  const env = getEnv();

  return (
    <AppShell currentPath="/">
      <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
        <SectionCard
          eyebrow="Launch"
          title="Start a local Operator-style run"
          className="min-h-[28rem]"
        >
          <div className="mb-8 grid gap-4 md:grid-cols-3">
            <div className="rounded-[1.4rem] bg-slate-950 px-5 py-4 text-white">
              <p className="text-xs uppercase tracking-[0.24em] text-white/70">Runs recorded</p>
              <p className="mt-3 text-3xl font-semibold">{runs.length}</p>
            </div>
            <div className="rounded-[1.4rem] bg-[#dae8de] px-5 py-4 text-slate-900">
              <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Planner model</p>
              <p className="mt-3 text-xl font-semibold">{env.OPENAI_MODEL}</p>
            </div>
            <div className="rounded-[1.4rem] bg-[#efe1d0] px-5 py-4 text-slate-900">
              <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Settings loaded</p>
              <p className="mt-3 text-xl font-semibold">{settings.length}</p>
            </div>
          </div>
          <TaskComposer />
        </SectionCard>

        <SectionCard eyebrow="Recent" title="Latest runs">
          <div className="space-y-4">
            {runs.slice(0, 5).map((run) => (
              <Link
                key={run.id}
                href={`/runs/${run.id}`}
                className="block rounded-[1.4rem] border border-slate-200 bg-[#fcfbf6] px-4 py-4 transition hover:border-slate-300 hover:bg-white"
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <RunStatusPill status={run.status} />
                  <span className="text-xs text-slate-500">{formatRelativeTime(run.createdAt)}</span>
                </div>
                <p className="text-sm font-medium text-slate-900">{truncate(run.goal, 120)}</p>
                <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-500">
                  {run.workflowMode.replaceAll("_", " ")}
                </p>
              </Link>
            ))}
            {runs.length === 0 ? (
              <p className="text-sm text-slate-600">
                No runs yet. Start with a browser task like researching a product page, extracting
                structured details, or drafting a form fill.
              </p>
            ) : null}
          </div>
        </SectionCard>
      </div>
    </AppShell>
  );
}
