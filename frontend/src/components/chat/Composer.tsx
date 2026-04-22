import { useId, useState } from "react";
import { ArrowUp } from "lucide-react";

import { Button } from "../common/Button";

interface ComposerProps {
  disabled?: boolean;
  submitting?: boolean;
  composerMode: "default" | "clarification";
  sourceTextLocked: boolean;
  onSubmit: (message: string) => Promise<void> | void;
}

export function Composer({
  disabled,
  submitting,
  composerMode,
  sourceTextLocked,
  onSubmit,
}: ComposerProps) {
  const [value, setValue] = useState("");
  const inputId = useId();

  const handleSubmit = async () => {
    if (!value.trim()) {
      return;
    }
    const next = value;
    setValue("");
    await onSubmit(next);
  };

  return (
    <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4">
      <div className="flex items-start gap-3">
        <label className="sr-only" htmlFor={inputId}>
          输入补充反馈
        </label>
        <textarea
          id={inputId}
          className="min-h-[92px] flex-1 resize-none bg-transparent px-1 py-2 text-sm leading-6 text-white outline-none placeholder:text-slate-500"
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void handleSubmit();
            }
          }}
          placeholder={
            !sourceTextLocked
              ? "先提交上方完整绘图内容，之后这里才可用于补充反馈或澄清回复…"
              : composerMode === "clarification"
                ? "请补充当前澄清所需的信息…"
                : "补充细节、修改逻辑/风格/布局，或继续和 AI 交流…"
          }
          value={value}
        />
        <Button
          className="mt-1 h-11 w-11 rounded-2xl px-0"
          disabled={disabled || !value.trim()}
          loading={submitting}
          onClick={() => void handleSubmit()}
          tone="primary"
        >
          <span className="sr-only">{composerMode === "clarification" ? "继续流程" : "发送反馈"}</span>
          <ArrowUp className="h-4 w-4" />
        </Button>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
        <p>
          {!sourceTextLocked
            ? "请先提交完整绘图内容"
            : composerMode === "clarification"
              ? "当前处于澄清恢复模式，本次输入会走 resume"
              : "当前处于补充反馈模式，本次输入会走 run(user_feedback)"}
        </p>
        <p>{sourceTextLocked ? "Enter 发送，Shift + Enter 换行" : "等待 source_text 提交"}</p>
      </div>
    </div>
  );
}
