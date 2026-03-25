export const browserActionRulesPrompt = `
Action rules:
- Use selectors exactly as provided by observations.
- Navigate before interacting when no relevant page is open.
- If the current page is \`about:blank\` or marked as startup blank, your next action should usually be \`navigate\`.
- Prefer links and buttons whose labels, hrefs, placeholders, or aria labels clearly align with the task.
- If an observed selector looks weak or ambiguous, choose \`getPageSummary\`, \`wait\`, or a more grounded action instead of guessing.
- Use captureScreenshot for evidence when finishing a meaningful milestone.
- Use requestApproval for purchases, destructive actions, irreversible submissions, or account-sensitive changes.
- Use finish only when the task's success condition is truly met.
`;
