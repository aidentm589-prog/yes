import { browserActionRulesPrompt } from "@/server/agent/prompts/browserRules";
import { completionCriteriaPrompt } from "@/server/agent/prompts/completion";
import { approvalEscalationPrompt } from "@/server/agent/prompts/approval";
import { safetyPolicyPrompt } from "@/server/agent/prompts/safety";
import { systemBehaviorPrompt } from "@/server/agent/prompts/system";

export function buildPlannerPrompt(workflowGuidance: string) {
  return [
    systemBehaviorPrompt.trim(),
    workflowGuidance.trim(),
    browserActionRulesPrompt.trim(),
    safetyPolicyPrompt.trim(),
    approvalEscalationPrompt.trim(),
    completionCriteriaPrompt.trim(),
  ].join("\n\n");
}
