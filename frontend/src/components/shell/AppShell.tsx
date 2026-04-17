import type { PropsWithChildren, ReactNode } from "react";

interface AppShellProps extends PropsWithChildren {
  sidebar: ReactNode;
  statusBar: ReactNode;
  drawer: ReactNode;
}

export function AppShell({ sidebar, statusBar, drawer, children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-app text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1680px] gap-6 px-5 py-5">
        <aside className="hidden w-[280px] shrink-0 xl:block">{sidebar}</aside>
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          {statusBar}
          <main className="min-h-0 flex-1 overflow-hidden rounded-[28px] border border-white/10 bg-panel shadow-2xl shadow-black/20">
            {children}
          </main>
        </div>
        <aside className="hidden w-[360px] shrink-0 xl:block">{drawer}</aside>
      </div>
    </div>
  );
}
