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
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-4 sm:px-5 md:px-8 md:py-6">
        <header className="mb-6 rounded-[1.6rem] border border-white/50 bg-white/70 px-4 py-4 shadow-[0_30px_80px_rgba(78,74,56,0.12)] backdrop-blur sm:px-5 md:mb-8 md:rounded-[2rem] md:px-6 md:py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-[0.32em] text-slate-500 sm:text-xs sm:tracking-[0.4em]">
                Operator Local
              </p>
              <h1 className="font-serif text-xl text-slate-950 sm:text-2xl md:text-3xl">
                Local browser agent runtime
              </h1>
            </div>
            <details className="group md:hidden">
              <summary className="list-none rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white marker:content-none">
                Menu
              </summary>
              <nav className="mt-3 grid min-w-[11rem] gap-2 rounded-[1.25rem] border border-slate-200 bg-[#fcfbf6] p-3 shadow-lg">
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
            </details>
          </div>
          <div className="hidden md:mt-5 md:block">
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
          </div>
        </header>
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
