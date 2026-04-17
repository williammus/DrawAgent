import { MessagesSquare } from "lucide-react";

export function ClarificationCard({ question }: { question: string }) {
  return (
    <div className="rounded-[22px] border border-sky-400/20 bg-sky-400/10 px-4 py-4 text-sm text-sky-50">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-sky-200">
        <MessagesSquare className="h-4 w-4" />
        需要补充信息
      </div>
      <p className="mt-2 leading-6">{question}</p>
    </div>
  );
}
