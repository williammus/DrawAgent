import { TriangleAlert } from "lucide-react";

interface ErrorBubbleProps {
  text: string;
  errorCode?: string;
  summary?: string | null;
}

export function ErrorBubble({ text, errorCode, summary }: ErrorBubbleProps) {
  return (
    <div className="rounded-[22px] border border-rose-400/20 bg-rose-400/10 px-4 py-4 text-sm text-rose-50">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-rose-200">
        <TriangleAlert className="h-4 w-4" />
        流程失败
      </div>
      <p className="mt-2 leading-6">{text}</p>
      {errorCode ? (
        <p className="mt-2 text-[11px] uppercase tracking-[0.16em] text-rose-200/90">
          {errorCode}
        </p>
      ) : null}
      {summary ? <p className="mt-2 text-xs leading-5 text-rose-100/90">{summary}</p> : null}
    </div>
  );
}
