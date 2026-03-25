import { getEnv } from "@/lib/env";

type ProviderReadiness = {
  provider: "openai" | "ollama";
  ready: boolean;
  message: string;
  details: {
    model: string;
    baseUrl?: string;
    reachable?: boolean;
    modelAvailable?: boolean;
    openaiConfigured?: boolean;
  };
};

type OllamaTagsResponse = {
  models?: Array<{ name?: string; model?: string }>;
};

export async function getProviderReadiness(): Promise<ProviderReadiness> {
  const env = getEnv();

  if (env.OPERATOR_PLANNER_PROVIDER === "openai") {
    return {
      provider: "openai",
      ready: Boolean(env.OPENAI_API_KEY),
      message: env.OPENAI_API_KEY
        ? "OpenAI planner is configured."
        : "OpenAI planner is selected, but OPENAI_API_KEY is missing.",
      details: {
        model: env.OPENAI_MODEL,
        openaiConfigured: Boolean(env.OPENAI_API_KEY),
      },
    };
  }

  try {
    const response = await fetch(`${env.OLLAMA_BASE_URL}/api/tags`, {
      method: "GET",
      cache: "no-store",
      signal: AbortSignal.timeout(3_000),
    });

    if (!response.ok) {
      return {
        provider: "ollama",
        ready: false,
        message: `Ollama is not ready at ${env.OLLAMA_BASE_URL} (${response.status}).`,
        details: {
          model: env.OLLAMA_MODEL,
          baseUrl: env.OLLAMA_BASE_URL,
          reachable: false,
          modelAvailable: false,
        },
      };
    }

    const data = (await response.json()) as OllamaTagsResponse;
    const knownModels = data.models?.flatMap((model) =>
      [model.name, model.model].filter((value): value is string => Boolean(value)),
    ) ?? [];
    const modelAvailable = knownModels.includes(env.OLLAMA_MODEL);

    return {
      provider: "ollama",
      ready: modelAvailable,
      message: modelAvailable
        ? "Ollama planner is reachable and the selected model is available."
        : `Ollama is reachable, but model ${env.OLLAMA_MODEL} is not pulled yet.`,
      details: {
        model: env.OLLAMA_MODEL,
        baseUrl: env.OLLAMA_BASE_URL,
        reachable: true,
        modelAvailable,
      },
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown Ollama connection error";
    return {
      provider: "ollama",
      ready: false,
      message: `Unable to reach Ollama at ${env.OLLAMA_BASE_URL}: ${message}`,
      details: {
        model: env.OLLAMA_MODEL,
        baseUrl: env.OLLAMA_BASE_URL,
        reachable: false,
        modelAvailable: false,
      },
    };
  }
}
