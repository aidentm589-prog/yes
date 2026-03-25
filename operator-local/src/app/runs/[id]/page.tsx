import Link from "next/link";
import { notFound } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ApprovalActions } from "@/components/approval-actions";
import { LiveRunController } from "@/components/live-run-controller";
import { RunStatusPill } from "@/components/run-status-pill";
import { SectionCard } from "@/components/section-card";
import { formatDateTime, truncate } from "@/lib/utils";
import { getRunDetail } from "@/server/services/run-service";

export const revalidate = 0;

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const run = await getRunDetail(id);

  if (!run) {
    notFound();
  }

  const latestPendingApproval = run.approvals.find((approval) => approval.status === "pending");
  const plannerAction = run.actions.find((action) => {
    const payload = action.inputPayload as Record<string, unknown> | null;
    const plannerMeta = payload?.plannerMeta as Record<string, unknown> | undefined;
    return typeof plannerMeta?.provider === "string";
  });
  const plannerPayload = plannerAction?.inputPayload as Record<string, unknown> | null | undefined;
  const plannerMeta = plannerPayload?.plannerMeta as Record<string, unknown> | undefined;
  const plannerProvider =
    typeof plannerMeta?.provider === "string" ? plannerMeta.provider : "unknown";
  const hadRetryableErrors = run.errors.some((error) => error.code === "RETRYABLE_STEP_FAILURE");

  return (
    <AppShell currentPath="/runs">
      <LiveRunController runId={run.id} status={run.status} />
      <div className="grid gap-6 xl:grid-cols-[0.88fr_1.12fr]">
        <div className="space-y-6">
          <SectionCard eyebrow="Run" title="Execution overview">
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-3">
                <RunStatusPill status={run.status} />
                <span className="text-sm text-slate-500">{run.workflowMode.replaceAll("_", " ")}</span>
              </div>
              <p className="text-lg text-slate-900">{run.goal}</p>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-[1.3rem] bg-[#fcfbf6] p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Planner</p>
                  <p className="mt-2 text-lg font-semibold">{run.model}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-500">
                    Provider: {plannerProvider}
                  </p>
                </div>
                <div className="rounded-[1.3rem] bg-[#fcfbf6] p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Steps</p>
                  <p className="mt-2 text-lg font-semibold">
                    {run.stepCount} / {run.maxSteps}
                  </p>
                  <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-500">
                    Retryable errors seen: {hadRetryableErrors ? "yes" : "no"}
                  </p>
                </div>
              </div>
              <div className="text-sm text-slate-600">
                <p>Started: {formatDateTime(run.startedAt)}</p>
                <p>Updated: {formatDateTime(run.updatedAt)}</p>
                <p>Latest URL: {run.latestUrl ?? "Not navigated yet"}</p>
              </div>
              {run.status === "failed" && run.errors[0] ? (
                <div className="rounded-[1.4rem] border border-rose-200 bg-rose-50 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-rose-700">Run failed</p>
                  <p className="mt-2 text-sm text-rose-900">{run.errors[0].message}</p>
                  {run.errors[0].details &&
                  typeof run.errors[0].details === "object" &&
                  run.errors[0].details !== null &&
                  "retryAttempt" in (run.errors[0].details as Record<string, unknown>) ? (
                    <p className="mt-2 text-xs text-rose-700">
                      Retryable failure attempts were recorded before the run stopped.
                    </p>
                  ) : null}
                </div>
              ) : null}
              {latestPendingApproval ? (
                <div className="rounded-[1.4rem] border border-amber-200 bg-amber-50 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-amber-700">
                    Approval required
                  </p>
                  <p className="mt-2 text-sm text-amber-900">{latestPendingApproval.reason}</p>
                  <div className="mt-4">
                    <ApprovalActions approvalId={latestPendingApproval.id} />
                  </div>
                </div>
              ) : null}
              <Link
                href="/approvals"
                className="inline-flex rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white"
              >
                Open approvals panel
              </Link>
            </div>
          </SectionCard>

          <SectionCard eyebrow="Outcome" title="Final result">
            {run.finalOutcome ? (
              <div className="space-y-3">
                <p className="text-lg text-slate-900">{run.finalOutcome.summary}</p>
                {run.memory &&
                typeof run.memory === "object" &&
                run.memory !== null &&
                "discoveredFacts" in (run.memory as Record<string, unknown>) ? (
                  <div className="rounded-[1.2rem] bg-[#fcfbf6] p-4 text-sm text-slate-700">
                    <p className="font-semibold text-slate-900">Facts gathered</p>
                    <ul className="mt-2 space-y-1">
                      {(((run.memory as Record<string, unknown>).discoveredFacts as string[]) ?? [])
                        .slice(0, 6)
                        .map((fact) => (
                          <li key={fact}>• {fact}</li>
                        ))}
                    </ul>
                  </div>
                ) : null}
                <pre className="overflow-x-auto rounded-[1.3rem] bg-slate-950 p-4 text-sm text-slate-100">
                  {JSON.stringify(run.finalOutcome.structuredData ?? {}, null, 2)}
                </pre>
              </div>
            ) : (
              <p className="text-sm text-slate-600">
                No final outcome yet. The agent is still running or paused before completion.
              </p>
            )}
          </SectionCard>

          <SectionCard eyebrow="Diagnostics" title="Errors and extracted artifacts">
            <div className="space-y-4">
              <div>
                <p className="mb-2 text-sm font-semibold text-slate-900">Errors</p>
                {run.errors.length ? (
                  <div className="space-y-3">
                    {run.errors.map((error) => (
                      <div key={error.id} className="rounded-[1.2rem] bg-rose-50 p-4 text-sm">
                        <p className="font-semibold text-rose-900">{error.code}</p>
                        <p className="mt-1 text-rose-800">{error.message}</p>
                        {error.details ? (
                          <pre className="mt-3 overflow-x-auto rounded-[1rem] bg-white/70 p-3 text-xs text-rose-900">
                            {JSON.stringify(error.details, null, 2)}
                          </pre>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-600">No errors recorded for this run.</p>
                )}
              </div>
              <div>
                <p className="mb-2 text-sm font-semibold text-slate-900">Extraction artifacts</p>
                {run.extractions.length ? (
                  <div className="space-y-3">
                    {run.extractions.map((artifact) => (
                      <div key={artifact.id} className="rounded-[1.2rem] bg-[#fcfbf6] p-4">
                        <p className="text-sm font-semibold text-slate-900">{artifact.label}</p>
                        <pre className="mt-2 overflow-x-auto text-xs text-slate-700">
                          {JSON.stringify(artifact.content, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-600">No artifacts captured yet.</p>
                )}
              </div>
            </div>
          </SectionCard>
        </div>

        <div className="space-y-6">
          <SectionCard eyebrow="Timeline" title="Action log">
            <div className="space-y-4">
              {run.actions.length ? (
                run.actions.map((action) => (
                  <div key={action.id} className="rounded-[1.35rem] border border-slate-200 bg-[#fcfbf6] p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <p className="font-semibold text-slate-950">{action.kind}</p>
                      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                        {action.status}
                      </span>
                    </div>
                    <p className="text-sm text-slate-700">{truncate(action.rationale, 220)}</p>
                    <pre className="mt-3 overflow-x-auto rounded-[1rem] bg-white p-3 text-xs text-slate-700">
                      {JSON.stringify(action.inputPayload, null, 2)}
                    </pre>
                    {action.outputPayload ? (
                      <pre className="mt-3 overflow-x-auto rounded-[1rem] bg-slate-950 p-3 text-xs text-slate-100">
                        {JSON.stringify(action.outputPayload, null, 2)}
                      </pre>
                    ) : null}
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-600">No actions logged yet.</p>
              )}
            </div>
          </SectionCard>

          <SectionCard eyebrow="Evidence" title="Screenshots and observations">
            <div className="space-y-4">
              {run.screenshots.length ? (
                run.screenshots.slice(0, 8).map((screenshot) => (
                  <div key={screenshot.id} className="rounded-[1.35rem] border border-slate-200 bg-[#fcfbf6] p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-950">{screenshot.label}</p>
                        <p className="text-xs text-slate-500">{formatDateTime(screenshot.createdAt)}</p>
                      </div>
                      <Link
                        href={`/api/runs/${run.id}/screenshots/${screenshot.id}`}
                        className="text-sm font-medium text-slate-700 underline"
                        target="_blank"
                      >
                        Open full image
                      </Link>
                    </div>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={`/api/runs/${run.id}/screenshots/${screenshot.id}`}
                      alt={screenshot.label}
                      className="w-full rounded-[1rem] border border-slate-200"
                    />
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-600">No screenshots recorded yet.</p>
              )}

              {run.observations.length ? (
                <div className="space-y-3">
                  {run.observations.slice(0, 4).map((observation) => (
                    <div key={observation.id} className="rounded-[1.2rem] bg-white p-4">
                      <p className="text-sm font-semibold text-slate-950">{observation.title || observation.url}</p>
                      <p className="mt-2 text-sm text-slate-700">{truncate(observation.summary, 260)}</p>
                      {observation.recentErrors ? (
                        <pre className="mt-3 overflow-x-auto text-xs text-slate-500">
                          {JSON.stringify(observation.recentErrors, null, 2)}
                        </pre>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </SectionCard>
        </div>
      </div>
    </AppShell>
  );
}
