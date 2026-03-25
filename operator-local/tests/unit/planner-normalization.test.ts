import { describe, expect, it } from "vitest";

import { parsePlannerResponse } from "@/server/agent/planner";

describe("parsePlannerResponse", () => {
  it("parses a valid JSON object", () => {
    const decision = parsePlannerResponse(
      JSON.stringify({
        rationale: "Navigate first.",
        completionSignal: "continue",
        action: {
          kind: "navigate",
          url: "https://example.com",
        },
      }),
      "ollama",
    );

    expect(decision.action.kind).toBe("navigate");
  });

  it("recovers fenced JSON", () => {
    const decision = parsePlannerResponse(
      '```json\n{"rationale":"Done","completionSignal":"done","action":{"kind":"finish","summary":"done"}}\n```',
      "ollama",
    );

    expect(decision.completionSignal).toBe("done");
    expect(decision.plannerMeta?.provider).toBe("ollama");
  });

  it("throws on malformed JSON", () => {
    expect(() =>
      parsePlannerResponse('{"rationale":"bad"', "ollama"),
    ).toThrowError("Planner returned invalid JSON output.");
  });

  it("throws on invalid action shape", () => {
    expect(() =>
      parsePlannerResponse(
        JSON.stringify({
          rationale: "Try clicking.",
          completionSignal: "continue",
          action: {
            kind: "navigate",
          },
        }),
        "ollama",
      ),
    ).toThrowError("Planner returned invalid JSON output.");
  });
});
