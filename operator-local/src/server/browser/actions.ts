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

  await locator.waitFor({ state: "attached", timeout: 1_500 }).catch(() => null);

  if ((await locator.count()) === 0) {
    await page.waitForTimeout(500);
    if ((await locator.count()) === 0) {
      throw new Error(`Selector not found: ${selector}`);
    }
  }

  await locator.scrollIntoViewIfNeeded().catch(() => null);

  const disabled = await locator
    .evaluate((element) => {
      const html = element as HTMLElement;
      return (
        html.hasAttribute("disabled") ||
        html.getAttribute("aria-disabled") === "true"
      );
    })
    .catch(() => false);

  if (disabled) {
    throw new Error(`Selector is disabled: ${selector}`);
  }

  return locator;
}

function isRecoverableActionError(error: unknown) {
  return (
    isClosedTargetError(error) ||
    (error instanceof Error &&
      /Selector not found|Timeout|Navigation.*interrupted|net::ERR|Target closed/i.test(error.message))
  );
}

async function withActionRecovery<T>(runId: string, actionName: string, work: () => Promise<T>): Promise<T> {
  try {
    return await work();
  } catch (error) {
    if (!isRecoverableActionError(error)) {
      throw error;
    }

    const { page } = await resetBrowserSession(runId);
    await page.waitForTimeout(250);

    try {
      return await work();
    } catch (retryError) {
      const retryMessage = retryError instanceof Error ? retryError.message : String(retryError);
      throw new Error(`${actionName} failed after recovery attempt: ${retryMessage}`);
    }
  }
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
  switch (action.kind) {
    case "navigate": {
      return withActionRecovery(runId, "navigate", async () => {
        const { page } = await getBrowserSession(runId);
        const url = new URL(action.url);
        if (!["http:", "https:"].includes(url.protocol)) {
          throw new Error(`Unsupported navigation protocol: ${url.protocol}`);
        }
        await page.goto(action.url, { waitUntil: "domcontentloaded", timeout: 15_000 });
        return { ok: true, url: page.url() };
      });
    }
    case "click": {
      return withActionRecovery(runId, "click", async () => {
        const locator = await ensureSelector(runId, action.selector);
        await locator.click({ timeout: 5_000 });
        return { ok: true };
      });
    }
    case "type": {
      return withActionRecovery(runId, "type", async () => {
        const locator = await ensureSelector(runId, action.selector);
        await locator.fill(action.text, { timeout: 5_000 });
        return { ok: true };
      });
    }
    case "selectOption": {
      return withActionRecovery(runId, "selectOption", async () => {
        const locator = await ensureSelector(runId, action.selector);
        await locator.selectOption(action.value, { timeout: 5_000 });
        return { ok: true };
      });
    }
    case "pressKey": {
      return withActionRecovery(runId, "pressKey", async () => {
        const { page } = await getBrowserSession(runId);
        await page.keyboard.press(action.key);
        return { ok: true };
      });
    }
    case "scroll": {
      return withActionRecovery(runId, "scroll", async () => {
        const { page } = await getBrowserSession(runId);
        const amount = action.direction === "down" ? action.amount : action.amount * -1;
        await page.mouse.wheel(0, amount);
        return { ok: true };
      });
    }
    case "wait": {
      return withActionRecovery(runId, "wait", async () => {
        const { page } = await getBrowserSession(runId);
        await page.waitForTimeout(action.ms);
        return { ok: true };
      });
    }
    case "getPageSummary": {
      return withActionRecovery(runId, "getPageSummary", async () => {
        const { page } = await getBrowserSession(runId);
        return {
          ok: true,
          observation: await inspectPage(page, "checkpoint"),
        };
      });
    }
    case "extractText": {
      return withActionRecovery(runId, "extractText", async () => {
        const locator = await ensureSelector(runId, action.selector);
        const text = (await locator.textContent())?.trim() ?? "";
        return {
          ok: true,
          text,
          label: action.label,
        };
      });
    }
    case "captureScreenshot": {
      const screenshotPath = await captureRunScreenshot(runId, action.label);
      return { ok: true, screenshotPath };
    }
  }
}
