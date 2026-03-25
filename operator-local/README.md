# Operator Local

Operator Local is a local, inspectable, Operator-style browser agent platform built with Next.js, TypeScript, Playwright, Prisma, SQLite, and pluggable planner backends. It is designed to accept plain-English browser tasks, plan multi-step actions, operate a local browser through a narrow typed action layer, capture screenshots and observations, pause for risky approvals, and preserve a full audit trail for replay and debugging.

## What It Does Today

- Accepts arbitrary browser-task prompts from a local web console
- Persists runs, tasks, actions, observations, screenshots, approvals, artifacts, outcomes, and errors
- Uses a server-side orchestration loop with either OpenAI Responses or a local Ollama planner
- Controls a local Chromium session via Playwright
- Captures screenshots and observation summaries as evidence
- Surfaces run history, live status, approvals, and final outcomes in the UI
- Provides starter workflow framing for general browsing, extraction, comparison, and draft form fill

## Realistic Scope And Limitations

- This is not a replica of OpenAI’s internal Operator stack. It is a practical local equivalent built from public APIs and local automation tools.
- The MVP is browser-focused. It does not expose arbitrary shell execution to the model.
- Approval gating is intentionally conservative and pauses on risky or irreversible interactions.
- Playwright is the execution path for the MVP. The architecture leaves room for future OpenAI `computer` tool experiments, but that is not the main runtime path yet.
- The checked-in SQLite bootstrap uses a local initializer script because Prisma schema push is unstable in this specific local environment. Prisma still provides the client, schema, and typed data access layer.
- The cheapest and recommended local setup uses `Ollama` as the planner provider so the browser agent can run without OpenAI API quota.

## Project Structure

```text
operator-local/
  prisma/
  scripts/
  src/
    app/
    components/
    lib/
    server/
    types/
  tests/
```

## Setup

1. Install dependencies:

```bash
cd "/Users/aidenmessier/Documents/New project/operator-local"
npm install --cache ../.npm-cache
```

2. Create a local env file from `.env.example`.

3. For the free local path, install and start Ollama:

```bash
brew install ollama
ollama serve
ollama pull qwen2.5:7b-instruct
```

4. Set at least:

```bash
OPERATOR_PLANNER_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
DATABASE_URL="file:./prisma/dev.db"
PLAYWRIGHT_HEADLESS=false
```

If you want to use OpenAI instead, switch `OPERATOR_PLANNER_PROVIDER=openai` and provide `OPENAI_API_KEY`.

5. Initialize the local SQLite database:

```bash
npm run db:push
```

6. Install Chromium for Playwright if needed:

```bash
npm run playwright:install
```

7. Start the app:

```bash
npm run dev
```

## How Approvals Work

- The planner proposes typed actions such as `navigate`, `click`, `type`, `extractText`, and `finish`.
- Before execution, a policy layer checks blocked domains, allowlists, caps, and sensitive action patterns.
- Risky actions create an `ApprovalRequest`, attach page context and evidence, and move the run into `waiting_for_approval`.
- You can approve or reject from the run detail page or the dedicated approvals panel.

## Testing

```bash
npm run lint
DATABASE_URL="file:./prisma/dev.db" npm run build
npm test
```

Playwright e2e scaffolding is present under `tests/e2e/` for future browser-console coverage.

## Current Limitations

- The live run loop currently advances through polling and repeated `continue` calls rather than websocket streaming.
- Browser observation is lightweight and mixes DOM summaries with screenshot evidence; it is not a full computer-vision stack.
- The planner uses one-step-at-a-time tool selection rather than a more advanced long-horizon planner with subgoals and recovery trees.
- The Ollama provider currently uses prompt-based JSON planning rather than native tool calling.
- The current policy engine uses rule-based keyword escalation for approval detection and should be expanded over time.
- SQLite and local filesystem storage are intended for local experimentation, not multi-user production deployment.

## Roadmap

- Add richer DOM and screenshot grounding for harder websites
- Add explicit replay mode for recorded action timelines
- Expand workflow packs for research, scheduling, shopping comparison, and account flows
- Add streaming run updates and richer console diagnostics
- Add a clean adapter for OpenAI `computer` tool experimentation

## Useful Commands

```bash
npm run dev
npm run lint
npm run build
npm run db:push
npm run db:prisma-push
npm test
```
