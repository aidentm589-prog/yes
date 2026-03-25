# AGENTS.md

## Purpose

This project is a local Operator-style browser agent platform. It is meant to be reusable, inspectable, and safe enough for real local experimentation. Do not reshape it into a single hardcoded demo app.

## Architecture Boundaries

- Keep the browser agent runtime modular across UI, API, orchestration, browser control, repositories, and services.
- Prefer vertical slices that keep the app runnable over broad scaffold-only changes.
- Preserve the narrow typed browser action interface.
- Keep prompts modular. Do not collapse planning, safety, completion, and approval logic into one giant prompt blob.
- Treat Playwright execution, observation capture, and persistence as first-class runtime layers.

## Safety Rules

- Never add arbitrary shell execution for the model.
- Never hardcode API keys, tokens, credentials, or private cookies.
- Always log meaningful browser actions and persist evidence where practical.
- Require approval before purchases, destructive actions, irreversible submissions, or account-sensitive changes.
- Do not pretend an action succeeded if there is no evidence from execution or observation.

## Data And Types

- Use typed Zod schemas for external inputs and planner action contracts.
- Keep Prisma models aligned with the platform concept: runs, tasks, actions, observations, screenshots, approvals, artifacts, outcomes, and errors.
- Preserve auditability. New features should extend the event trail rather than bypass it.

## Implementation Preferences

- Favor small server-side modules with clear responsibilities.
- Prefer repository/service boundaries over raw database access scattered through the app.
- Capture screenshots on important transitions, especially navigation, failure, approvals, and completion.
- Document stubs or compromises explicitly in code comments or README when a hard problem is deferred.

## Workflow Expectations

- Run lint/build/tests after meaningful changes when feasible.
- Keep the project runnable locally.
- If a future change touches safety or approval behavior, update tests and README guidance in the same change.
