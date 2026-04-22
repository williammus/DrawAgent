import { Copy } from "lucide-react";
import { toast } from "sonner";

import type { TextArtifact } from "../../types/domain";
import { ActionButtonGroup } from "./ActionButtonGroup";

interface PromptPreviewCardProps {
  payload: TextArtifact;
  disabled?: boolean;
  showActions?: boolean;
  hasRiskWarning?: boolean;
  onConfirm: () => void;
  onFeedback: () => void;
}

export function PromptPreviewCard({
  payload,
  disabled,
  showActions = true,
  hasRiskWarning = false,
  onConfirm,
  onFeedback,
}: PromptPreviewCardProps) {
  const copyText = async (text: string, label: string) => {
    await navigator.clipboard.writeText(text);
    toast.success(`${label} 已复制`);
  };

  return (
    <section className="rounded-[24px] border border-emerald-400/20 bg-emerald-400/10 p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-emerald-200">Final Prompt</p>
          <h3 className="mt-2 text-lg font-semibold text-white">Prompt 已就绪，确认后即可生成图片</h3>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {hasRiskWarning ? (
            <span className="rounded-full border border-amber-300/20 bg-amber-400/10 px-3 py-1 text-xs text-amber-50">
              带风险放行
            </span>
          ) : null}
          <span className="rounded-full border border-emerald-300/20 bg-black/10 px-3 py-1 text-xs text-emerald-100">
            {payload.prompt_version}
          </span>
        </div>
      </div>

      {hasRiskWarning ? (
        <div className="mt-4 rounded-[20px] border border-amber-300/20 bg-black/10 px-4 py-3 text-sm leading-6 text-amber-50">
          当前 Prompt 是在 warning 放行条件下生成的。生成前请先确认逻辑、风格和布局是否符合预期。
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <PromptBlock
          title="Final Prompt"
          value={payload.content}
          onCopy={() => void copyText(payload.content, "Final Prompt")}
        />
      </div>

      {showActions ? <ActionButtonGroup disabled={disabled} onConfirm={onConfirm} onFeedback={onFeedback} /> : null}
    </section>
  );
}

function PromptBlock({ title, value, onCopy }: { title: string; value: string; onCopy: () => void }) {
  return (
    <div className="rounded-[20px] border border-white/10 bg-black/10 p-4">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-medium text-white">{title}</h4>
        <button
          aria-label={`复制 ${title}`}
          className="inline-flex items-center gap-1 rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 hover:bg-white/5"
          onClick={onCopy}
          type="button"
        >
          <Copy className="h-3.5 w-3.5" />
          复制
        </button>
      </div>
      <pre className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-100">{value}</pre>
    </div>
  );
}
