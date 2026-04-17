import { RefreshCcw, X } from "lucide-react";

import { toHeadline } from "../../lib/format";
import type { ArtifactsBundle } from "../../types/domain";
import { Button } from "../common/Button";
import { EmptyState } from "../common/EmptyState";

interface ArtifactDrawerProps {
  artifacts: ArtifactsBundle | null;
  open: boolean;
  onToggle: (open: boolean) => void;
  onRefresh: () => void;
}

export function ArtifactDrawer({ artifacts, open, onToggle, onRefresh }: ArtifactDrawerProps) {
  return (
    <div
      className={`flex h-full flex-col rounded-[28px] border border-white/10 bg-panel/90 p-5 shadow-2xl shadow-black/20 ${
        open ? "" : "opacity-80"
      }`}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Artifacts</p>
          <h2 className="mt-2 text-lg font-semibold text-white">过程与产物</h2>
        </div>
        <div className="flex items-center gap-2">
          <Button className="h-9 px-3" onClick={onRefresh} tone="ghost">
            <RefreshCcw className="mr-2 h-4 w-4" />
            刷新
          </Button>
          <Button className="h-9 px-3 2xl:hidden" onClick={() => onToggle(!open)} tone="ghost">
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="mt-5 min-h-0 flex-1 space-y-4 overflow-y-auto">
        {!artifacts ? (
          <EmptyState>流程推进后，逻辑、风格、布局、评审和 Final Prompt 会逐步出现在这里。</EmptyState>
        ) : (
          ([
            ["payload_logic", artifacts.payload_logic],
            ["payload_style", artifacts.payload_style],
            ["payload_mapper", artifacts.payload_mapper],
            ["payload_review", artifacts.payload_review],
            ["payload_final", artifacts.payload_final],
          ] as const).map(([key, value]) => (
            <section key={key} className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
              <h3 className="text-sm font-medium text-white">{toHeadline(key)}</h3>
              {value ? (
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-slate-300">
                  {JSON.stringify(value, null, 2)}
                </pre>
              ) : (
                <p className="mt-3 text-sm text-slate-500">尚未生成</p>
              )}
            </section>
          ))
        )}
      </div>
    </div>
  );
}
