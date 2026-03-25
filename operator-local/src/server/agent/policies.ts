import type { BrowserAction } from "@/lib/schemas";
import { domainMatches } from "@/lib/permissions";
import type { ObservationSnapshot, PolicySnapshot } from "@/types/operator";

const riskyKeywords = [
  "buy",
  "purchase",
  "pay",
  "checkout",
  "place order",
  "submit",
  "delete",
  "remove",
  "confirm",
  "send",
  "transfer",
];

const sensitiveInputKeywords = ["password", "credit", "card", "cvv", "ssn", "social security"];

export type PolicyDecision =
  | { allowed: true; requiresApproval: false }
  | { allowed: true; requiresApproval: true; reason: string }
  | { allowed: false; reason: string };

export function validateActionAgainstPolicy(
  action: BrowserAction,
  policy: PolicySnapshot,
  observation?: ObservationSnapshot,
): PolicyDecision {
  if (action.kind === "navigate") {
    const hostname = new URL(action.url).hostname.toLowerCase();

    if (policy.blockedDomains.length > 0 && domainMatches(hostname, policy.blockedDomains)) {
      return { allowed: false, reason: `Navigation to blocked domain: ${hostname}` };
    }

    if (policy.allowedDomains.length > 0 && !domainMatches(hostname, policy.allowedDomains)) {
      return { allowed: false, reason: `Navigation outside allowlist: ${hostname}` };
    }
  }

  const haystack = JSON.stringify({
    action,
    summary: observation?.summary ?? "",
    text: observation?.visibleText ?? "",
  }).toLowerCase();

  if (
    (action.kind === "click" || action.kind === "pressKey" || action.kind === "selectOption") &&
    riskyKeywords.some((keyword) => haystack.includes(keyword))
  ) {
    return {
      allowed: true,
      requiresApproval: true,
      reason: "This interaction looks potentially irreversible or account-sensitive.",
    };
  }

  if (
    action.kind === "type" &&
    sensitiveInputKeywords.some(
      (keyword) =>
        action.selector.toLowerCase().includes(keyword) || action.text.toLowerCase().includes(keyword),
    )
  ) {
    return {
      allowed: true,
      requiresApproval: true,
      reason: "This input appears sensitive and should be reviewed before continuing.",
    };
  }

  return { allowed: true, requiresApproval: false };
}
