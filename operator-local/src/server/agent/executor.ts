import type { BrowserAction } from "@/lib/schemas";
import { writeArtifact } from "@/lib/storage";

import { captureRunScreenshot, executeBrowserAction } from "@/server/browser/actions";
import { runRepository } from "@/server/repositories/run-repository";

export async function executeActionForRun(runId: string, action: BrowserAction) {
  if (action.kind === "finish") {
    const artifactPath = await writeArtifact(runId, "final-outcome", action);
    return {
      ok: true,
      output: {
        artifactPath,
        summary: action.summary,
        structuredData: action.structuredData ?? {},
      },
    };
  }

  if (action.kind === "requestApproval") {
    return {
      ok: true,
      output: {
        reason: action.reason,
        actionPayload: action.actionPayload,
      },
    };
  }

  const result = await executeBrowserAction(runId, action);

  if (action.kind === "extractText" && "text" in result) {
    await runRepository.createExtraction({
      runId,
      kind: "text",
      label: action.label,
      content: {
        selector: action.selector,
        text: typeof result.text === "string" ? result.text : String(result.text ?? ""),
      },
    });
  }

  if (action.kind === "captureScreenshot" && "screenshotPath" in result) {
    return {
      ok: true,
      output: result,
    };
  }

  if (action.kind === "navigate") {
    const screenshotPath = await captureRunScreenshot(runId, "navigation");
    return {
      ok: true,
      output: {
        ...result,
        screenshotPath,
      },
    };
  }

  return {
    ok: true,
    output: result,
  };
}
