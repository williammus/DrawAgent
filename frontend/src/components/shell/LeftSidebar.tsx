import type { PropsWithChildren } from "react";
import { FileText, Plus, Sparkles } from "lucide-react";

import { APP_TITLE } from "../../lib/constants";
import { formatDateTime, formatFileSize } from "../../lib/format";
import type { SessionSummary, StoredFileMeta } from "../../types/domain";
import { Button } from "../common/Button";

interface LeftSidebarProps {
  summary: SessionSummary | null;
  uploadedFiles: StoredFileMeta[];
  onRestart: () => void;
}

export function LeftSidebar({ summary, uploadedFiles, onRestart }: LeftSidebarProps) {
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
          以对话方式整理逻辑、风格和布局产物，再确认出图。
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
            <Row label="错误数">{String(summary.error_count)}</Row>
            <Row label="更新时间">{formatDateTime(summary.updated_at)}</Row>
          </dl>
        )}
      </section>

      <section className="min-h-0 flex-1 rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">当前附件</h2>
          <span className="text-xs text-slate-500">{uploadedFiles.length} 个</span>
        </div>
        <div className="mt-4 space-y-3 overflow-y-auto">
          {uploadedFiles.length === 0 ? (
            <p className="text-sm leading-6 text-slate-500">上传的论文摘要、截图和参考图会出现在这里。</p>
          ) : (
            uploadedFiles.map((file) => (
              <div key={file.file_id} className="rounded-2xl border border-white/10 bg-black/10 p-3">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-xl bg-white/5 p-2 text-slate-300">
                    <FileText className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-100">{file.original_name}</p>
                    <p className="mt-1 text-xs text-slate-500">{formatFileSize(file.size_bytes)}</p>
                  </div>
                </div>
              </div>
            ))
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
