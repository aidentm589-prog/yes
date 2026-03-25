import { getEnv } from "@/lib/env";
import { normalizeDomainList } from "@/lib/permissions";
import type { PolicySnapshot } from "@/types/operator";

import { settingsRepository } from "@/server/repositories/settings-repository";

export function buildPolicySnapshot(): PolicySnapshot {
  const env = getEnv();

  return {
    allowedDomains: normalizeDomainList(env.OPERATOR_ALLOWED_DOMAINS),
    blockedDomains: normalizeDomainList(env.OPERATOR_BLOCKED_DOMAINS),
    maxSteps: env.OPERATOR_DEFAULT_MAX_STEPS,
    maxRetries: env.OPERATOR_DEFAULT_MAX_RETRIES,
    timeoutMs: env.OPERATOR_DEFAULT_TIMEOUT_MS,
    screenshotEveryStep: env.OPERATOR_SCREENSHOT_EVERY_STEP,
  };
}

export async function ensureDefaultSettings() {
  const env = getEnv();

  await settingsRepository.ensureDefaults([
    {
      key: "planner_provider",
      value: { value: env.OPERATOR_PLANNER_PROVIDER },
      description: "Planner provider used by the runtime.",
    },
    {
      key: "model",
      value: {
        value: env.OPERATOR_PLANNER_PROVIDER === "ollama" ? env.OLLAMA_MODEL : env.OPENAI_MODEL,
      },
      description: "Default model used by the planner.",
    },
    {
      key: "reasoning_effort",
      value: { value: env.OPENAI_REASONING_EFFORT },
      description: "Default reasoning effort for Responses requests.",
    },
    {
      key: "policy",
      value: buildPolicySnapshot(),
      description: "Default policy caps and domain rules.",
    },
  ]);

  return settingsRepository.list();
}
