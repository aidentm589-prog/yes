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

function normalizePlannerDecision(raw: Record<string, unknown>) {
  const actionJson = typeof raw.actionJson === "string" ? raw.actionJson : "";
  const action = JSON.parse(actionJson) as Record<string, unknown>;

  return {
    rationale: raw.rationale,
    completionSignal: raw.completionSignal,
    action,
  };
}

export async function decideNextAction(input: PlannerInput): Promise<PlannerDecision> {
  const env = getEnv();
  if (env.OPERATOR_PLANNER_PROVIDER === "ollama") {
    return decideNextActionWithOllama(input);
  }

  return decideNextActionWithOpenAI(input);
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

  return plannerDecisionSchema.parse(
    normalizePlannerDecision(JSON.parse(toolCall.arguments) as Record<string, unknown>),
  );
}

async function decideNextActionWithOllama(input: PlannerInput): Promise<PlannerDecision> {
  const instructions = buildPlannerPrompt(input.workflowGuidance);
  const prompt = [
    instructions,
    "Return JSON only.",
    "The JSON must have this exact shape:",
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
    "For requestApproval include: kind, reason, actionPayload.",
    "For finish include: kind, summary, optional structuredData.",
    "Do not wrap the JSON in markdown.",
    JSON.stringify(
      {
        goal: input.goal,
        pendingApproval: input.pendingApproval,
        memory: input.memory,
        observation: input.observation,
      },
      null,
      2,
    ),
  ].join("\n\n");

  const raw = await generateWithOllama(prompt);
  return plannerDecisionSchema.parse(JSON.parse(raw));
}
