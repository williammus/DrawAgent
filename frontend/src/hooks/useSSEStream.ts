import { useEffect, useRef } from "react";

import { openEventStream } from "../lib/sse";
import { STAGE_PROGRESS_COPY } from "../lib/constants";
import { useAppStore } from "../store/useAppStore";
import type { SseEventData, SseEventEnvelope } from "../types/api";

interface UseSSEStreamOptions {
  onPromptReady?: () => void;
}

const MAX_RECONNECT_ATTEMPTS_BEFORE_DISCONNECTED = 3;

function buildErrorSummary(details?: Record<string, unknown> | null) {
  if (!details) {
    return null;
  }

  const parts: string[] = [];
  const failingNode = typeof details.failing_node === "string" ? details.failing_node : null;
  const provider = typeof details.provider === "string" ? details.provider : null;
  const model = typeof details.model === "string" ? details.model : null;
  const error = typeof details.error === "string" ? details.error : null;
  const missingFields = Array.isArray(details.missing_fields)
    ? details.missing_fields.filter((value): value is string => typeof value === "string")
    : [];

  if (failingNode) {
    parts.push(`节点: ${failingNode}`);
  }
  if (provider) {
    parts.push(`Provider: ${provider}`);
  }
  if (model) {
    parts.push(`Model: ${model}`);
  }
  if (missingFields.length > 0) {
    parts.push(`缺失配置: ${missingFields.join(", ")}`);
  }
  if (error) {
    parts.push(`原因: ${error}`);
  }

  return parts.length > 0 ? parts.join(" | ") : null;
}

export function useSSEStream(options: UseSSEStreamOptions = {}) {
  const sessionId = useAppStore((state) => state.sessionId);
  const latestEventId = useAppStore((state) => state.latestEventId);
  const setLatestEventId = useAppStore((state) => state.setLatestEventId);
  const setEventStreamStatus = useAppStore((state) => state.setEventStreamStatus);
  const applySseEvent = useAppStore((state) => state.applySseEvent);
  const replaceThinkingMessage = useAppStore((state) => state.replaceThinkingMessage);
  const clearThinkingMessages = useAppStore((state) => state.clearThinkingMessages);
  const addMessage = useAppStore((state) => state.addMessage);
  const setClarification = useAppStore((state) => state.setClarification);
  const setGeneratedImageUrl = useAppStore((state) => state.setGeneratedImageUrl);
  const reconnectTimerRef = useRef<number | null>(null);
  const lastEventIdRef = useRef(latestEventId);
  const reconnectAttemptsRef = useRef(0);
  const onPromptReadyRef = useRef(options.onPromptReady);

  useEffect(() => {
    lastEventIdRef.current = latestEventId;
  }, [latestEventId]);

  useEffect(() => {
    onPromptReadyRef.current = options.onPromptReady;
  }, [options.onPromptReady]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    const currentSessionId = sessionId;
    let closed = false;
    reconnectAttemptsRef.current = 0;
    setEventStreamStatus("connecting");
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
          reconnectAttemptsRef.current = 0;
          setEventStreamStatus("connected");
        },
        onError: () => {
          reconnectAttemptsRef.current += 1;
          setEventStreamStatus(
            reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS_BEFORE_DISCONNECTED
              ? "disconnected"
              : "reconnecting"
          );
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
              setClarification(event.question);
              addMessage({
                id: crypto.randomUUID(),
                kind: "clarification",
                timestamp: event.timestamp,
                text: event.question,
                meta: {
                  reason: event.reason,
                  missing_fields: event.missing_fields,
                },
              });
              break;
            case "review_failed":
              addMessage({
                id: crypto.randomUUID(),
                kind: "review_failed",
                timestamp: event.timestamp,
                text: event.reason,
                meta: {
                  review_phase: event.review_phase,
                  error_stage: event.error_stage,
                  fix_suggestion: event.fix_suggestion,
                },
              });
              break;
            case "workflow_warning":
              addMessage({
                id: crypto.randomUUID(),
                kind: "assistant",
                timestamp: event.timestamp,
                text: event.message,
                meta: {
                  warning_type: event.warning_type,
                  review_phase: event.review_phase,
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
              onPromptReadyRef.current?.();
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
                    error_summary: buildErrorSummary(event.details),
                    details: event.details ?? null,
                  },
                });
              break;
          }
        },
      });
    }

    return () => {
      closed = true;
      controller.close();
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
    };
  }, [
    addMessage,
    applySseEvent,
    clearThinkingMessages,
    replaceThinkingMessage,
    sessionId,
    setClarification,
    setEventStreamStatus,
    setGeneratedImageUrl,
    setLatestEventId,
  ]);
}
