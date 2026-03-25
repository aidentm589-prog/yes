import { cn } from "@/lib/utils";

const statusStyles: Record<string, string> = {
  queued: "bg-slate-200 text-slate-700",
  running: "bg-cyan-100 text-cyan-800",
  waiting_for_approval: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
  cancelled: "bg-slate-200 text-slate-700",
  timed_out: "bg-orange-100 text-orange-800",
};

export function RunStatusPill({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em]",
        statusStyles[status] ?? "bg-slate-200 text-slate-700",
      )}
    >
      {status.replaceAll("_", " ")}
    </span>
  );
}
