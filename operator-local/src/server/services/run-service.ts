import type { WorkflowMode } from "@prisma/client";

import { getEnv } from "@/lib/env";
import { ensureRunStorage } from "@/lib/storage";

import { runRepository } from "@/server/repositories/run-repository";
import { buildPolicySnapshot } from "@/server/services/settings-service";

function classifyWorkflowMode(prompt: string, requestedMode?: WorkflowMode): WorkflowMode {
  if (requestedMode) {
    return requestedMode;
  }

  const lower = prompt.toLowerCase();

  if (lower.includes("compare") || lower.includes("versus")) {
    return "compare_options";
  }

  if (lower.includes("form") || lower.includes("application") || lower.includes("fill")) {
    return "draft_form_fill";
  }

  if (lower.includes("extract") || lower.includes("summarize") || lower.includes("gather details")) {
    return "extract_and_summarize";
  }

  return "general_browser_task";
}

export async function createRun(prompt: string, requestedMode?: WorkflowMode) {
  const env = getEnv();
  const workflowMode = classifyWorkflowMode(prompt, requestedMode);
  const storage = await ensureRunStorage(`pending-${Date.now()}`);
  const policySnapshot = buildPolicySnapshot();

  const run = await runRepository.createRun({
    goal: prompt,
    workflowMode,
    model: env.OPENAI_MODEL,
    reasoningEffort: env.OPENAI_REASONING_EFFORT,
    maxSteps: policySnapshot.maxSteps,
    maxRetries: policySnapshot.maxRetries,
    timeoutMs: policySnapshot.timeoutMs,
    storagePath: storage.runDir,
    policySnapshot: policySnapshot as never,
  });

  const finalStorage = await ensureRunStorage(run.id);

  return runRepository.updateRun(run.id, {
    storagePath: finalStorage.runDir,
  });
}

export async function listRuns() {
  return runRepository.listRuns();
}

export async function getRunDetail(runId: string) {
  return runRepository.getRun(runId);
}
