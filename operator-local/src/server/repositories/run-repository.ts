import type { Prisma, WorkflowMode } from "@prisma/client";

import { db } from "@/lib/db";

export const runInclude = {
  task: true,
  actions: {
    orderBy: {
      createdAt: "asc",
    },
  },
  observations: {
    orderBy: {
      createdAt: "desc",
    },
  },
  screenshots: {
    orderBy: {
      createdAt: "desc",
    },
  },
  approvals: {
    orderBy: {
      requestedAt: "desc",
    },
  },
  errors: {
    orderBy: {
      createdAt: "desc",
    },
  },
  extractions: {
    orderBy: {
      createdAt: "desc",
    },
  },
  finalOutcome: true,
} satisfies Prisma.RunInclude;

export const runRepository = {
  listRuns() {
    return db.run.findMany({
      include: {
        task: true,
        approvals: true,
        finalOutcome: true,
      },
      orderBy: {
        createdAt: "desc",
      },
    });
  },

  getRun(runId: string) {
    return db.run.findUnique({
      where: { id: runId },
      include: runInclude,
    });
  },

  createRun(input: {
    goal: string;
    workflowMode: WorkflowMode;
    model: string;
    reasoningEffort: string;
    maxSteps: number;
    maxRetries: number;
    timeoutMs: number;
    storagePath: string;
    policySnapshot: Prisma.InputJsonValue;
  }) {
    return db.run.create({
      data: {
        goal: input.goal,
        workflowMode: input.workflowMode,
        model: input.model,
        reasoningEffort: input.reasoningEffort,
        maxSteps: input.maxSteps,
        maxRetries: input.maxRetries,
        timeoutMs: input.timeoutMs,
        storagePath: input.storagePath,
        policySnapshot: input.policySnapshot,
        task: {
          create: {
            originalPrompt: input.goal,
            normalizedGoal: input.goal,
          },
        },
      },
      include: runInclude,
    });
  },

  updateRun(runId: string, data: Prisma.RunUpdateInput) {
    return db.run.update({
      where: { id: runId },
      data,
      include: runInclude,
    });
  },

  createObservation(data: Prisma.ObservationUncheckedCreateInput) {
    return db.observation.create({ data });
  },

  createScreenshot(data: Prisma.ScreenshotUncheckedCreateInput) {
    return db.screenshot.create({ data });
  },

  createAction(data: Prisma.AgentActionUncheckedCreateInput) {
    return db.agentAction.create({ data });
  },

  updateAction(actionId: string, data: Prisma.AgentActionUncheckedUpdateInput) {
    return db.agentAction.update({
      where: { id: actionId },
      data,
    });
  },

  createApprovalRequest(data: Prisma.ApprovalRequestUncheckedCreateInput) {
    return db.approvalRequest.create({ data });
  },

  getApprovalRequest(id: string) {
    return db.approvalRequest.findUnique({
      where: { id },
      include: {
        run: true,
        observation: true,
      },
    });
  },

  listPendingApprovals() {
    return db.approvalRequest.findMany({
      where: {
        status: "pending",
      },
      include: {
        run: true,
        observation: true,
      },
      orderBy: {
        requestedAt: "desc",
      },
    });
  },

  getScreenshot(runId: string, screenshotId: string) {
    return db.screenshot.findFirst({
      where: {
        id: screenshotId,
        runId,
      },
    });
  },

  resolveApprovalRequest(id: string, data: Prisma.ApprovalRequestUpdateInput) {
    return db.approvalRequest.update({
      where: { id },
      data,
      include: {
        run: true,
      },
    });
  },

  upsertFinalOutcome(runId: string, status: string, summary: string, structuredData?: Prisma.InputJsonValue) {
    return db.finalOutcome.upsert({
      where: { runId },
      update: { status, summary, structuredData },
      create: { runId, status, summary, structuredData },
    });
  },

  createExtraction(data: Prisma.ExtractionArtifactUncheckedCreateInput) {
    return db.extractionArtifact.create({ data });
  },

  createError(data: Prisma.ErrorEventUncheckedCreateInput) {
    return db.errorEvent.create({ data });
  },
};
