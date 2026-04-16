type PlaceholderPanelProps = {
  title: string;
  description: string;
};

export function PlaceholderPanel({ title, description }: PlaceholderPanelProps) {
  return (
    <section className="rounded-3xl border border-white/60 bg-white/75 p-6 shadow-sm backdrop-blur">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">{title}</h2>
          <p className="mt-3 max-w-xl text-sm leading-7 text-slate-600">{description}</p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
          Placeholder
        </span>
      </div>
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <div className="h-40 rounded-2xl border border-dashed border-slate-300 bg-slate-50" />
        <div className="h-40 rounded-2xl border border-dashed border-slate-300 bg-slate-50" />
      </div>
    </section>
  );
}
