import { useEffect, useRef } from "react";

import { openEventStream } from "../lib/sse";
import { STAGE_PROGRESS_COPY } from "../lib/constants";
import { useAppStore } from "../store/useAppStore";
import type { SseEventData, SseEventEnvelope } from "../types/api";

interface UseSSEStreamOptions {
  onPromptReady?: () => void;
}

export function useSSEStream(options: UseSSEStreamOptions = {}) {
  const sessionId = useAppStore((state) => state.sessionId);
  const latestEventId = useAppStore((state) => state.latestEventId);
  const setLatestEventId = useAppStore((state) => state.setLatestEventId);
  const setEventStreamConnected = useAppStore((state) => state.setEventStreamConnected);
  const applySseEvent = useAppStore((state) => state.applySseEvent);
  const replaceThinkingMessage = useAppStore((state) => state.replaceThinkingMessage);
  const clearThinkingMessages = useAppStore((state) => state.clearThinkingMessages);
  const addMessage = useAppStore((state) => state.addMessage);
  const setClarification = useAppStore((state) => state.setClarification);
  const setGeneratedImageUrl = useAppStore((state) => state.setGeneratedImageUrl);
  const reconnectTimerRef = useRef<number | null>(null);
  const lastEventIdRef = useRef(latestEventId);
  const onPromptReady = options.onPromptReady;

  useEffect(() => {
    lastEventIdRef.current = latestEventId;
  }, [latestEventId]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    const currentSessionId = sessionId;
    let closed = false;
    let controller = open();

    function scheduleReconnect() {
      if (closed || reconnectTimerRef.current !== null) {
        return;
      }

      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        if (!closed) {
          controller = open();
        }
      }, 1500);
    }

    function open() {
      return openEventStream({
        sessionId: currentSessionId,
        afterId: lastEventIdRef.current,
        onOpen: () => {
          setEventStreamConnected(true);
        },
        onError: () => {
          setEventStreamConnected(false);
          scheduleReconnect();
        },
        onEvent: (_eventType, payload, eventId) => {
          const envelope = JSON.parse(payload) as SseEventEnvelope<SseEventData>;
          const event = envelope.data;
          setLatestEventId(eventId || envelope.event_id);
          applySseEvent(eventId || envelope.event_id, event);

          switch (event.event_type) {
            case "stage_started":
              replaceThinkingMessage(STAGE_PROGRESS_COPY[event.stage] ?? event.message);
              break;
            case "stage_completed":
              addMessage({
                id: crypto.randomUUID(),
                kind: "stage_status",
                timestamp: event.timestamp,
                text: event.message,
                meta: { stage: event.stage },
              });
              break;
            case "clarification_required":
              clearThinkingMessages();
              setClarification(event.clarification_question);
              addMessage({
                id: crypto.randomUUID(),
                kind: "clarification",
                timestamp: event.timestamp,
                text: event.clarification_question,
              });
              break;
            case "review_failed":
              addMessage({
                id: crypto.randomUUID(),
                kind: "review_failed",
                timestamp: event.timestamp,
                text: event.reason,
                meta: {
                  error_stage: event.error_stage,
                  fix_suggestion: event.fix_suggestion,
                },
              });
              break;
            case "prompt_ready":
              clearThinkingMessages();
              addMessage({
                id: crypto.randomUUID(),
                kind: "assistant",
                timestamp: event.timestamp,
                text: "最终 Prompt 已经准备好。请先预览，再决定是否生成图片。",
              });
              onPromptReady?.();
              break;
            case "image_generated":
              clearThinkingMessages();
              setGeneratedImageUrl(`/api/download/${event.session_id}`);
              addMessage({
                id: crypto.randomUUID(),
                kind: "image_result",
                timestamp: event.timestamp,
                text: "图片已生成，可以直接预览或下载。",
              });
              break;
            case "error":
              clearThinkingMessages();
              addMessage({
                id: crypto.randomUUID(),
                kind: "error",
                timestamp: event.timestamp,
                text: event.message,
                meta: {
                  error_code: event.error_code,
                },
              });
              break;
          }
        },
      });
    }

    return () => {
      closed = true;
      setEventStreamConnected(false);
      controller.close();
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
    };
  }, [
    addMessage,
    applySseEvent,
    clearThinkingMessages,
    onPromptReady,
    replaceThinkingMessage,
    sessionId,
    setClarification,
    setEventStreamConnected,
    setGeneratedImageUrl,
    setLatestEventId,
  ]);
}
