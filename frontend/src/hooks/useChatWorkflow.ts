import { useCallback, useState } from "react";

import { resumeWorkflow, runWorkflow } from "../api/chat";
import { generateImage } from "../api/generate";
import { deleteSession, initSession } from "../api/session";
import { ApiError } from "../lib/http";
import { useAppStore } from "../store/useAppStore";

export function useChatWorkflow() {
  const [submitting, setSubmitting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const sessionId = useAppStore((state) => state.sessionId);
  const summary = useAppStore((state) => state.summary);
  const addMessage = useAppStore((state) => state.addMessage);
  const replaceThinkingMessage = useAppStore((state) => state.replaceThinkingMessage);
  const setSummary = useAppStore((state) => state.setSummary);
  const setLastError = useAppStore((state) => state.setLastError);
  const setWorkspaceStatus = useAppStore((state) => state.setWorkspaceStatus);
  const resetForNewSession = useAppStore((state) => state.resetForNewSession);
  const setSession = useAppStore((state) => state.setSession);
  const setArtifacts = useAppStore((state) => state.setArtifacts);
  const setGeneratedImageUrl = useAppStore((state) => state.setGeneratedImageUrl);
  const setClarification = useAppStore((state) => state.setClarification);
  const setSourceText = useAppStore((state) => state.setSourceText);
  const syncSourceTextLock = useAppStore((state) => state.syncSourceTextLock);

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

  const submitSourceText = useCallback(
    async (sourceText: string) => {
      if (!sessionId || !sourceText.trim()) {
        return;
      }

      setSubmitting(true);
      replaceThinkingMessage("系统正在接收完整绘图内容…");
      setWorkspaceStatus("workflow_running");

      try {
        const next = sourceText.trim();
        const response = await runWorkflow({
          session_id: sessionId,
          source_text: next,
        });
        setSourceText(next);
        setSummary(response.summary);
        syncSourceTextLock(response.summary.source_text_locked);
        setClarification(null);
      } catch (error) {
        pushApiError(error, "提交完整绘图内容失败。");
        setWorkspaceStatus("failed");
      } finally {
        setSubmitting(false);
      }
    },
    [
      pushApiError,
      replaceThinkingMessage,
      sessionId,
      setClarification,
      setSourceText,
      setSummary,
      setWorkspaceStatus,
      syncSourceTextLock,
    ]
  );

  const submitFeedback = useCallback(
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
      replaceThinkingMessage("系统正在接收你的补充反馈…");
      setWorkspaceStatus("workflow_running");

      try {
        const response = await runWorkflow({
          session_id: sessionId,
          user_feedback: message.trim(),
        });
        setSummary(response.summary);
        setClarification(null);
      } catch (error) {
        pushApiError(error, "提交补充反馈失败。");
        setWorkspaceStatus("failed");
      } finally {
        setSubmitting(false);
      }
    },
    [
      addMessage,
      pushApiError,
      replaceThinkingMessage,
      sessionId,
      setClarification,
      setSummary,
      setWorkspaceStatus,
    ]
  );

  const resumeClarification = useCallback(
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
      replaceThinkingMessage("系统正在接收你的澄清补充…");
      setWorkspaceStatus("workflow_running");

      try {
        const response = await resumeWorkflow({
          session_id: sessionId,
          user_feedback: message.trim(),
        });
        setSummary(response.summary);
        setClarification(null);
      } catch (error) {
        pushApiError(error, "提交澄清回复失败。");
        setWorkspaceStatus("failed");
      } finally {
        setSubmitting(false);
      }
    },
    [
      addMessage,
      pushApiError,
      replaceThinkingMessage,
      sessionId,
      setClarification,
      setSummary,
      setWorkspaceStatus,
    ]
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
      setSourceText("");
      syncSourceTextLock(false);
      addMessage({
        id: crypto.randomUUID(),
        kind: "assistant",
        timestamp: new Date().toISOString(),
        text: "已为你开启新的绘图会话。请先提交完整绘图内容。",
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
    setSourceText,
    setWorkspaceStatus,
    syncSourceTextLock,
  ]);

  return {
    submitting,
    generating,
    submitSourceText,
    submitFeedback,
    resumeClarification,
    confirmGeneration,
    restartSession,
  };
}
