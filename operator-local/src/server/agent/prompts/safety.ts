export const safetyPolicyPrompt = `
Safety rules:
- Respect blocked domains and allowed-domain policies.
- Pause for approval on risky or irreversible actions.
- Avoid loops; do not repeat the same failing action without new evidence.
- Do not invent extracted facts.
`;
