import { appendFile, mkdir } from "node:fs/promises";
import path from "node:path";

import { getEnv } from "@/lib/env";

type LogLevel = "info" | "warn" | "error";

type LogPayload = {
  scope: string;
  message: string;
  data?: Record<string, unknown>;
};

async function writeLine(level: LogLevel, payload: LogPayload) {
  const env = getEnv();
  const logDir = path.resolve(process.cwd(), env.OPERATOR_STORAGE_DIR, "logs");
  await mkdir(logDir, { recursive: true });

  const line = JSON.stringify({
    level,
    time: new Date().toISOString(),
    ...payload,
  });

  await appendFile(path.join(logDir, "operator.log"), `${line}\n`);
}

export const logger = {
  async info(payload: LogPayload) {
    console.info(`[${payload.scope}] ${payload.message}`, payload.data ?? "");
    await writeLine("info", payload);
  },
  async warn(payload: LogPayload) {
    console.warn(`[${payload.scope}] ${payload.message}`, payload.data ?? "");
    await writeLine("warn", payload);
  },
  async error(payload: LogPayload) {
    console.error(`[${payload.scope}] ${payload.message}`, payload.data ?? "");
    await writeLine("error", payload);
  },
};
