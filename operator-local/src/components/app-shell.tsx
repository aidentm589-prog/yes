import Link from "next/link";

import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Console" },
  { href: "/runs", label: "Runs" },
  { href: "/approvals", label: "Approvals" },
  { href: "/settings", label: "Settings" },
];

export function AppShell({
  children,
  currentPath,
}: {
  children: React.ReactNode;
  currentPath?: string;
}) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(170,215,216,0.28),_transparent_32%),linear-gradient(180deg,_#f6f4ee_0%,_#f2efe5_45%,_#ebe7dc_100%)] text-slate-900">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-6 py-6 md:px-8">
        <header className="mb-8 flex flex-col gap-5 rounded-[2rem] border border-white/50 bg-white/70 px-6 py-5 shadow-[0_30px_80px_rgba(78,74,56,0.12)] backdrop-blur md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Operator Local</p>
            <h1 className="font-serif text-3xl text-slate-950">Local browser agent runtime</h1>
          </div>
          <nav className="flex flex-wrap gap-2">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-full px-4 py-2 text-sm transition",
                  currentPath === item.href
                    ? "bg-slate-900 text-white"
                    : "bg-slate-900/5 text-slate-700 hover:bg-slate-900/10",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
