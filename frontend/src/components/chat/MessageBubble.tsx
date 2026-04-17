import type { UIMessage } from "../../types/ui";
import { ClarificationCard } from "./ClarificationCard";
import { ErrorBubble } from "./ErrorBubble";
import { ReviewRollbackCard } from "./ReviewRollbackCard";
import { ThinkingBubble } from "./ThinkingBubble";

export function MessageBubble({ message }: { message: UIMessage }) {
  if (message.kind === "thinking") {
    return <ThinkingBubble text={message.text ?? "系统处理中…"} />;
  }
  if (message.kind === "clarification") {
    return <ClarificationCard question={message.text ?? ""} />;
  }
  if (message.kind === "review_failed") {
    return (
      <ReviewRollbackCard
        errorStage={String(message.meta?.error_stage ?? "unknown")}
        reason={message.text ?? "评审未通过"}
        suggestions={Array.isArray(message.meta?.fix_suggestion) ? (message.meta?.fix_suggestion as string[]) : []}
      />
    );
  }
  if (message.kind === "error") {
    return <ErrorBubble text={message.text ?? "发生错误"} />;
  }
  if (message.kind === "stage_status") {
    return (
      <div className="rounded-[20px] border border-white/10 bg-white/[0.02] px-4 py-3 text-sm text-slate-300">
        {message.text}
      </div>
    );
  }
  if (message.kind === "image_result") {
    return (
      <div className="rounded-[20px] border border-white/10 bg-white/[0.02] px-4 py-3 text-sm text-slate-200">
        {message.text}
      </div>
    );
  }

  const isUser = message.kind === "user";
  return (
    <div className={`max-w-[760px] rounded-[22px] px-4 py-3 text-sm leading-6 ${isUser ? "ml-auto bg-emerald-400 text-slate-950" : "bg-white/[0.04] text-slate-100"}`}>
      {message.text}
    </div>
  );
}
