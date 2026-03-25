import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";

function resolveSqlitePath(databaseUrl: string) {
  const prefix = "file:";
  if (!databaseUrl.startsWith(prefix)) {
    throw new Error(`Unsupported DATABASE_URL for local bootstrap: ${databaseUrl}`);
  }

  const rawPath = databaseUrl.slice(prefix.length);
  if (path.isAbsolute(rawPath)) {
    return rawPath;
  }

  return path.resolve(process.cwd(), rawPath.replace(/^\.\//, ""));
}

const databaseUrl = process.env.DATABASE_URL ?? "file:./prisma/dev.db";
const databasePath = resolveSqlitePath(databaseUrl);

mkdirSync(path.dirname(databasePath), { recursive: true });

const sql = `
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS "Run" (
  "id" TEXT PRIMARY KEY NOT NULL,
  "status" TEXT NOT NULL DEFAULT 'queued',
  "workflowMode" TEXT NOT NULL DEFAULT 'general_browser_task',
  "goal" TEXT NOT NULL,
  "model" TEXT NOT NULL,
  "reasoningEffort" TEXT NOT NULL,
  "maxSteps" INTEGER NOT NULL,
  "maxRetries" INTEGER NOT NULL,
  "timeoutMs" INTEGER NOT NULL,
  "stepCount" INTEGER NOT NULL DEFAULT 0,
  "retryCount" INTEGER NOT NULL DEFAULT 0,
  "policySnapshot" TEXT NOT NULL,
  "memory" TEXT,
  "storagePath" TEXT NOT NULL,
  "latestUrl" TEXT,
  "latestObservationId" TEXT,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "startedAt" DATETIME,
  "finishedAt" DATETIME,
  "lastHeartbeatAt" DATETIME
);

CREATE TABLE IF NOT EXISTS "Task" (
  "id" TEXT PRIMARY KEY NOT NULL,
  "runId" TEXT NOT NULL UNIQUE,
  "originalPrompt" TEXT NOT NULL,
  "normalizedGoal" TEXT,
  "metadata" TEXT,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY ("runId") REFERENCES "Run"("id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "Observation" (
  "id" TEXT PRIMARY KEY NOT NULL,
  "runId" TEXT NOT NULL,
  "url" TEXT NOT NULL,
  "title" TEXT,
  "summary" TEXT NOT NULL,
  "visibleText" TEXT NOT NULL,
  "interactiveMap" TEXT,
  "recentErrors" TEXT,
  "screenshotPath" TEXT,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY ("runId") REFERENCES "Run"("id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "Screenshot" (
  "id" TEXT PRIMARY KEY NOT NULL,
  "runId" TEXT NOT NULL,
  "observationId" TEXT,
  "label" TEXT NOT NULL,
  "path" TEXT NOT NULL,
  "mimeType" TEXT NOT NULL DEFAULT 'image/png',
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY ("runId") REFERENCES "Run"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY ("observationId") REFERENCES "Observation"("id") ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "AgentAction" (
  "id" TEXT PRIMARY KEY NOT NULL,
  "runId" TEXT NOT NULL,
  "kind" TEXT NOT NULL,
  "status" TEXT NOT NULL DEFAULT 'pending',
  "rationale" TEXT NOT NULL,
  "inputPayload" TEXT NOT NULL,
  "outputPayload" TEXT,
  "errorMessage" TEXT,
  "url" TEXT,
  "retryCount" INTEGER NOT NULL DEFAULT 0,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "completedAt" DATETIME,
  "observationId" TEXT,
  "screenshotId" TEXT,
  FOREIGN KEY ("runId") REFERENCES "Run"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY ("observationId") REFERENCES "Observation"("id") ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "ApprovalRequest" (
  "id" TEXT PRIMARY KEY NOT NULL,
  "runId" TEXT NOT NULL,
  "observationId" TEXT,
  "status" TEXT NOT NULL DEFAULT 'pending',
  "reason" TEXT NOT NULL,
  "actionPayload" TEXT NOT NULL,
  "pageContext" TEXT,
  "screenshotPath" TEXT,
  "requestedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "resolvedAt" DATETIME,
  "resolutionNote" TEXT,
  FOREIGN KEY ("runId") REFERENCES "Run"("id") ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY ("observationId") REFERENCES "Observation"("id") ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "ExtractionArtifact" (
  "id" TEXT PRIMARY KEY NOT NULL,
  "runId" TEXT NOT NULL,
  "kind" TEXT NOT NULL,
  "label" TEXT NOT NULL,
  "content" TEXT NOT NULL,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY ("runId") REFERENCES "Run"("id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "FinalOutcome" (
  "id" TEXT PRIMARY KEY NOT NULL,
  "runId" TEXT NOT NULL UNIQUE,
  "status" TEXT NOT NULL,
  "summary" TEXT NOT NULL,
  "structuredData" TEXT,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY ("runId") REFERENCES "Run"("id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "ErrorEvent" (
  "id" TEXT PRIMARY KEY NOT NULL,
  "runId" TEXT NOT NULL,
  "code" TEXT NOT NULL,
  "message" TEXT NOT NULL,
  "details" TEXT,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY ("runId") REFERENCES "Run"("id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "Setting" (
  "id" TEXT PRIMARY KEY NOT NULL,
  "key" TEXT NOT NULL UNIQUE,
  "value" TEXT NOT NULL,
  "description" TEXT,
  "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS "Observation_runId_idx" ON "Observation"("runId");
CREATE INDEX IF NOT EXISTS "Screenshot_runId_idx" ON "Screenshot"("runId");
CREATE INDEX IF NOT EXISTS "AgentAction_runId_idx" ON "AgentAction"("runId");
CREATE INDEX IF NOT EXISTS "ApprovalRequest_runId_idx" ON "ApprovalRequest"("runId");
CREATE INDEX IF NOT EXISTS "ExtractionArtifact_runId_idx" ON "ExtractionArtifact"("runId");
CREATE INDEX IF NOT EXISTS "ErrorEvent_runId_idx" ON "ErrorEvent"("runId");
`;

execFileSync("sqlite3", [databasePath], {
  input: sql,
  stdio: ["pipe", "inherit", "inherit"],
});

console.log(`Initialized SQLite database at ${databasePath}`);
