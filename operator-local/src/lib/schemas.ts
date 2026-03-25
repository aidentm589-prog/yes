import { z } from "zod";

export const workflowModeSchema = z.enum([
  "general_browser_task",
  "extract_and_summarize",
  "compare_options",
  "draft_form_fill",
]);

export const navigateActionSchema = z.object({
  kind: z.literal("navigate"),
  url: z.string().url(),
});

export const clickActionSchema = z.object({
  kind: z.literal("click"),
  selector: z.string().min(1),
});

export const typeActionSchema = z.object({
  kind: z.literal("type"),
  selector: z.string().min(1),
  text: z.string(),
});

export const selectOptionActionSchema = z.object({
  kind: z.literal("selectOption"),
  selector: z.string().min(1),
  value: z.string().min(1),
});

export const pressKeyActionSchema = z.object({
  kind: z.literal("pressKey"),
  key: z.string().min(1),
});

export const scrollActionSchema = z.object({
  kind: z.literal("scroll"),
  direction: z.enum(["up", "down"]),
  amount: z.number().int().min(100).max(3000),
});

export const waitActionSchema = z.object({
  kind: z.literal("wait"),
  ms: z.number().int().min(100).max(10_000),
});

export const getPageSummaryActionSchema = z.object({
  kind: z.literal("getPageSummary"),
});

export const extractTextActionSchema = z.object({
  kind: z.literal("extractText"),
  selector: z.string().min(1),
  label: z.string().min(1),
});

export const captureScreenshotActionSchema = z.object({
  kind: z.literal("captureScreenshot"),
  label: z.string().min(1),
});

export const requestApprovalActionSchema = z.object({
  kind: z.literal("requestApproval"),
  reason: z.string().min(1),
  actionPayload: z.record(z.string(), z.unknown()),
});

export const finishActionSchema = z.object({
  kind: z.literal("finish"),
  summary: z.string().min(1),
  structuredData: z.record(z.string(), z.unknown()).optional(),
});

export const browserActionSchema = z.discriminatedUnion("kind", [
  navigateActionSchema,
  clickActionSchema,
  typeActionSchema,
  selectOptionActionSchema,
  pressKeyActionSchema,
  scrollActionSchema,
  waitActionSchema,
  getPageSummaryActionSchema,
  extractTextActionSchema,
  captureScreenshotActionSchema,
  requestApprovalActionSchema,
  finishActionSchema,
]);

export const plannerDecisionSchema = z.object({
  rationale: z.string().min(1),
  action: browserActionSchema,
  completionSignal: z.enum(["continue", "needs_approval", "done"]).default("continue"),
});

export const createRunSchema = z.object({
  prompt: z.string().min(10).max(4_000),
  workflowMode: workflowModeSchema.optional(),
});

export const approvalDecisionSchema = z.object({
  note: z.string().max(1_000).optional(),
});

export type BrowserAction = z.infer<typeof browserActionSchema>;
export type PlannerDecision = z.infer<typeof plannerDecisionSchema>;
export type CreateRunInput = z.infer<typeof createRunSchema>;
