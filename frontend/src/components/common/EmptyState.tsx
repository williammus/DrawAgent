import type { PropsWithChildren } from "react";

export function EmptyState({ children }: PropsWithChildren) {
  return (
    <div className="rounded-[24px] border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm text-slate-400">
      {children}
    </div>
  );
}
