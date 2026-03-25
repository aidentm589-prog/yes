import { getEnv } from "@/lib/env";

type OllamaGenerateResponse = {
  response: string;
  done: boolean;
};

export async function generateWithOllama(prompt: string) {
  const env = getEnv();
  const response = await fetch(`${env.OLLAMA_BASE_URL}/api/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: env.OLLAMA_MODEL,
      prompt,
      stream: false,
      format: "json",
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Ollama request failed (${response.status}): ${text}`);
  }

  const data = (await response.json()) as OllamaGenerateResponse;
  return data.response;
}
