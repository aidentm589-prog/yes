import path from "node:path";

import { PrismaClient } from "@prisma/client";

import { getEnv } from "@/lib/env";

declare global {
  var __operatorPrisma__: PrismaClient | undefined;
}

function resolveDatasourceUrl() {
  const env = getEnv();
  const url = env.DATABASE_URL;

  if (!url.startsWith("file:")) {
    return url;
  }

  const rawPath = url.slice("file:".length);
  if (path.isAbsolute(rawPath)) {
    return url;
  }

  return `file:${path.resolve(process.cwd(), rawPath.replace(/^\.\//, ""))}`;
}

export const db =
  global.__operatorPrisma__ ??
  new PrismaClient({
    datasources: {
      db: {
        url: resolveDatasourceUrl(),
      },
    },
    log: process.env.NODE_ENV === "development" ? ["warn", "error"] : ["error"],
  });

if (process.env.NODE_ENV !== "production") {
  global.__operatorPrisma__ = db;
}
