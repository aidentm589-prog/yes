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
    visitedUrls: [],
    unresolvedQuestions: [],
    extractedEntities: [],
    taskSubgoals: [],
    recentActions: [],
  };
}

export function updateMemoryWithObservation(memory: RunMemory, observation: ObservationSnapshot): RunMemory {
  const visibleFacts = observation.visibleText
    .split(/[\n.]/)
    .map((segment) => segment.replace(/\s+/g, " ").trim())
    .filter((segment) => segment.length > 20)
    .slice(0, 3);

  return {
    ...memory,
    latestObservationSummary: observation.summary,
    discoveredFacts: [...memory.discoveredFacts, ...visibleFacts].slice(-12),
    visitedUrls: observation.url
      ? [...new Set([...memory.visitedUrls, observation.url])].slice(-12)
      : memory.visitedUrls,
    unresolvedQuestions: observation.startupBlank
      ? [...memory.unresolvedQuestions, "A useful destination page has not been opened yet."].slice(
          -6,
        )
      : memory.unresolvedQuestions,
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
    taskSubgoals: [
      ...memory.taskSubgoals,
      `${action.kind} on ${url || "unknown page"}`,
    ].slice(-10),
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

export function recordPlannerIssue(memory: RunMemory, message: string): RunMemory {
  return {
    ...memory,
    lastPlannerError: message,
    blockedReasons: [...memory.blockedReasons, message].slice(-8),
  };
}

export function detectLikelyLoop(memory: RunMemory, action: BrowserAction, url: string) {
  const fingerprint = JSON.stringify(action);
  const recent = memory.recentActions.filter(
    (entry) => entry.fingerprint === fingerprint && entry.url === url,
  );

  return recent.length >= 2;
}
