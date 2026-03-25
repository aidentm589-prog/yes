import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { getEnv } from "@/lib/env";
import { toSlug } from "@/lib/utils";

export async function ensureStorageDirs() {
  const env = getEnv();
  const root = path.resolve(process.cwd(), env.OPERATOR_STORAGE_DIR);

  await Promise.all(
    ["", "runs", "screenshots", "artifacts", "logs", "profiles"].map((segment) =>
      mkdir(path.join(root, segment), { recursive: true }),
    ),
  );

  return root;
}

export async function ensureRunStorage(runId: string) {
  const root = await ensureStorageDirs();
  const runDir = path.join(root, "runs", runId);
  const screenshotDir = path.join(runDir, "screenshots");
  const artifactDir = path.join(runDir, "artifacts");
  const profileDir = path.join(root, "profiles", runId);

  await Promise.all([
    mkdir(runDir, { recursive: true }),
    mkdir(screenshotDir, { recursive: true }),
    mkdir(artifactDir, { recursive: true }),
    mkdir(profileDir, { recursive: true }),
  ]);

  return {
    root,
    runDir,
    screenshotDir,
    artifactDir,
    profileDir,
  };
}

export async function writeArtifact(runId: string, label: string, content: unknown) {
  const { artifactDir } = await ensureRunStorage(runId);
  const filePath = path.join(
    artifactDir,
    `${new Date().toISOString().replace(/[:.]/g, "-")}-${toSlug(label) || "artifact"}.json`,
  );

  await writeFile(filePath, JSON.stringify(content, null, 2), "utf8");
  return filePath;
}

export async function imageFileToDataUrl(filePath: string) {
  const buffer = await readFile(filePath);
  return `data:image/png;base64,${buffer.toString("base64")}`;
}
