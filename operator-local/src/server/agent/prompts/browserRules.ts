export const browserActionRulesPrompt = `
Action rules:
- Use selectors exactly as provided by observations.
- Navigate before interacting when no relevant page is open.
- Use captureScreenshot for evidence when finishing a meaningful milestone.
- Use requestApproval for purchases, destructive actions, irreversible submissions, or account-sensitive changes.
- Use finish only when the task's success condition is truly met.
`;
