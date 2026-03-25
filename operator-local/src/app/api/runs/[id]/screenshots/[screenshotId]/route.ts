import { readFile } from "node:fs/promises";

import { NextResponse } from "next/server";

import { runRepository } from "@/server/repositories/run-repository";

export const runtime = "nodejs";

export async function GET(
  _: Request,
  context: { params: Promise<{ id: string; screenshotId: string }> },
) {
  const { id, screenshotId } = await context.params;
  const screenshot = await runRepository.getScreenshot(id, screenshotId);

  if (!screenshot) {
    return NextResponse.json({ error: "Screenshot not found." }, { status: 404 });
  }

  const file = await readFile(screenshot.path);

  return new NextResponse(file, {
    headers: {
      "Content-Type": screenshot.mimeType,
      "Cache-Control": "no-store",
    },
  });
}
