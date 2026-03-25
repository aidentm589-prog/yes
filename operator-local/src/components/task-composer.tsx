"use client";

import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";

export function TaskComposer() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const createResponse = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      if (!createResponse.ok) {
        const payload = (await createResponse.json()) as { error?: string };
        throw new Error(payload.error ?? "Failed to create run.");
      }

      const created = (await createResponse.json()) as { run: { id: string } };
      await fetch(`/api/runs/${created.run.id}/continue`, { method: "POST" });

      startTransition(() => {
        router.push(`/runs/${created.run.id}`);
      });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Could not start run.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <textarea
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        placeholder="Ask the agent to research, extract, compare, or draft a browser workflow..."
        className="min-h-44 w-full rounded-[1.5rem] border border-slate-200 bg-[#fcfbf6] px-5 py-4 text-base text-slate-900 shadow-inner outline-none transition focus:border-slate-400"
        required
        minLength={10}
      />
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <p className="max-w-2xl text-sm text-slate-600">
          Runs execute through a typed Playwright action layer, record evidence, and pause for
          risky actions that require approval.
        </p>
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Starting run..." : "Start operator run"}
        </button>
      </div>
      {error ? <p className="text-sm text-rose-700">{error}</p> : null}
    </form>
  );
}
