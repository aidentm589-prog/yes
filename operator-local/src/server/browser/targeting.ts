import type { InteractiveElement, ObservationSnapshot } from "@/types/operator";

type CandidateActionHint = {
  kind: "click" | "type" | "selectOption" | "navigate" | "getPageSummary";
  selector?: string;
  url?: string;
  reason: string;
  score: number;
};

const consentKeywords = [
  "accept",
  "agree",
  "allow",
  "continue",
  "got it",
  "ok",
  "close",
  "dismiss",
];

const blockerKeywords = [
  "cookie",
  "privacy",
  "terms",
  "conditions",
  "consent",
  "feedback",
  "sign in",
  "subscribe",
  "newsletter",
];

function normalizeText(value: string | null | undefined) {
  return (value ?? "").replace(/\s+/g, " ").trim().toLowerCase();
}

function candidateLabel(element: InteractiveElement) {
  return normalizeText(
    element.text || element.ariaLabel || element.name || element.placeholder || element.href || "",
  );
}

export function detectBarriers(observation: ObservationSnapshot) {
  const haystack = `${observation.title} ${observation.summary} ${observation.visibleText}`.toLowerCase();
  const barriers = new Set<string>();

  if (blockerKeywords.some((keyword) => haystack.includes(keyword))) {
    barriers.add("overlay_or_banner");
  }
  if (/sign in|log in|create account/.test(haystack)) {
    barriers.add("auth_gate");
  }
  if (/feedback|survey|how relevant is this ad/.test(haystack)) {
    barriers.add("feedback_modal");
  }
  if (/cookie|privacy/.test(haystack)) {
    barriers.add("cookie_banner");
  }
  if (/terms|conditions|agree/.test(haystack)) {
    barriers.add("terms_gate");
  }

  return Array.from(barriers);
}

function scoreElementForGoal(element: InteractiveElement, goal: string, barriers: string[]) {
  const label = candidateLabel(element);
  const goalText = goal.toLowerCase();
  let score = 0;
  const reasons: string[] = [];

  if (element.disabled) {
    return { score: -100, reason: "Disabled control" };
  }

  if (barriers.length && consentKeywords.some((keyword) => label.includes(keyword))) {
    score += 10;
    reasons.push("Matches a likely blocker-dismissal control");
  }

  const goalWords = goalText.split(/\W+/).filter((word) => word.length > 2);
  const overlap = goalWords.filter((word) => label.includes(word));
  if (overlap.length) {
    score += overlap.length * 4;
    reasons.push(`Matches goal words: ${overlap.slice(0, 3).join(", ")}`);
  }

  if (/headline|news|top stories|top headlines/.test(goalText) && /(world|politics|business|us|latest|news)/.test(label)) {
    score += 5;
    reasons.push("Looks related to news navigation");
  }

  if (element.tag === "button") {
    score += 2;
  }
  if (element.role === "button") {
    score += 1;
  }
  if (element.selectorSource === "id" || element.selectorSource === "data-testid") {
    score += 2;
    reasons.push("Has a relatively stable selector");
  }

  return {
    score,
    reason: reasons.join("; ") || "Visible interactive control",
  };
}

export function buildSuggestedActions(
  observation: ObservationSnapshot,
  goal: string,
): CandidateActionHint[] {
  const barriers = detectBarriers(observation);
  const candidates = observation.interactiveMap
    .map((element) => {
      const { score, reason } = scoreElementForGoal(element, goal, barriers);
      return {
        kind: "click" as const,
        selector: element.selector,
        reason,
        score,
      };
    })
    .filter((candidate) => candidate.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 6);

  if (!candidates.length && observation.startupBlank) {
    return [
      {
        kind: "navigate",
        reason: "The browser is still on about:blank, so navigation is required first.",
        score: 10,
      },
    ];
  }

  if (!candidates.length && observation.visibleText.trim().length > 50) {
    return [
      {
        kind: "getPageSummary",
        reason: "The page already contains useful readable text and may be ready to summarize.",
        score: 5,
      },
    ];
  }

  return candidates;
}

export function derivePageState(observation: ObservationSnapshot) {
  const barriers = detectBarriers(observation);
  if (observation.startupBlank) {
    return "startup_blank";
  }
  if (barriers.includes("cookie_banner") || barriers.includes("feedback_modal")) {
    return "blocked_by_overlay";
  }
  if (barriers.includes("terms_gate")) {
    return "awaiting_terms_acknowledgement";
  }
  if (observation.interactiveMap.some((element) => ["input", "select", "textarea"].includes(element.tag))) {
    return "form_step";
  }
  if (observation.visibleText.trim().length > 100) {
    return "content_page";
  }
  return "interactive_page";
}
