import { execFileSync } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import path from "node:path";

import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const cwd = path.resolve(__dirname, "../..");
const dbPath = path.join(cwd, "prisma", "test-integration.db");
const dbUrl = `file:${dbPath}`;

const plannerMock = vi.fn();
const executeActionMock = vi.fn();
const inspectPageMock = vi.fn();
const captureScreenshotMock = vi.fn();
const getBrowserSessionMock = vi.fn();

vi.mock("@/server/agent/planner", () => ({
  decideNextAction: plannerMock,
}));

vi.mock("@/server/agent/executor", () => ({
  executeActionForRun: executeActionMock,
}));

vi.mock("@/server/browser/observers", () => ({
  inspectPage: inspectPageMock,
}));

vi.mock("@/server/browser/actions", () => ({
  captureRunScreenshot: captureScreenshotMock,
}));

vi.mock("@/server/browser/playwright", () => ({
  getBrowserSession: getBrowserSessionMock,
}));

describe("continueRun", () => {
  beforeAll(() => {
    if (existsSync(dbPath)) {
      rmSync(dbPath);
    }

    process.env.DATABASE_URL = dbUrl;
    process.env.OPENAI_MODEL = "gpt-5.2";
    process.env.OPENAI_REASONING_EFFORT = "medium";
    process.env.OPERATOR_STORAGE_DIR = "./runtime";
    process.env.OPERATOR_ALLOWED_DOMAINS = "";
    process.env.OPERATOR_BLOCKED_DOMAINS = "";
    process.env.OPERATOR_DEFAULT_MAX_STEPS = "6";
    process.env.OPERATOR_DEFAULT_MAX_RETRIES = "1";
    process.env.OPERATOR_DEFAULT_TIMEOUT_MS = "60000";
    process.env.OPERATOR_SCREENSHOT_EVERY_STEP = "false";
    process.env.OPERATOR_INVOKE_STEP_BUDGET = "3";

    execFileSync("npm", ["run", "db:push"], {
      cwd,
      env: {
        ...process.env,
        DATABASE_URL: dbUrl,
      },
      stdio: "inherit",
    });
  });

  beforeEach(async () => {
    plannerMock.mockReset();
    executeActionMock.mockReset();
    inspectPageMock.mockReset();
    captureScreenshotMock.mockReset();
    getBrowserSessionMock.mockReset();

    const { db } = await import("@/lib/db");

    await db.errorEvent.deleteMany();
    await db.approvalRequest.deleteMany();
    await db.agentAction.deleteMany();
    await db.screenshot.deleteMany();
    await db.observation.deleteMany();
    await db.extractionArtifact.deleteMany();
    await db.finalOutcome.deleteMany();
    await db.task.deleteMany();
    await db.run.deleteMany();
  });

  afterAll(() => {
    if (existsSync(dbPath)) {
      rmSync(dbPath);
    }
  });

  it("creates actions, observations, and a final outcome through the orchestration loop", async () => {
    getBrowserSessionMock.mockResolvedValue({ page: { url: () => "https://example.com" } });
    captureScreenshotMock.mockResolvedValue("/tmp/mock-shot.png");
    inspectPageMock
      .mockResolvedValueOnce({
        url: "about:blank",
        title: "Blank",
        summary: "Blank page",
        visibleText: "",
        interactiveMap: [],
        recentErrors: [],
        screenshotPath: "/tmp/mock-shot.png",
      })
      .mockResolvedValueOnce({
        url: "https://example.com",
        title: "Example",
        summary: "Example page",
        visibleText: "Example Domain",
        interactiveMap: [],
        recentErrors: [],
        screenshotPath: "/tmp/mock-shot.png",
      })
      .mockResolvedValueOnce({
        url: "https://example.com",
        title: "Example",
        summary: "Example page",
        visibleText: "Example Domain",
        interactiveMap: [],
        recentErrors: [],
        screenshotPath: "/tmp/mock-shot.png",
      });

    plannerMock
      .mockResolvedValueOnce({
        rationale: "Navigate to the target site.",
        completionSignal: "continue",
        action: {
          kind: "navigate",
          url: "https://example.com",
        },
      })
      .mockResolvedValueOnce({
        rationale: "The goal is complete.",
        completionSignal: "done",
        action: {
          kind: "finish",
          summary: "Collected the page information.",
          structuredData: {
            title: "Example Domain",
          },
        },
      });

    executeActionMock
      .mockResolvedValueOnce({
        ok: true,
        output: {
          ok: true,
          url: "https://example.com",
        },
      })
      .mockResolvedValueOnce({
        ok: true,
        output: {
          summary: "Collected the page information.",
          structuredData: {
            title: "Example Domain",
          },
        },
      });

    const [{ createRun }, { continueRun }, { db }] = await Promise.all([
      import("@/server/services/run-service"),
      import("@/server/agent/orchestrator"),
      import("@/lib/db"),
    ]);

    const run = await createRun("Navigate to example.com and summarize the landing page.");
    const updated = await continueRun(run.id);

    expect(updated?.status).toBe("completed");

    const persisted = await db.run.findUnique({
      where: { id: run.id },
      include: {
        actions: true,
        observations: true,
        finalOutcome: true,
      },
    });

    expect(persisted?.actions).toHaveLength(2);
    expect(persisted?.observations.length).toBeGreaterThanOrEqual(2);
    expect(persisted?.finalOutcome?.summary).toContain("Collected the page information");
  });
});
