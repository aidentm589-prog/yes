import type OpenAI from "openai";

import { plannerDecisionSchema, type PlannerDecision } from "@/lib/schemas";
import { imageFileToDataUrl } from "@/lib/storage";
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

const plannerTool: OpenAI.Responses.FunctionTool = {
  type: "function",
  name: "propose_browser_action",
  description: "Choose the next browser action for the current run.",
  strict: true,
  parameters: {
    type: "object",
    additionalProperties: false,
    required: ["rationale", "completionSignal", "action"],
    properties: {
      rationale: { type: "string" },
      completionSignal: {
        type: "string",
        enum: ["continue", "needs_approval", "done"],
      },
      action: {
        type: "object",
        additionalProperties: false,
        required: ["kind"],
        properties: {
          kind: {
            type: "string",
            enum: [
              "navigate",
              "click",
              "type",
              "selectOption",
              "pressKey",
              "scroll",
              "wait",
              "getPageSummary",
              "extractText",
              "captureScreenshot",
              "requestApproval",
              "finish",
            ],
          },
          url: { type: "string" },
          selector: { type: "string" },
          text: { type: "string" },
          value: { type: "string" },
          key: { type: "string" },
          direction: { type: "string", enum: ["up", "down"] },
          amount: { type: "number" },
          ms: { type: "number" },
          label: { type: "string" },
          reason: { type: "string" },
          actionPayload: {
            type: "object",
            additionalProperties: true,
          },
          summary: { type: "string" },
          structuredData: {
            type: "object",
            additionalProperties: true,
          },
        },
      },
    },
  },
};

function getFunctionCall(response: OpenAI.Responses.Response) {
  return response.output.find((item) => item.type === "function_call");
}

export async function decideNextAction(input: PlannerInput): Promise<PlannerDecision> {
  const client = getOpenAIClient();
  const instructions = buildPlannerPrompt(input.workflowGuidance);
  const content: OpenAI.Responses.ResponseInputMessageContentList = [
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
  ];

  if (input.observation.screenshotPath) {
    content.push({
      type: "input_image",
      image_url: await imageFileToDataUrl(input.observation.screenshotPath),
      detail: "low",
    });
  }

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
        content,
      },
    ],
  });

  const toolCall = getFunctionCall(response);
  if (!toolCall || toolCall.type !== "function_call") {
    throw new Error("Planner did not return a function call.");
  }

  return plannerDecisionSchema.parse(JSON.parse(toolCall.arguments));
}
