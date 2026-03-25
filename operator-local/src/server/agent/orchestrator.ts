import { type RunStatus } from "@prisma/client";

import type { BrowserAction } from "@/lib/schemas";
import { getEnv } from "@/lib/env";
import { logger } from "@/lib/logger";

import { isTerminalStatus } from "@/server/agent/completion";
import { executeActionForRun } from "@/server/agent/executor";
import { decideNextAction, isPlannerError } from "@/server/agent/planner";
import {
  detectLikelyLoop,
  initialMemory,
  recordPlannerIssue,
  updateMemoryWithAction,
  updateMemoryWithObservation,
} from "@/server/agent/memory";
import { validateActionAgainstPolicy } from "@/server/agent/policies";
import { compareOptionsWorkflow } from "@/server/agent/workflows/compareOptions";
import { extractAndSummarizeWorkflow } from "@/server/agent/workflows/extractAndSummarize";
import { formAssistWorkflow } from "@/server/agent/workflows/formAssist";
import { generalBrowserTaskWorkflow } from "@/server/agent/workflows/generalBrowserTask";
import { captureRunScreenshot } from "@/server/browser/actions";
import { inspectPage } from "@/server/browser/observers";
import { closeBrowserSession, getBrowserSession } from "@/server/browser/playwright";
import { runRepository } from "@/server/repositories/run-repository";

const workflows = {
  general_browser_task: generalBrowserTaskWorkflow,
  extract_and_summarize: extractAndSummarizeWorkflow,
  compare_options: compareOptionsWorkflow,
  draft_form_fill: formAssistWorkflow,
};

function getWorkflowGuidance(mode: keyof typeof workflows) {
  return workflows[mode].guidance;
}

async function captureObservation(
  runId: string,
  label: string,
  phase: "pre_action" | "post_action" | "checkpoint" = "checkpoint",
) {
  const { page } = await getBrowserSession(runId);
  const screenshotPath = await captureRunScreenshot(runId, label);
  const observation = await inspectPage(page, phase);
  observation.screenshotPath = screenshotPath;

  const record = await runRepository.createObservation({
    runId,
    url: observation.url,
    title: observation.title,
    summary: `[${phase.replaceAll("_", " ")}] ${observation.summary}`,
    visibleText: observation.visibleText,
    interactiveMap: observation.interactiveMap as never,
    recentErrors: [
      ...observation.recentErrors,
      observation.interactiveSummary ? `interactive-summary:${observation.interactiveSummary}` : "",
      observation.startupBlank ? "startup-blank:true" : "",
      `phase:${phase}`,
    ].filter(Boolean) as never,
    screenshotPath,
  });

  const screenshot = await runRepository.createScreenshot({
    runId,
    observationId: record.id,
    label,
    path: screenshotPath,
  });

  return {
    observation,
    observationRecord: record,
    screenshotRecord: screenshot,
  };
}

function shouldObserveAfterAction(action: BrowserAction) {
  return !["finish", "requestApproval", "getPageSummary", "captureScreenshot"].includes(action.kind);
}

function nextFailureStatus(runStepCount: number, maxSteps: number): RunStatus {
  return runStepCount >= maxSteps ? "failed" : "running";
}

function isSimpleSummaryGoal(goal: string) {
  return /summari[sz]e|top headlines|news|extract|gather details/i.test(goal);
}

function buildObservationBackedFinish(runId: string, goal: string, observation: Awaited<ReturnType<typeof captureObservation>>["observation"]) {
  const conciseSummary =
    observation.summary.length > 320
      ? `${observation.summary.slice(0, 317).trim()}...`
      : observation.summary;

  return {
    status: "completed" as const,
    summary: `Completed the task using the current page state from ${observation.url}. ${observation.title ? `Title: ${observation.title}. ` : ""}${conciseSummary}`,
    structuredData: {
      goal,
      title: observation.title,
      url: observation.url,
      pageSummary: observation.summary,
      visibleText: observation.visibleText,
      interactiveSummary: observation.interactiveSummary ?? "",
      evidence: {
        screenshotPath: observation.screenshotPath ?? null,
      },
    },
  };
}

function canFinishFromObservation(goal: string, observation: Awaited<ReturnType<typeof captureObservation>>["observation"]) {
  return (
    isSimpleSummaryGoal(goal) &&
    !observation.startupBlank &&
    observation.visibleText.trim().length > 80
  );
}

