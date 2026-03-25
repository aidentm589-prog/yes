import { validateActionAgainstPolicy } from "@/server/agent/policies";
import type { PolicySnapshot } from "@/types/operator";

const policy: PolicySnapshot = {
  allowedDomains: ["example.com"],
  blockedDomains: ["blocked.com"],
  maxSteps: 8,
  maxRetries: 2,
  timeoutMs: 120_000,
  screenshotEveryStep: false,
};

describe("validateActionAgainstPolicy", () => {
  it("blocks blocked domains", () => {
    const result = validateActionAgainstPolicy(
      { kind: "navigate", url: "https://blocked.com" },
      policy,
    );

    expect(result.allowed).toBe(false);
  });

  it("requires approval for risky click flows", () => {
    const result = validateActionAgainstPolicy(
      { kind: "click", selector: "button:nth-of-type(1)" },
      policy,
      {
        url: "https://example.com/checkout",
        title: "Checkout",
        summary: "Page includes a Place order button",
        visibleText: "Place order and pay now",
        interactiveMap: [],
        recentErrors: [],
      },
    );

    expect(result.allowed).toBe(true);
    expect("requiresApproval" in result && result.requiresApproval).toBe(true);
  });
});
