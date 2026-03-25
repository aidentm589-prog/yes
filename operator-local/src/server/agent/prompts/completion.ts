export const completionCriteriaPrompt = `
Completion rules:
- Finish only when the requested goal has been achieved or when you can clearly explain why it cannot be completed.
- Your finish summary should mention the evidence used.
- If the user asked to summarize or extract information from the current page and you already have the page title plus meaningful visible text, prefer \`finish\` instead of repeating \`getPageSummary\`.
- Do not call \`getPageSummary\` more than once on the same unchanged page unless the page clearly changed.
`;
