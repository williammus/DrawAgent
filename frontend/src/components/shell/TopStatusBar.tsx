import type { ReactNode } from "react";
import { CircleAlert, Radio, TimerReset } from "lucide-react";

import { formatStageLabel } from "../../lib/format";
import { useCountdown } from "../../hooks/useCountdown";
import type { SessionSummary } from "../../types/domain";

interface TopStatusBarProps {
  summary: SessionSummary | null;
  connected: boolean;
}

export function TopStatusBar({ summary, connected }: TopStatusBarProps) {
  const countdown = useCountdown(summary?.expires_at ?? null);

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-[24px] border border-white/10 bg-panel/90 px-4 py-3 shadow-2xl shadow-black/20">
      <StatusPill label="阶段" value={summary ? formatStageLabel(summary.stage) : "初始化中"} />
      <StatusPill label="连接" value={connected ? "SSE 已连接" : "连接中断"} tone={connected ? "success" : "warn"} />
      <StatusPill label="剩余 TTL" value={countdown} icon={<TimerReset className="h-4 w-4" />} />
      <StatusPill
        label="错误数"
        value={summary ? String(summary.error_count) : "0"}
        tone={summary && summary.error_count > 0 ? "warn" : "neutral"}
        icon={<CircleAlert className="h-4 w-4" />}
      />
      <div className="ml-auto hidden items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-400 md:flex">
        <Radio className={`h-3.5 w-3.5 ${connected ? "text-emerald-300" : "text-amber-300"}`} />
        所有阶段状态以 SSE 事件为准
      </div>
    </div>
  );
}

function StatusPill({
  label,
  value,
  tone = "neutral",
  icon,
}: {
  label: string;
  value: string;
  tone?: "neutral" | "success" | "warn";
  icon?: ReactNode;
}) {
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs ${
        tone === "success"
          ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-200"
          : tone === "warn"
            ? "border-amber-400/20 bg-amber-400/10 text-amber-200"
            : "border-white/10 bg-white/[0.03] text-slate-300"
      }`}
    >
      {icon}
      <span className="text-slate-500">{label}</span>
      <strong className="font-medium text-current">{value}</strong>
    </div>
  );
}
