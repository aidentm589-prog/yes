import { chromium, type BrowserContext, type Page } from "playwright";

import { getEnv } from "@/lib/env";
import { ensureRunStorage } from "@/lib/storage";

type BrowserSession = {
  context: BrowserContext;
  page: Page;
};

const sessions = new Map<string, BrowserSession>();

function isSessionUsable(session: BrowserSession) {
  return session.context.browser()?.isConnected() !== false && !session.page.isClosed();
}

async function createBrowserSession(runId: string): Promise<BrowserSession> {
  const env = getEnv();
  const storage = await ensureRunStorage(runId);
  const context = await chromium.launchPersistentContext(storage.profileDir, {
    headless: env.PLAYWRIGHT_HEADLESS,
    viewport: {
      width: 1440,
      height: 960,
    },
    slowMo: env.PLAYWRIGHT_SLOW_MO,
  });
  const page = context.pages()[0] ?? (await context.newPage());
  const session = { context, page };

  sessions.set(runId, session);
  return session;
}

export async function getBrowserSession(runId: string): Promise<BrowserSession> {
  const existing = sessions.get(runId);
  if (existing && isSessionUsable(existing)) {
    return existing;
  }

  if (existing) {
    await existing.context.close().catch(() => null);
    sessions.delete(runId);
  }

  return createBrowserSession(runId);
}

export async function closeBrowserSession(runId: string) {
  const session = sessions.get(runId);
  if (!session) {
    return;
  }

  await session.context.close();
  sessions.delete(runId);
}

export async function resetBrowserSession(runId: string) {
  await closeBrowserSession(runId);
  return createBrowserSession(runId);
}
