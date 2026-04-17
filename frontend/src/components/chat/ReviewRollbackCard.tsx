export function ReviewRollbackCard({
  reason,
  errorStage,
  suggestions,
}: {
  reason: string;
  errorStage: string;
  suggestions: string[];
}) {
  return (
    <div className="rounded-[22px] border border-amber-400/20 bg-amber-400/10 px-4 py-4 text-sm text-amber-50">
      <p className="text-xs uppercase tracking-[0.2em] text-amber-200">评审未通过，系统正在自动回滚</p>
      <p className="mt-2 leading-6">{reason}</p>
      <p className="mt-3 text-xs text-amber-200">回滚阶段：{errorStage}</p>
      {suggestions.length > 0 ? (
        <ul className="mt-3 space-y-2 text-xs text-amber-100">
          {suggestions.map((item) => (
            <li key={item}>- {item}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
