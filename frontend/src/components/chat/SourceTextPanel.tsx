import { FileLock2, FileText } from "lucide-react";

import { Button } from "../common/Button";

interface SourceTextPanelProps {
  value: string;
  locked: boolean;
  disabled?: boolean;
  onChange: (value: string) => void;
  onSubmit: () => Promise<void> | void;
}

export function SourceTextPanel({
  value,
  locked,
  disabled,
  onChange,
  onSubmit,
}: SourceTextPanelProps) {
  const isSubmitDisabled = disabled || locked || !value.trim();

  return (
    <section className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5 shadow-2xl shadow-black/10">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Source Text</p>
          <h3 className="mt-2 text-lg font-semibold text-white">完整绘图内容</h3>
        </div>
        <div className="rounded-full border border-white/10 bg-black/10 px-3 py-1 text-xs text-slate-300">
          {locked ? "已锁定" : "待提交"}
        </div>
      </div>

      <label className="sr-only" htmlFor="source-text-panel">
        请在此处输入用于绘图的完整内容(论文/代码)
      </label>
      <div className="mt-5 rounded-[22px] border border-white/10 bg-black/10 p-4">
        <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-400">
          {locked ? <FileLock2 className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
          请在此处输入用于绘图的完整内容(论文/代码)
        </div>
        <textarea
          id="source-text-panel"
          className="min-h-[220px] w-full resize-y bg-transparent text-sm leading-6 text-white outline-none placeholder:text-slate-500 disabled:cursor-not-allowed"
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          placeholder="粘贴论文摘要、方法流程、模块说明或需要可视化的完整代码上下文…"
          readOnly={locked}
          value={
            locked && !value
              ? "完整绘图内容已提交，本地未保留原文缓存。如需替换，请重新开始新会话。"
              : value
          }
        />
      </div>

      <div className="mt-4 flex items-center justify-between gap-4">
        <p className="text-sm leading-6 text-slate-400">
          {locked
            ? "完整绘图内容已锁定。后续补充细节、澄清回复或局部修改，请使用下方输入框。"
            : "先提交完整绘图内容，系统才能开始主流程并开启后续反馈输入。"}
        </p>
        {!locked ? (
          <Button disabled={isSubmitDisabled} onClick={() => void onSubmit()} tone="primary">
            开始绘图流程
          </Button>
        ) : null}
      </div>
    </section>
  );
}
