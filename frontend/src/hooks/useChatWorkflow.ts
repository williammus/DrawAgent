import { useCallback, useState } from "react";

import { sendChatMessage } from "../api/chat";
import { deleteSession, initSession } from "../api/session";
import { uploadFiles, deleteUploadedFile } from "../api/upload";
import { generateImage } from "../api/generate";
import { MAX_FILE_SIZE_MB, MAX_SESSION_FILES } from "../lib/constants";
import { ApiError } from "../lib/http";
import { useAppStore } from "../store/useAppStore";

export function useChatWorkflow() {
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const sessionId = useAppStore((state) => state.sessionId);
  const summary = useAppStore((state) => state.summary);
  const uploadedFiles = useAppStore((state) => state.uploadedFiles);
  const selectedAttachmentIds = useAppStore((state) => state.selectedAttachmentIds);
  const addMessage = useAppStore((state) => state.addMessage);
  const replaceThinkingMessage = useAppStore((state) => state.replaceThinkingMessage);
  const setSummary = useAppStore((state) => state.setSummary);
  const addUploadedFiles = useAppStore((state) => state.addUploadedFiles);
  const removeUploadedFile = useAppStore((state) => state.removeUploadedFile);
  const setLastError = useAppStore((state) => state.setLastError);
  const setWorkspaceStatus = useAppStore((state) => state.setWorkspaceStatus);
  const resetForNewSession = useAppStore((state) => state.resetForNewSession);
  const setSession = useAppStore((state) => state.setSession);
  const setArtifacts = useAppStore((state) => state.setArtifacts);
  const setGeneratedImageUrl = useAppStore((state) => state.setGeneratedImageUrl);
  const setClarification = useAppStore((state) => state.setClarification);
  const setNotice = useAppStore((state) => state.setNotice);

  const pushApiError = useCallback(
    (error: unknown, fallbackMessage: string) => {
      if (error instanceof ApiError) {
        setLastError(error.detail);
        addMessage({
          id: crypto.randomUUID(),
          kind: "error",
          timestamp: new Date().toISOString(),
          text: error.detail?.message ?? fallbackMessage,
        });
      } else {
        addMessage({
          id: crypto.randomUUID(),
          kind: "error",
          timestamp: new Date().toISOString(),
          text: fallbackMessage,
        });
      }
    },
    [addMessage, setLastError]
  );

  const submitMessage = useCallback(
    async (message: string) => {
      if (!sessionId || !message.trim()) {
        return;
      }

      setSubmitting(true);
      addMessage({
        id: crypto.randomUUID(),
        kind: "user",
        timestamp: new Date().toISOString(),
        text: message.trim(),
      });
      replaceThinkingMessage("系统正在接收你的请求…");
      setWorkspaceStatus("workflow_running");

      try {
        const response = await sendChatMessage({
          session_id: sessionId,
          message: message.trim(),
          attachments: selectedAttachmentIds,
        });
        setSummary(response.summary);
        setClarification(null);
      } catch (error) {
        pushApiError(error, "提交消息失败。");
        setWorkspaceStatus("failed");
      } finally {
        setSubmitting(false);
      }
    },
    [
      addMessage,
      pushApiError,
      replaceThinkingMessage,
      selectedAttachmentIds,
      sessionId,
      setClarification,
      setSummary,
      setWorkspaceStatus,
    ]
  );

  const submitUploads = useCallback(
    async (files: FileList | null) => {
      if (!sessionId || !files || files.length === 0) {
        return;
      }

      if (uploadedFiles.length + files.length > MAX_SESSION_FILES) {
        setNotice({
          title: "附件数量超出限制",
          description: `单会话最多允许 ${MAX_SESSION_FILES} 个附件。`,
          tone: "error",
        });
        return;
      }

      const oversized = Array.from(files).find((file) => file.size > MAX_FILE_SIZE_MB * 1024 * 1024);
      if (oversized) {
        setNotice({
          title: "附件过大",
          description: `${oversized.name} 超过 ${MAX_FILE_SIZE_MB}MB 上限。`,
          tone: "error",
        });
        return;
      }

      setUploading(true);
      setWorkspaceStatus("uploading");
      try {
        const response = await uploadFiles(sessionId, Array.from(files));
        addUploadedFiles(response.files);
        setWorkspaceStatus(summary ? derivePostUploadStatus(summary.stage) : "idle");
        setNotice({
          title: "附件上传完成",
          description: `已添加 ${response.files.length} 个附件。`,
          tone: "success",
        });
      } catch (error) {
        pushApiError(error, "上传附件失败。");
        setWorkspaceStatus("failed");
      } finally {
        setUploading(false);
      }
    },
    [
      addUploadedFiles,
      pushApiError,
      sessionId,
      setNotice,
      setWorkspaceStatus,
      summary,
      uploadedFiles.length,
    ]
  );

  const removeAttachment = useCallback(
    async (fileId: string) => {
      if (!sessionId) {
        return;
      }

      try {
        await deleteUploadedFile(sessionId, fileId);
        removeUploadedFile(fileId);
      } catch (error) {
        pushApiError(error, "删除附件失败。");
      }
    },
    [pushApiError, removeUploadedFile, sessionId]
  );

  const confirmGeneration = useCallback(async () => {
    if (!sessionId) {
      return;
    }

    setGenerating(true);
    setWorkspaceStatus("image_generating");
    replaceThinkingMessage("正在提交图片生成任务…");
    try {
      const response = await generateImage(sessionId);
      if (response.download_url) {
        setGeneratedImageUrl(response.download_url);
      }
      if (summary) {
        setSummary({
          ...summary,
          stage: response.stage,
          user_confirmed: true,
        });
      }
    } catch (error) {
      pushApiError(error, "启动图片生成失败。");
      setWorkspaceStatus("failed");
    } finally {
      setGenerating(false);
    }
  }, [
    pushApiError,
    replaceThinkingMessage,
    sessionId,
    setGeneratedImageUrl,
    setSummary,
    setWorkspaceStatus,
    summary,
  ]);

  const restartSession = useCallback(async () => {
    const previousSessionId = sessionId;
    resetForNewSession();

    try {
      if (previousSessionId) {
        await deleteSession(previousSessionId);
      }
    } catch {
      // Ignore cleanup failures during restart.
    }

    try {
      const response = await initSession();
      setSession(response.session_id, response.summary);
      setWorkspaceStatus("idle");
      setArtifacts(null);
      setGeneratedImageUrl(null);
      addMessage({
        id: crypto.randomUUID(),
        kind: "assistant",
        timestamp: new Date().toISOString(),
        text: "已为你开启新的绘图会话。",
      });
    } catch (error) {
      pushApiError(error, "重新创建会话失败。");
      setWorkspaceStatus("failed");
    }
  }, [
    addMessage,
    pushApiError,
    resetForNewSession,
    sessionId,
    setArtifacts,
    setGeneratedImageUrl,
    setSession,
    setWorkspaceStatus,
  ]);

  return {
    submitting,
    uploading,
    generating,
    submitMessage,
    submitUploads,
    removeAttachment,
    confirmGeneration,
    restartSession,
  };
}

function derivePostUploadStatus(stage: string) {
  return stage === "failed" ? "failed" : "idle";
}
