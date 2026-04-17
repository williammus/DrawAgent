import { Sparkles } from "lucide-react";

export function ThinkingBubble({ text }: { text: string }) {
  return (
    <div className="rounded-[22px] border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-100">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-emerald-300">
        <Sparkles className="h-4 w-4" />
        Agent 正在处理
      </div>
      <p className="mt-2 leading-6">{text}</p>
    </div>
  );
}
