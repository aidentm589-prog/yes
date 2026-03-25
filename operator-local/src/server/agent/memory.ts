import type { WorkflowMode } from "@prisma/client";

import type { BrowserAction } from "@/lib/schemas";
import type { ObservationSnapshot, RunMemory } from "@/types/operator";

export function initialMemory(goal: string, workflowMode: WorkflowMode): RunMemory {
  return {
    goal,
    workflowMode,
    discoveredFacts: [],
    completedSteps: [],
    blockedReasons: [],
    recentActions: [],
  };
}

export function updateMemoryWithObservation(memory: RunMemory, observation: ObservationSnapshot): RunMemory {
  return {
    ...memory,
    latestObservationSummary: observation.summary,
  };
}

export function updateMemoryWithAction(
  memory: RunMemory,
  action: BrowserAction,
  url: string,
  completedStep?: string,
): RunMemory {
  return {
    ...memory,
    completedSteps: completedStep
      ? [...memory.completedSteps, completedStep].slice(-10)
      : memory.completedSteps,
    recentActions: [
      ...memory.recentActions,
      {
        kind: action.kind,
        fingerprint: JSON.stringify(action),
        url,
      },
    ].slice(-6),
  };
}

export function detectLikelyLoop(memory: RunMemory, action: BrowserAction, url: string) {
  const fingerprint = JSON.stringify(action);
  const recent = memory.recentActions.filter(
    (entry) => entry.fingerprint === fingerprint && entry.url === url,
  );

  return recent.length >= 2;
}
