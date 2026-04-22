import { useEffect } from "react";
import { PanelRight, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { ArtifactDrawer } from "./components/artifact/ArtifactDrawer";
import { AttachmentTray } from "./components/chat/AttachmentTray";
import { Composer } from "./components/chat/Composer";
import { ImageResultCard } from "./components/chat/ImageResultCard";
import { MessageList } from "./components/chat/MessageList";
import { PromptPreviewCard } from "./components/chat/PromptPreviewCard";
import { Button } from "./components/common/Button";
import { EmptyState } from "./components/common/EmptyState";
import { LeftSidebar } from "./components/shell/LeftSidebar";
import { AppShell } from "./components/shell/AppShell";
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
  const uploadedFiles = useAppStore((state) => state.uploadedFiles);
  const artifacts = useAppStore((state) => state.artifacts);
  const messages = useAppStore((state) => state.messages);
  const eventStreamStatus = useAppStore((state) => state.eventStreamStatus);
  const generatedImageUrl = useAppStore((state) => state.generatedImageUrl);
  const selectedAttachmentIds = useAppStore((state) => state.selectedAttachmentIds);
  const artifactDrawerOpen = useAppStore((state) => state.artifactDrawerOpen);
  const composerMode = useAppStore((state) => state.composerMode);
  const workspaceStatus = useAppStore((state) => state.workspaceStatus);
  const clarificationQuestion = useAppStore((state) => state.clarificationQuestion);
  const setSelectedAttachmentIds = useAppStore((state) => state.setSelectedAttachmentIds);
  const setArtifactDrawerOpen = useAppStore((state) => state.setArtifactDrawerOpen);
  const setComposerMode = useAppStore((state) => state.setComposerMode);
  const setWorkspaceStatus = useAppStore((state) => state.setWorkspaceStatus);
  const setNotice = useAppStore((state) => state.setNotice);
  const notice = useAppStore((state) => state.notice);
  const { refreshArtifacts } = useArtifacts();
  const {
    submitting,
    uploading,
    generating,
    submitMessage,
    submitUploads,
    removeAttachment,
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

  const handleToggleAttachment = (fileId: string) => {
    if (selectedAttachmentIds.length === 0) {
      setSelectedAttachmentIds(uploadedFiles.filter((file) => file.file_id !== fileId).map((file) => file.file_id));
      return;
    }

    if (selectedAttachmentIds.includes(fileId)) {
      const next = selectedAttachmentIds.filter((id) => id !== fileId);
      setSelectedAttachmentIds(next.length === 0 ? [] : next);
      return;
    }

    const next = [...selectedAttachmentIds, fileId];
    if (next.length === uploadedFiles.length) {
      setSelectedAttachmentIds([]);
      return;
    }
    setSelectedAttachmentIds(next);
  };

  const finalPrompt = artifacts?.final_prompt_artifact;

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
      sidebar={<LeftSidebar onRestart={() => void restartSession()} summary={summary} uploadedFiles={uploadedFiles} />}
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
              <MessageList messages={messages} />

              {workspaceStatus === "idle" && messages.length <= 1 ? (
                <EmptyState>
                  先输入完整绘图内容或直接描述你的科研图需求。系统会在需要时主动追问，并在 Prompt 准备好后让你确认是否出图。
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
                  showActions={workspaceStatus === "prompt_reviewing"}
                  onConfirm={() => void confirmGeneration()}
                  onFeedback={() => {
                    setComposerMode("default");
                    setWorkspaceStatus("idle");
                  }}
                  payload={finalPrompt}
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
              <AttachmentTray
                files={uploadedFiles}
                onDelete={(fileId) => void removeAttachment(fileId)}
                onToggle={handleToggleAttachment}
                selectedAttachmentIds={selectedAttachmentIds}
              />
              <Composer
                composerMode={composerMode}
                disabled={!sessionId || uploading || generating}
                onSubmit={submitMessage}
                onUpload={submitUploads}
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
