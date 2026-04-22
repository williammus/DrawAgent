import type { PropsWithChildren } from "react";
import { AlertTriangle, Plus, Sparkles, TextSearch } from "lucide-react";

import { APP_TITLE } from "../../lib/constants";
import { formatDateTime } from "../../lib/format";
import type { SessionSummary, WorkflowWarning } from "../../types/domain";
import { Button } from "../common/Button";

interface LeftSidebarProps {
  summary: SessionSummary | null;
  workflowWarnings: WorkflowWarning[];
  onRestart: () => void;
}

export function LeftSidebar({ summary, workflowWarnings, onRestart }: LeftSidebarProps) {
  const latestWarning = workflowWarnings.length > 0 ? workflowWarnings[workflowWarnings.length - 1] : null;

  return (
    <div className="flex h-full flex-col gap-4 rounded-[28px] border border-white/10 bg-panel/90 p-5 shadow-2xl shadow-black/20">
      <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-400/15 text-emerald-300">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Scientific Diagram Agent</p>
            <h1 className="mt-1 text-xl font-semibold text-white">{APP_TITLE}</h1>
          </div>
        </div>
        <p className="mt-4 text-sm leading-6 text-slate-400">
          先锁定完整绘图内容，再通过对话补充细节、澄清需求并确认出图。
        </p>
        <Button className="mt-5" tone="primary" block onClick={onRestart}>
          <Plus className="mr-2 h-4 w-4" />
          新建任务
        </Button>
      </div>

      <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
        <h2 className="text-sm font-semibold text-white">当前会话</h2>
        {!summary ? (
          <p className="mt-3 text-sm text-slate-500">正在创建会话…</p>
        ) : (
          <dl className="mt-4 space-y-3 text-sm text-slate-300">
            <Row label="Session">{summary.session_id.slice(0, 8)}…</Row>
            <Row label="阶段">{summary.stage}</Row>
            <Row label="意图">{summary.intent}</Row>
            <Row label="完整内容">{summary.source_text_locked ? "已提交" : "待提交"}</Row>
            <Row label="风险警告">{summary.has_bypass_warning ? "存在" : "无"}</Row>
            <Row label="错误数">{String(summary.error_count)}</Row>
            <Row label="更新时间">{formatDateTime(summary.updated_at)}</Row>
          </dl>
        )}
      </section>

      <section className="min-h-0 flex-1 rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">当前状态提示</h2>
          <TextSearch className="h-4 w-4 text-slate-500" />
        </div>
        <div className="mt-4 space-y-3 overflow-y-auto">
          <div className="rounded-2xl border border-white/10 bg-black/10 p-4 text-sm leading-6 text-slate-300">
            {summary?.source_text_locked
              ? "基础绘图内容已锁定。接下来请使用底部输入框补充澄清、修改逻辑/风格/布局。"
              : "先在主工作区提交完整绘图内容，系统才会开始执行主流程。"}
          </div>

          {latestWarning ? (
            <div className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4 text-sm text-amber-50">
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-amber-200">
                <AlertTriangle className="h-4 w-4" />
                最新 Warning
              </div>
              <p className="mt-2 leading-6">{latestWarning.message}</p>
            </div>
          ) : (
            <p className="text-sm leading-6 text-slate-500">当前没有 warning。达到澄清或审查上限后会在这里显示风险提示。</p>
          )}
        </div>
      </section>
    </div>
  );
}

function Row({ label, children }: PropsWithChildren<{ label: string }>) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="max-w-[160px] truncate text-right text-slate-200">{children}</dd>
    </div>
  );
}
