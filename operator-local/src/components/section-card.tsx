import { cn } from "@/lib/utils";

export function SectionCard({
  title,
  eyebrow,
  children,
  className,
}: {
  title: string;
  eyebrow?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-[1.75rem] border border-white/60 bg-white/80 p-6 shadow-[0_24px_64px_rgba(78,74,56,0.09)] backdrop-blur",
        className,
      )}
    >
      <div className="mb-4">
        {eyebrow ? (
          <p className="mb-2 text-xs uppercase tracking-[0.28em] text-slate-500">{eyebrow}</p>
        ) : null}
        <h2 className="font-serif text-2xl text-slate-950">{title}</h2>
      </div>
      {children}
    </section>
  );
}
