import { useEffect } from "react";
import { AlertTriangle, PanelRight, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { ArtifactDrawer } from "./components/artifact/ArtifactDrawer";
import { Composer } from "./components/chat/Composer";
import { ImageResultCard } from "./components/chat/ImageResultCard";
import { MessageList } from "./components/chat/MessageList";
import { PromptPreviewCard } from "./components/chat/PromptPreviewCard";
import { SourceTextPanel } from "./components/chat/SourceTextPanel";
import { Button } from "./components/common/Button";
import { EmptyState } from "./components/common/EmptyState";
import { AppShell } from "./components/shell/AppShell";
import { LeftSidebar } from "./components/shell/LeftSidebar";
import { TopStatusBar } from "./components/shell/TopStatusBar";
import { useArtifacts } from "./hooks/useArtifacts";
import { useChatWorkflow } from "./hooks/useChatWorkflow";
import { useSSEStream } from "./hooks/useSSEStream";
import { useSessionBootstrap } from "./hooks/useSessionBootstrap";
import { useAppStore } from "./store/useAppStore";

function App() {
  useSessionBootstrap();

  const sessionId = useAppStore((state) => state.sessionId);
  const summary = useAppStore((state) => state.summary);
  const sourceText = useAppStore((state) => state.sourceText);
  const sourceTextLocked = useAppStore((state) => state.sourceTextLocked);
  const artifacts = useAppStore((state) => state.artifacts);
  const messages = useAppStore((state) => state.messages);
  const workflowWarnings = useAppStore((state) => state.workflowWarnings);
  const eventStreamStatus = useAppStore((state) => state.eventStreamStatus);
  const generatedImageUrl = useAppStore((state) => state.generatedImageUrl);
  const artifactDrawerOpen = useAppStore((state) => state.artifactDrawerOpen);
  const composerMode = useAppStore((state) => state.composerMode);
  const workspaceStatus = useAppStore((state) => state.workspaceStatus);
  const clarificationQuestion = useAppStore((state) => state.clarificationQuestion);
  const setArtifactDrawerOpen = useAppStore((state) => state.setArtifactDrawerOpen);
  const setComposerMode = useAppStore((state) => state.setComposerMode);
  const setNotice = useAppStore((state) => state.setNotice);
  const notice = useAppStore((state) => state.notice);
  const setSourceText = useAppStore((state) => state.setSourceText);
  const { refreshArtifacts } = useArtifacts();
  const {
    submitting,
    generating,
    submitSourceText,
    submitFeedback,
    resumeClarification,
    confirmGeneration,
    restartSession,
  } = useChatWorkflow();

  useSSEStream({
    onPromptReady: () => {
      void refreshArtifacts();
    },
  });

  useEffect(() => {
    if (!notice) {
      return;
    }

    const fn = notice.tone === "error" ? toast.error : notice.tone === "success" ? toast.success : toast;
    fn(notice.title, {
      description: notice.description,
    });
    setNotice(null);
  }, [notice, setNotice]);

  const finalPrompt = artifacts?.final_prompt_artifact;
  const latestWarning = workflowWarnings.length > 0 ? workflowWarnings[workflowWarnings.length - 1] : null;
  const hasRiskWarning = Boolean(latestWarning || summary?.has_bypass_warning);

  return (
    <AppShell
      drawer={
        <ArtifactDrawer
          artifacts={artifacts}
          onRefresh={() => void refreshArtifacts()}
          onToggle={setArtifactDrawerOpen}
          open={artifactDrawerOpen}
        />
      }
      sidebar={
        <LeftSidebar
          onRestart={() => void restartSession()}
          summary={summary}
          workflowWarnings={workflowWarnings}
        />
      }
      statusBar={<TopStatusBar streamStatus={eventStreamStatus} summary={summary} />}
    >
      <div className="h-full min-h-0">
        <section className="flex h-full min-h-0 flex-col">
          <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Workspace</p>
              <h2 className="mt-2 text-lg font-semibold text-white">科研绘图对话工作台</h2>
            </div>
            <div className="flex items-center gap-2">
              <Button className="xl:hidden" onClick={() => setArtifactDrawerOpen(!artifactDrawerOpen)} tone="ghost">
                <PanelRight className="mr-2 h-4 w-4" />
                产物面板
              </Button>
              <Button onClick={() => void restartSession()} tone="ghost">
                <RotateCcw className="mr-2 h-4 w-4" />
                重新开始
              </Button>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
            <div className="mx-auto max-w-[920px] space-y-5">
              <SourceTextPanel
                disabled={!sessionId || submitting || generating}
                locked={sourceTextLocked}
                onChange={setSourceText}
                onSubmit={() => submitSourceText(sourceText)}
                value={sourceText}
              />

              {latestWarning ? (
                <div className="rounded-[22px] border border-amber-400/20 bg-amber-400/10 px-4 py-4 text-sm text-amber-50">
                  <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-amber-200">
                    <AlertTriangle className="h-4 w-4" />
                    Workflow Warning
                  </div>
                  <p className="mt-2 leading-6">{latestWarning.message}</p>
                </div>
              ) : null}

              <MessageList messages={messages} />

              {workspaceStatus === "idle" && messages.length <= 1 ? (
                <EmptyState>
                  先在上方提交完整绘图内容。完成后，底部输入框会用于澄清回复、局部修改和补充细节。
                </EmptyState>
              ) : null}

              {clarificationQuestion ? (
                <div className="rounded-[20px] border border-sky-400/20 bg-sky-400/10 px-4 py-3 text-sm text-sky-100">
                  当前待补充问题：{clarificationQuestion}
                </div>
              ) : null}

              {finalPrompt ? (
                <PromptPreviewCard
                  disabled={generating || workspaceStatus === "workflow_running"}
                  hasRiskWarning={hasRiskWarning}
                  onConfirm={() => void confirmGeneration()}
                  onFeedback={() => {
                    setComposerMode("default");
                  }}
                  payload={finalPrompt}
                  showActions={workspaceStatus === "prompt_reviewing"}
                />
              ) : null}

              {generatedImageUrl ? <ImageResultCard imageUrl={generatedImageUrl} /> : null}

              {artifactDrawerOpen ? (
                <div className="xl:hidden">
                  <ArtifactDrawer
                    artifacts={artifacts}
                    onRefresh={() => void refreshArtifacts()}
                    onToggle={setArtifactDrawerOpen}
                    open={artifactDrawerOpen}
                  />
                </div>
              ) : null}
            </div>
          </div>

          <div className="border-t border-white/10 px-6 py-5">
            <div className="mx-auto max-w-[920px] space-y-4">
              <Composer
                composerMode={composerMode}
                disabled={!sessionId || !sourceTextLocked || submitting || generating}
                onSubmit={composerMode === "clarification" ? resumeClarification : submitFeedback}
                sourceTextLocked={sourceTextLocked}
                submitting={submitting}
              />
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

export default App;
