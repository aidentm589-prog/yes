import { plannerDecisionSchema, type PlannerDecision } from "@/lib/schemas";
import { getEnv } from "@/lib/env";
import { generateWithOllama } from "@/lib/ollama";
import { getOpenAIClient } from "@/lib/openai";
import type { ObservationSnapshot, RunMemory } from "@/types/operator";

import { buildPlannerPrompt } from "@/server/agent/prompts/planner";

type PlannerInput = {
  model: string;
  reasoningEffort: "low" | "medium" | "high";
  workflowGuidance: string;
  goal: string;
  observation: ObservationSnapshot;
  memory: RunMemory;
  pendingApproval: boolean;
};

const plannerTool = {
  type: "function",
  name: "propose_browser_action",
  description: "Choose the next browser action for the current run.",
  strict: true,
  parameters: {
    type: "object",
    additionalProperties: false,
    required: ["rationale", "completionSignal", "actionJson"],
    properties: {
      rationale: { type: "string" },
      completionSignal: {
        type: "string",
        enum: ["continue", "needs_approval", "done"],
      },
      actionJson: { type: "string" },
    },
  },
} as const;

class PlannerError extends Error {
  details?: Record<string, unknown>;

  constructor(message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "PlannerError";
    this.details = details;
  }
}

export async function decideNextAction(input: PlannerInput): Promise<PlannerDecision> {
  const env = getEnv();
  if (env.OPERATOR_PLANNER_PROVIDER === "ollama") {
    return decideNextActionWithOllama(input);
  }

  return decideNextActionWithOpenAI(input);
}

function stripMarkdownFence(raw: string) {
  return raw.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
}

export function extractJsonObject(raw: string) {
  const cleaned = stripMarkdownFence(raw);
  const firstBrace = cleaned.indexOf("{");
  const lastBrace = cleaned.lastIndexOf("}");

  if (firstBrace === -1 || lastBrace === -1 || lastBrace <= firstBrace) {
    return { jsonText: cleaned, recovered: false };
  }

  const sliced = cleaned.slice(firstBrace, lastBrace + 1);
  return { jsonText: sliced, recovered: sliced !== cleaned };
}

function normalizePlannerDecision(
  raw: Record<string, unknown>,
  provider: "openai" | "ollama",
  rawOutput: string,
  recoveredJson = false,
) {
  const actionValue =
    typeof raw.actionJson === "string"
      ? JSON.parse(raw.actionJson)
      : ((raw.action ?? raw.actionPayload) as Record<string, unknown>);

  return plannerDecisionSchema.parse({
    rationale: raw.rationale,
    completionSignal: raw.completionSignal,
    action: actionValue,
    plannerMeta: {
      provider,
      rawOutput,
      recoveredJson,
    },
  });
}

export function parsePlannerResponse(
  rawOutput: string,
  provider: "openai" | "ollama",
  options?: { actionJsonString?: boolean },
) {
  const { jsonText, recovered } = extractJsonObject(rawOutput);

  try {
    const parsed = JSON.parse(jsonText) as Record<string, unknown>;
    const normalized = options?.actionJsonString
      ? normalizePlannerDecision(parsed, provider, rawOutput, recovered)
      : plannerDecisionSchema.parse({
          ...parsed,
          action:
            typeof parsed.actionJson === "string"
              ? JSON.parse(parsed.actionJson)
              : parsed.action,
          plannerMeta: {
            provider,
            rawOutput,
            recoveredJson: recovered,
          },
        });

    return normalized;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown planner parse error";
    throw new PlannerError("Planner returned invalid JSON output.", {
      provider,
      rawOutput,
      jsonText,
      validationError: message,
    });
  }
}

async function decideNextActionWithOpenAI(input: PlannerInput): Promise<PlannerDecision> {
  const client = getOpenAIClient();
  const instructions = buildPlannerPrompt(input.workflowGuidance);

  const response = await client.responses.create({
    model: input.model,
    reasoning: {
      effort: input.reasoningEffort,
    },
    tool_choice: {
      type: "function",
      name: "propose_browser_action",
    },
    tools: [plannerTool],
    input: [
      {
        role: "system",
        content: [{ type: "input_text", text: instructions }],
      },
      {
        role: "user",
        content: [
          {
            type: "input_text",
            text: JSON.stringify(
              {
                goal: input.goal,
                pendingApproval: input.pendingApproval,
                memory: input.memory,
                observation: input.observation,
              },
              null,
              2,
            ),
          },
        ],
      },
    ],
  });

  const toolCall = response.output.find((item) => item.type === "function_call");
  if (!toolCall || toolCall.type !== "function_call") {
    throw new Error("Planner did not return a function call.");
  }

  try {
    return normalizePlannerDecision(
      JSON.parse(toolCall.arguments) as Record<string, unknown>,
      "openai",
      toolCall.arguments,
      false,
    );
  } catch (error) {
    if (error instanceof PlannerError) {
      throw error;
    }
    const message = error instanceof Error ? error.message : "Unknown OpenAI planner error";
    throw new PlannerError("OpenAI planner output could not be normalized.", {
      provider: "openai",
      rawOutput: toolCall.arguments,
      validationError: message,
    });
  }
}

async function decideNextActionWithOllama(input: PlannerInput): Promise<PlannerDecision> {
  const instructions = buildPlannerPrompt(input.workflowGuidance);
  const payload = {
    goal: input.goal,
    pendingApproval: input.pendingApproval,
    memory: input.memory,
    observation: input.observation,
  };
  const prompt = [
    "Return JSON only.",
    "Use this exact top-level shape:",
    JSON.stringify(
      {
        rationale: "short reason",
        completionSignal: "continue",
        action: {
          kind: "navigate",
          url: "https://example.com",
        },
      },
      null,
      2,
    ),
    "Allowed action kinds: navigate, click, type, selectOption, pressKey, scroll, wait, getPageSummary, extractText, captureScreenshot, requestApproval, finish.",
    "For requestApproval include kind, reason, and actionPayload.",
    "For finish include kind, summary, and optional structuredData.",
    "If the observation is startupBlank or the url is about:blank, navigate first unless the goal is already complete.",
    "Do not wrap the response in markdown or add commentary outside the JSON object.",
    JSON.stringify(payload, null, 2),
  ].join("\n\n");

  const raw = await generateWithOllama(prompt, instructions);

  try {
    return parsePlannerResponse(raw, "ollama");
  } catch (error) {
    if (!(error instanceof PlannerError)) {
      throw error;
    }

    const retryPrompt = [
      prompt,
      "Your last response could not be parsed or validated.",
      `Validation error: ${error.details?.validationError ?? error.message}`,
      "Return one corrected JSON object only.",
    ].join("\n\n");
    const retriedRaw = await generateWithOllama(retryPrompt, instructions);
    return parsePlannerResponse(retriedRaw, "ollama");
  }
}
