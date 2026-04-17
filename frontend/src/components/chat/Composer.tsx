import { useId, useRef, useState } from "react";
import { ArrowUp, Paperclip } from "lucide-react";

import { Button } from "../common/Button";

interface ComposerProps {
  disabled?: boolean;
  submitting?: boolean;
  composerMode: "default" | "clarification";
  onSubmit: (message: string) => Promise<void> | void;
  onUpload: (files: FileList | null) => Promise<void> | void;
}

export function Composer({
  disabled,
  submitting,
  composerMode,
  onSubmit,
  onUpload,
}: ComposerProps) {
  const [value, setValue] = useState("");
  const inputId = useId();
  const fileRef = useRef<HTMLInputElement | null>(null);

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
        <button
          aria-label="上传附件"
          className="mt-1 inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-black/10 text-slate-300 hover:bg-white/5"
          onClick={() => fileRef.current?.click()}
          type="button"
        >
          <Paperclip className="h-4 w-4" />
        </button>
        <label className="sr-only" htmlFor={inputId}>
          输入任务描述
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
            composerMode === "clarification"
              ? "补充论文摘要、方法细节或你希望修改的具体内容…"
              : "描述你想生成的科研图，也可以直接粘贴论文摘要和修改意见…"
          }
          value={value}
        />
        <Button className="mt-1 h-11 w-11 rounded-2xl px-0" disabled={disabled || !value.trim()} loading={submitting} onClick={() => void handleSubmit()} tone="primary">
          <span className="sr-only">{composerMode === "clarification" ? "继续流程" : "发送消息"}</span>
          <ArrowUp className="h-4 w-4" />
        </Button>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
        <p>{composerMode === "clarification" ? "当前处于澄清回复模式" : "Enter 发送，Shift + Enter 换行"}</p>
        <p>{composerMode === "clarification" ? "继续流程" : "发送需求"}</p>
      </div>
      <input
        hidden
        multiple
        onChange={(event) => {
          void onUpload(event.target.files);
          event.currentTarget.value = "";
        }}
        ref={fileRef}
        type="file"
      />
    </div>
  );
}
