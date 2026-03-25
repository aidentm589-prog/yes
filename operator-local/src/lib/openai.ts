import OpenAI from "openai";

import { assertOpenAIConfigured } from "@/lib/env";

let cachedClient: OpenAI | null = null;

export function getOpenAIClient() {
  if (cachedClient) {
    return cachedClient;
  }

  cachedClient = new OpenAI({
    apiKey: assertOpenAIConfigured(),
  });

  return cachedClient;
}
