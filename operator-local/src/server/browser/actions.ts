import path from "node:path";

import type { BrowserAction } from "@/lib/schemas";
import { ensureRunStorage } from "@/lib/storage";

import { getBrowserSession, resetBrowserSession } from "@/server/browser/playwright";
import { inspectPage } from "@/server/browser/observers";

function isClosedTargetError(error: unknown) {
  return (
    error instanceof Error &&
    /Target page, context or browser has been closed|has been closed/i.test(error.message)
  );
}

async function ensureSelector(runId: string, selector: string) {
  const { page } = await getBrowserSession(runId);
  const locator = page.locator(selector).first();

  if ((await locator.count()) === 0) {
    throw new Error(`Selector not found: ${selector}`);
  }

  return locator;
}

export async function captureRunScreenshot(runId: string, label: string) {
  const storage = await ensureRunStorage(runId);
  const filePath = path.join(
    storage.screenshotDir,
    `${new Date().toISOString().replace(/[:.]/g, "-")}-${label.replace(/[^a-z0-9-_]+/gi, "-")}.png`,
  );

  try {
    const { page } = await getBrowserSession(runId);
    await page.screenshot({
      path: filePath,
      fullPage: true,
    });
  } catch (error) {
    if (!isClosedTargetError(error)) {
      throw error;
    }

    const { page } = await resetBrowserSession(runId);
    await page.screenshot({
      path: filePath,
      fullPage: true,
    });
  }

  return filePath;
}

export async function executeBrowserAction(runId: string, action: Exclude<BrowserAction, { kind: "requestApproval" | "finish" }>) {
  const { page } = await getBrowserSession(runId);

  switch (action.kind) {
    case "navigate": {
      await page.goto(action.url, { waitUntil: "domcontentloaded" });
      return { ok: true, url: page.url() };
    }
    case "click": {
      const locator = await ensureSelector(runId, action.selector);
      await locator.click();
      return { ok: true };
    }
    case "type": {
      const locator = await ensureSelector(runId, action.selector);
      await locator.fill(action.text);
      return { ok: true };
    }
    case "selectOption": {
      const locator = await ensureSelector(runId, action.selector);
      await locator.selectOption(action.value);
      return { ok: true };
    }
    case "pressKey": {
      await page.keyboard.press(action.key);
      return { ok: true };
    }
    case "scroll": {
      const amount = action.direction === "down" ? action.amount : action.amount * -1;
      await page.mouse.wheel(0, amount);
      return { ok: true };
    }
    case "wait": {
      await page.waitForTimeout(action.ms);
      return { ok: true };
    }
    case "getPageSummary": {
      return {
        ok: true,
        observation: await inspectPage(page),
      };
    }
    case "extractText": {
      const locator = await ensureSelector(runId, action.selector);
      const text = (await locator.textContent())?.trim() ?? "";
      return {
        ok: true,
        text,
        label: action.label,
      };
    }
    case "captureScreenshot": {
      const screenshotPath = await captureRunScreenshot(runId, action.label);
      return { ok: true, screenshotPath };
    }
  }
}