function shouldRetryRun(run: Awaited<ReturnType<typeof runRepository.getRun>>, message: string) {
  if (!run) {
    return false;
  }

  return (
    run.retryCount < run.maxRetries &&
    /Selector not found|Timeout|Target page, context or browser has been closed|Navigation.*interrupted|net::ERR/i.test(
      message,
    )
  );
}

async function failRun(runId: string, code: string, message: string, details?: unknown) {
  await runRepository.createError({
    runId,
    code,
    message,
    details: details as never,
  });

  await closeBrowserSession(runId).catch(() => null);

  return runRepository.updateRun(runId, {
    status: "failed",
    finishedAt: new Date(),
  });
}

export async function continueRun(runId: string) {
  const env = getEnv();
  const invokeBudget = env.OPERATOR_INVOKE_STEP_BUDGET;
  let run = await runRepository.getRun(runId);

  if (!run) {
    throw new Error(`Run ${runId} was not found.`);
  }

  if (isTerminalStatus(run.status)) {
    return run;
  }

  if (!run.startedAt) {
    run = await runRepository.updateRun(runId, {
      status: "running",
      startedAt: new Date(),
      lastHeartbeatAt: new Date(),
    });
  }

  let memory =
    (run.memory as ReturnType<typeof initialMemory> | null) ??
    initialMemory(run.goal, run.workflowMode);

  for (let step = 0; step < invokeBudget; step += 1) {
    run = (await runRepository.getRun(runId)) ?? run;

    if (isTerminalStatus(run.status) || run.status === "waiting_for_approval") {
      break;
    }

    const timedOut =
      run.startedAt && Date.now() - run.startedAt.getTime() > run.timeoutMs;
    if (timedOut) {
      await runRepository.createError({
        runId,
        code: "TIMEOUT",
        message: "Run exceeded the configured timeout window.",
      });
      run = await runRepository.updateRun(runId, {
        status: "timed_out",
        finishedAt: new Date(),
      });
      break;
    }

    if (run.stepCount >= run.maxSteps) {
      await runRepository.createError({
        runId,
        code: "STEP_CAP",
        message: "Run exceeded the configured maximum number of steps.",
      });
      run = await runRepository.updateRun(runId, {
        status: "failed",
        finishedAt: new Date(),
      });
      break;
    }

    try {
      const { observation, observationRecord, screenshotRecord } = await captureObservation(
        runId,
        `step-${run.stepCount + 1}`,
        "pre_action",
      );
      memory = updateMemoryWithObservation(memory, observation);

      let decision;
      try {
        decision = await decideNextAction({
          model: run.model,
          reasoningEffort: run.reasoningEffort as "low" | "medium" | "high",
          workflowGuidance: getWorkflowGuidance(run.workflowMode),
          goal: run.goal,
          observation,
          memory,
          pendingApproval: false,
        });
      } catch (error) {
        if (isPlannerError(error) && canFinishFromObservation(run.goal, observation)) {
          const fallbackFinish = buildObservationBackedFinish(runId, run.goal, observation);
          await runRepository.createError({
            runId,
            code: "PLANNER_OUTPUT_RECOVERED",
            message: error.message,
            details: error.details as never,
          });
          await runRepository.upsertFinalOutcome(
            runId,
            fallbackFinish.status,
            fallbackFinish.summary,
            fallbackFinish.structuredData as never,
          );
          run = await runRepository.updateRun(runId, {
            status: "completed",
            finishedAt: new Date(),
            latestUrl: observation.url,
            latestObservationId: observationRecord.id,
            memory: memory as never,
            stepCount: {
              increment: 1,
            },
          });
          break;
        }

        throw error;
      }

      if (
        decision.action.kind === "getPageSummary" &&
        isSimpleSummaryGoal(run.goal) &&
        memory.recentActions.some(
          (entry) => entry.kind === "getPageSummary" && entry.url === observation.url,
        ) &&
        !observation.startupBlank
      ) {
        const fallbackFinish = buildObservationBackedFinish(runId, run.goal, observation);
        await runRepository.upsertFinalOutcome(
          runId,
          fallbackFinish.status,
          fallbackFinish.summary,
          fallbackFinish.structuredData as never,
        );
        run = await runRepository.updateRun(runId, {
          status: "completed",
          finishedAt: new Date(),
          latestUrl: observation.url,
          latestObservationId: observationRecord.id,
          memory: memory as never,
          stepCount: {
            increment: 1,
          },
        });
        break;
      }

      const actionPolicy = validateActionAgainstPolicy(
        decision.action,
        run.policySnapshot as never,
        observation,
      );

      if (!actionPolicy.allowed) {
        run = await failRun(runId, "POLICY_BLOCK", actionPolicy.reason, decision);
        break;
      }

      const loopDetected = detectLikelyLoop(memory, decision.action, observation.url);
      if (loopDetected) {
        run = await failRun(
          runId,
          "LOOP_DETECTED",
          "The planner repeated the same action on the same page without making progress.",
          decision,
        );
        break;
      }

      const actionRecord = await runRepository.createAction({
        runId,
        kind: decision.action.kind,
        status: actionPolicy.requiresApproval ? "blocked" : "pending",
        rationale: decision.rationale,
        inputPayload: decision as never,
        url: observation.url,
        observationId: observationRecord.id,
        screenshotId: screenshotRecord.id,
        retryCount: run.retryCount,
      });

      if (actionPolicy.requiresApproval || decision.action.kind === "requestApproval") {
        const reason =
          decision.action.kind === "requestApproval"
            ? decision.action.reason
            : actionPolicy.requiresApproval
              ? actionPolicy.reason
              : "Approval required by policy.";
        await runRepository.createApprovalRequest({
          runId,
          observationId: observationRecord.id,
          reason,
          actionPayload:
            decision.action.kind === "requestApproval"
              ? decision.action.actionPayload
              : (decision.action as unknown as Record<string, unknown>),
          pageContext: observation as never,
          screenshotPath: observation.screenshotPath,
        } as never);
        await runRepository.updateAction(actionRecord.id, {
          status: "blocked",
          completedAt: new Date(),
        });
        run = await runRepository.updateRun(runId, {
          status: "waiting_for_approval",
          latestUrl: observation.url,
          latestObservationId: observationRecord.id,
          memory: memory as never,
          lastHeartbeatAt: new Date(),
        });
        break;
      }

      const result = await executeActionForRun(runId, decision.action);
      let latestObservationId = observationRecord.id;
      let latestUrl = observation.url;
      let actionScreenshotId = screenshotRecord.id;

      if (shouldObserveAfterAction(decision.action)) {
        const after = await captureObservation(runId, `after-${decision.action.kind}`, "post_action");
        latestObservationId = after.observationRecord.id;
        latestUrl = after.observation.url;
        actionScreenshotId = after.screenshotRecord.id;
        memory = updateMemoryWithObservation(memory, after.observation);
      }

      memory = updateMemoryWithAction(memory, decision.action, latestUrl, decision.rationale);

      await runRepository.updateAction(actionRecord.id, {
        status: "success",
        outputPayload: result.output as never,
        completedAt: new Date(),
        observationId: latestObservationId,
        screenshotId: actionScreenshotId,
      });

      if (decision.action.kind === "finish") {
        const structuredData = {
          ...(decision.action.structuredData ?? {}),
          factsGathered: memory.discoveredFacts,
          pagesVisited: memory.visitedUrls,
          actionsTaken: memory.completedSteps,
          unresolvedIssues: memory.blockedReasons,
          evidence: {
            latestUrl,
            latestObservationId,
            latestScreenshotId: actionScreenshotId,
          },
        };
        await runRepository.upsertFinalOutcome(
          runId,
          "completed",
          decision.action.summary,
          structuredData as never,
        );
        run = await runRepository.updateRun(runId, {
          status: "completed",
          finishedAt: new Date(),
          stepCount: {
            increment: 1,
          },
          latestUrl,
          latestObservationId,
          memory: memory as never,
        });
        break;
      }

      run = await runRepository.updateRun(runId, {
        status: nextFailureStatus(run.stepCount + 1, run.maxSteps),
        latestUrl,
        latestObservationId,
        memory: memory as never,
        stepCount: {
          increment: 1,
        },
        lastHeartbeatAt: new Date(),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown run error";
      await logger.error({
        scope: "orchestrator",
        message: "Step execution failed",
        data: { runId, error: message },
      });

      memory = recordPlannerIssue(memory, message);

      if (shouldRetryRun(run, message)) {
        await runRepository.createError({
          runId,
          code: "RETRYABLE_STEP_FAILURE",
          message,
          details: { retryAttempt: run.retryCount + 1 } as never,
        });
        run = await runRepository.updateRun(runId, {
          status: "running",
          retryCount: {
            increment: 1,
          },
          memory: memory as never,
          lastHeartbeatAt: new Date(),
        });
        continue;
      }

      run = await failRun(runId, "STEP_FAILURE", message, {
        blockedReasons: [...memory.blockedReasons, message].slice(-8),
      });
      break;
    }
  }

  return runRepository.getRun(runId);
}
