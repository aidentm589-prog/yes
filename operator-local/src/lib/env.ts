import { z } from "zod";

const envSchema = z.object({
  OPERATOR_PLANNER_PROVIDER: z.enum(["openai", "ollama"]).default("ollama"),
  OPENAI_API_KEY: z.string().optional(),
  OPENAI_MODEL: z.string().default("gpt-5.2"),
  OPENAI_REASONING_EFFORT: z.enum(["low", "medium", "high"]).default("medium"),
  OLLAMA_BASE_URL: z.string().url().default("http://127.0.0.1:11434"),
  OLLAMA_MODEL: z.string().default("qwen2.5:7b-instruct"),
  DATABASE_URL: z.string().min(1).default("file:./prisma/dev.db"),
  PLAYWRIGHT_HEADLESS: z
    .string()
    .default("false")
    .transform((value) => value === "true"),
  PLAYWRIGHT_SLOW_MO: z.coerce.number().int().min(0).default(0),
  OPERATOR_STORAGE_DIR: z.string().default("./runtime"),
  OPERATOR_ALLOWED_DOMAINS: z.string().default(""),
  OPERATOR_BLOCKED_DOMAINS: z.string().default(""),
  OPERATOR_DEFAULT_MAX_STEPS: z.coerce.number().int().min(1).default(12),
  OPERATOR_DEFAULT_MAX_RETRIES: z.coerce.number().int().min(0).default(2),
  OPERATOR_DEFAULT_TIMEOUT_MS: z.coerce.number().int().min(10_000).default(300_000),
  OPERATOR_SCREENSHOT_EVERY_STEP: z
    .string()
    .default("false")
    .transform((value) => value === "true"),
  OPERATOR_INVOKE_STEP_BUDGET: z.coerce.number().int().min(1).max(10).default(3),
});

export type AppEnv = z.infer<typeof envSchema>;

let cachedEnv: AppEnv | null = null;

export function getEnv(overrides?: Partial<Record<keyof AppEnv, unknown>>): AppEnv {
  if (!overrides && cachedEnv) {
    return cachedEnv;
  }

  const source = {
    ...process.env,
    ...overrides,
  };

  const parsed = envSchema.parse(source);

  if (!overrides) {
    cachedEnv = parsed;
  }

  return parsed;
}

export function assertOpenAIConfigured() {
  const env = getEnv();

  if (!env.OPENAI_API_KEY) {
    throw new Error("OPENAI_API_KEY is required to run the planner.");
  }

  return env.OPENAI_API_KEY;
}
