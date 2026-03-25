"use client";

import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";

export function ApprovalActions({ approvalId }: { approvalId: string }) {
  const router = useRouter();
  const [pending, setPending] = useState<"approve" | "reject" | null>(null);

  async function submit(decision: "approve" | "reject") {
    setPending(decision);
    await fetch(`/api/approvals/${approvalId}/${decision}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: `${decision}d in UI` }),
    });
    startTransition(() => {
      router.refresh();
    });
    setPending(null);
  }

  return (
    <div className="flex gap-2">
      <button
        type="button"
        onClick={() => submit("approve")}
        disabled={pending !== null}
        className="rounded-full bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
      >
        {pending === "approve" ? "Approving..." : "Approve"}
      </button>
      <button
        type="button"
        onClick={() => submit("reject")}
        disabled={pending !== null}
        className="rounded-full bg-rose-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
      >
        {pending === "reject" ? "Rejecting..." : "Reject"}
      </button>
    </div>
  );
}
