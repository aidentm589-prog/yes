import type { WorkflowMode } from "@prisma/client";

import type { BrowserAction } from "@/lib/schemas";

export type InteractiveElement = {
  selector: string;
  tag: string;
  role: string | null;
  text: string;
  placeholder: string | null;
  type: string | null;
};

export type ObservationSnapshot = {
  url: string;
  title: string;
  summary: string;
  visibleText: string;
  interactiveMap: InteractiveElement[];
  recentErrors: string[];
  screenshotPath?: string;
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
  recentActions: Array<{
    kind: BrowserAction["kind"];
    fingerprint: string;
    url: string;
  }>;
  latestObservationSummary?: string;
};
