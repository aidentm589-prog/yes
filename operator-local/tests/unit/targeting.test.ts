import { describe, expect, it } from "vitest";

import type { ObservationSnapshot } from "@/types/operator";
import {
  buildSuggestedActions,
  derivePageState,
  detectBarriers,
} from "@/server/browser/targeting";

const baseObservation: ObservationSnapshot = {
  url: "https://example.com",
  title: "Cookie consent",
  summary: "A cookie and privacy banner is blocking the page.",
  visibleText: "We use cookies. Accept and continue.",
  headings: ["Cookie settings"],
  interactiveMap: [
    {
      selector: "button:nth-of-type(1)",
      tag: "button",
      role: null,
      text: "Accept and continue",
      name: null,
      ariaLabel: null,
      placeholder: null,
      type: "button",
      href: null,
      disabled: false,
      selectorSource: "dom-path",
    },
    {
      selector: "a:nth-of-type(1)",
      tag: "a",
      role: null,
      text: "World",
      name: null,
      ariaLabel: null,
      placeholder: null,
      type: null,
      href: "https://example.com/world",
      disabled: false,
      selectorSource: "href",
    },
  ],
  recentErrors: [],
  startupBlank: false,
  phase: "pre_action",
};

describe("targeting helpers", () => {
  it("detects blocking overlays", () => {
    expect(detectBarriers(baseObservation)).toContain("cookie_banner");
    expect(derivePageState(baseObservation)).toBe("blocked_by_overlay");
  });

  it("ranks likely blocker-dismiss controls above unrelated navigation", () => {
    const suggestions = buildSuggestedActions(
      baseObservation,
      "Open CNN and continue past the terms banner to summarize the headlines.",
    );

    expect(suggestions[0]?.kind).toBe("click");
    expect(suggestions[0]?.selector).toBe("button:nth-of-type(1)");
  });
});
