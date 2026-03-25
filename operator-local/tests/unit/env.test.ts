import { getEnv } from "@/lib/env";

describe("getEnv", () => {
  it("parses defaults and booleans", () => {
    const env = getEnv({
      DATABASE_URL: "file:./prisma/dev.db",
      OPENAI_MODEL: "gpt-5.2",
      OPENAI_REASONING_EFFORT: "medium",
      PLAYWRIGHT_HEADLESS: "true",
      PLAYWRIGHT_SLOW_MO: "25",
      OPERATOR_DEFAULT_MAX_STEPS: "8",
      OPERATOR_DEFAULT_MAX_RETRIES: "3",
      OPERATOR_DEFAULT_TIMEOUT_MS: "120000",
      OPERATOR_SCREENSHOT_EVERY_STEP: "false",
      OPERATOR_INVOKE_STEP_BUDGET: "2",
      OPERATOR_STORAGE_DIR: "./runtime",
      OPERATOR_ALLOWED_DOMAINS: "",
      OPERATOR_BLOCKED_DOMAINS: "",
    });

    expect(env.PLAYWRIGHT_HEADLESS).toBe(true);
    expect(env.PLAYWRIGHT_SLOW_MO).toBe(25);
    expect(env.OPERATOR_DEFAULT_MAX_STEPS).toBe(8);
  });
});
