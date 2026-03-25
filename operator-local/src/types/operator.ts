import type { WorkflowMode } from "@prisma/client";

import type { BrowserAction } from "@/lib/schemas";

export type InteractiveElement = {
  selector: string;
  tag: string;
  role: string | null;
  text: string;
  name: string | null;
  ariaLabel: string | null;
  placeholder: string | null;
  type: string | null;
  href: string | null;
  disabled: boolean;
  selectorSource: string | null;
};

export type ObservationSnapshot = {
  url: string;
  title: string;
  summary: string;
  visibleText: string;
  interactiveMap: InteractiveElement[];
  recentErrors: string[];
  screenshotPath?: string;
  startupBlank?: boolean;
  phase?: "pre_action" | "post_action" | "checkpoint";
  interactiveSummary?: string;
};

export type PolicySnapshot = {
  allowedDomains: string[];
  blockedDomains: string[];
  maxSteps: number;
  maxRetries: number;
  timeoutMs: number;
  screenshotEveryStep: boolean;
};

export type RunMemory = {
  goal: string;
  workflowMode: WorkflowMode;
  discoveredFacts: string[];
  completedSteps: string[];
  blockedReasons: string[];
  visitedUrls: string[];
  unresolvedQuestions: string[];
  extractedEntities: string[];
  taskSubgoals: string[];
  lastPlannerError?: string;
  recentActions: Array<{
    kind: BrowserAction["kind"];
    fingerprint: string;
    url: string;
  }>;
  latestObservationSummary?: string;
};
