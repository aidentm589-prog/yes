import type { RunStatus } from "@prisma/client";

export function isTerminalStatus(status: RunStatus) {
  return ["completed", "failed", "cancelled", "timed_out"].includes(status);
}
