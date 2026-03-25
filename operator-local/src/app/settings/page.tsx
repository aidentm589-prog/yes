import { AppShell } from "@/components/app-shell";
import { SectionCard } from "@/components/section-card";
import { getEnv } from "@/lib/env";
import { ensureDefaultSettings } from "@/server/services/settings-service";

export const revalidate = 0;

export default async function SettingsPage() {
  const settings = await ensureDefaultSettings();
  const env = getEnv();

  return (
    <AppShell currentPath="/settings">
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <SectionCard eyebrow="Runtime" title="Environment">
          <div className="space-y-3 text-sm text-slate-700">
            <p>Planner provider: {env.OPERATOR_PLANNER_PROVIDER}</p>
            <p>OpenAI configured: {env.OPENAI_API_KEY ? "Yes" : "No"}</p>
            <p>Model: {env.OPENAI_MODEL}</p>
            <p>Ollama model: {env.OLLAMA_MODEL}</p>
            <p>Ollama base URL: {env.OLLAMA_BASE_URL}</p>
            <p>Reasoning effort: {env.OPENAI_REASONING_EFFORT}</p>
            <p>Storage dir: {env.OPERATOR_STORAGE_DIR}</p>
            <p>Headless browser: {env.PLAYWRIGHT_HEADLESS ? "true" : "false"}</p>
          </div>
        </SectionCard>
        <SectionCard eyebrow="Policy" title="Persisted defaults">
          <div className="space-y-4">
            {settings.map((setting) => (
              <div key={setting.id} className="rounded-[1.3rem] bg-[#fcfbf6] p-4">
                <p className="text-sm font-semibold text-slate-950">{setting.key}</p>
                <p className="mt-1 text-sm text-slate-600">{setting.description}</p>
                <pre className="mt-3 overflow-x-auto text-xs text-slate-700">
                  {JSON.stringify(setting.value, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </AppShell>
  );
}
