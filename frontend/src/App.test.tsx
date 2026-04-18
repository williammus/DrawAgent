import React, { StrictMode } from "react";
import { render, renderHook, waitFor, act, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { AppProviders } from "./app/providers/AppProviders";
import { useChatWorkflow } from "./hooks/useChatWorkflow";
import { useSessionBootstrap } from "./hooks/useSessionBootstrap";
import { useSSEStream } from "./hooks/useSSEStream";
import { createInitialAppState, useAppStore } from "./store/useAppStore";
import type { SessionInitResponse, SseEventData, SseEventEnvelope } from "./types/api";
import type { SessionSummary, StoredFileMeta } from "./types/domain";

class MockEventSource {
  static instances: MockEventSource[] = [];

  readonly url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  private listeners = new Map<string, Array<(event: MessageEvent<string>) => void>>();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (event: MessageEvent<string>) => void) {
    const handlers = this.listeners.get(type) ?? [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  close() {
    this.closed = true;
    this.onopen = null;
    this.onerror = null;
    this.listeners.clear();
  }

  connect() {
    if (!this.closed) {
      this.onopen?.();
    }
  }

  fail() {
    if (!this.closed) {
      this.onerror?.();
    }
  }

  emit(eventType: string, envelope: SseEventEnvelope, eventId: number) {
    if (this.closed) {
      return;
    }

    const handlers = this.listeners.get(eventType) ?? [];
    const event = {
      data: JSON.stringify(envelope),
      lastEventId: String(eventId),
    } as MessageEvent<string>;
    handlers.forEach((handler) => handler(event));
  }
}

const initSummary: SessionSummary = {
  session_id: "session-1",
  stage: "idle",
  intent: "unknown",
  has_payload_logic: false,
  has_payload_style: false,
  has_payload_mapper: false,
  has_payload_review: false,
  has_payload_final: false,
  needs_clarification: false,
  user_confirmed: false,
  error_count: 0,
  updated_at: "2026-04-17T08:00:00Z",
  expires_at: "2026-04-17T08:30:00Z",
};

const initResponse: SessionInitResponse = {
  session_id: "session-1",
  summary: initSummary,
};

describe("frontend workflow contracts", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    useAppStore.setState(createInitialAppState());
    MockEventSource.instances = [];
    vi.useRealTimers();
    vi.stubGlobal("EventSource", MockEventSource);
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("open", vi.fn());

    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();

      if (url.endsWith("/api/session/init")) {
        return jsonResponse(initResponse, 201);
      }
      if (url.endsWith("/api/chat/message")) {
        return jsonResponse(
          {
            session_id: "session-1",
            stage: "idle",
            summary: initResponse.summary,
            accepted: true,
            stream_url: "/api/chat/stream/session-1",
            response_message: "Workflow request accepted.",
          },
          202
        );
      }
      if (url.endsWith("/api/upload")) {
        return jsonResponse(
          {
            session_id: "session-1",
            files: [uploadedFile("file-1", "paper.md")],
          },
          201
        );
      }
      if (url.endsWith("/api/upload/session-1/file-1")) {
        return jsonResponse({
          session_id: "session-1",
          file_id: "file-1",
          deleted: true,
        });
      }
      if (url.endsWith("/api/generate/session-1")) {
        return jsonResponse(
          {
            session_id: "session-1",
            stage: "generating_image",
            status: "accepted",
            generated_image_path: "/api/download/session-1",
            generated_image_meta: null,
            download_url: "/api/download/session-1",
          },
          202
        );
      }
      if (url.endsWith("/api/session/session-1")) {
        return jsonResponse({
          session_id: "session-1",
          deleted: true,
          cleanup: null,
        });
      }

      throw new Error(`Unhandled fetch: ${url}`);
    });
  });

  afterEach(() => {
    cleanup();
    MockEventSource.instances.forEach((instance) => instance.close());
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("bootstraps a session and inserts the assistant welcome message", async () => {
    renderHook(() => useSessionBootstrap());

    await waitFor(() => {
      expect(useAppStore.getState().sessionId).toBe("session-1");
    });

    const state = useAppStore.getState();
    expect(state.summary?.stage).toBe("idle");
    expect(state.messages[0]?.text).toContain("会话已创建");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/session/init"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("opens the SSE stream and applies clarification plus prompt-ready events", async () => {
    useAppStore.getState().setSession(initResponse.session_id, initResponse.summary);
    const onPromptReady = vi.fn();

    const { unmount } = renderHook(() => useSSEStream({ onPromptReady }));

    expect(MockEventSource.instances[0]?.url).toContain("/api/chat/stream/session-1");

    await act(async () => {
      MockEventSource.instances[0]?.connect();
    });

    await waitFor(() => {
      expect(useAppStore.getState().eventStreamStatus).toBe("connected");
    });

    await act(async () => {
      emitWorkflowEvent(2, {
        event_type: "clarification_required",
        session_id: "session-1",
        stage: "clarifying",
        timestamp: "2026-04-17T08:10:00Z",
        request_id: "req-clarify",
        message: "Clarification required.",
        clarification_question: "请补充论文摘要和目标期刊。",
      });
    });

    await waitFor(() => {
      expect(useAppStore.getState().clarificationQuestion).toBe("请补充论文摘要和目标期刊。");
      expect(useAppStore.getState().composerMode).toBe("clarification");
      expect(useAppStore.getState().workspaceStatus).toBe("waiting_clarification");
    });

    await act(async () => {
      emitWorkflowEvent(3, {
        event_type: "review_failed",
        session_id: "session-1",
        stage: "reviewing",
        timestamp: "2026-04-17T08:11:00Z",
        request_id: "req-review",
        message: "Critic requested a rollback.",
        reason: "布局层次不清晰。",
        error_stage: "visual_mapper",
        fix_suggestion: ["减少交叉箭头", "强化主路径"],
      });
    });

    await act(async () => {
      emitWorkflowEvent(4, {
        event_type: "prompt_ready",
        session_id: "session-1",
        stage: "prompt_ready",
        timestamp: "2026-04-17T08:12:00Z",
        request_id: "req-prompt",
        message: "Final prompt is ready.",
        prompt_version: "v1",
        ready_for_generation: true,
      });
    });

    await waitFor(() => {
      expect(onPromptReady).toHaveBeenCalledTimes(1);
      expect(useAppStore.getState().workspaceStatus).toBe("prompt_reviewing");
      expect(useAppStore.getState().latestEventId).toBe(4);
    });

    const rollbackMessage = useAppStore
      .getState()
      .messages.find((message) => message.kind === "review_failed");
    expect(rollbackMessage?.text).toBe("布局层次不清晰。");
    expect(rollbackMessage?.meta?.error_stage).toBe("visual_mapper");

    unmount();
  });

  it("does not reopen the SSE stream on app rerender after connection state changes", async () => {
    render(
      <StrictMode>
        <AppProviders>
          <App />
        </AppProviders>
      </StrictMode>
    );

    await waitFor(() => {
      expect(useAppStore.getState().sessionId).toBe("session-1");
      expect(MockEventSource.instances).toHaveLength(1);
    });

    await act(async () => {
      MockEventSource.instances[0]?.connect();
    });

    await waitFor(() => {
      expect(useAppStore.getState().eventStreamStatus).toBe("connected");
    });

    expect(MockEventSource.instances).toHaveLength(1);
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/api/session/session-1"),
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("stores diagnostic details from workflow error events", async () => {
    useAppStore.getState().setSession(initResponse.session_id, initResponse.summary);

    renderHook(() => useSSEStream());

    await act(async () => {
      MockEventSource.instances[0]?.connect();
    });

    await act(async () => {
      emitWorkflowEvent(5, {
        event_type: "error",
        session_id: "session-1",
        stage: "failed",
        timestamp: "2026-04-17T08:13:00Z",
        request_id: "req-error",
        message: "Orchestrator failed.",
        error_code: "llm_invocation_error",
        details: {
          failing_node: "orchestrator",
          model: "qwen-plus",
          error: "401 Unauthorized",
        },
      });
    });

    await waitFor(() => {
      const errorMessage = useAppStore
        .getState()
        .messages.find((message) => message.kind === "error");
      expect(errorMessage?.meta?.error_code).toBe("llm_invocation_error");
      expect(errorMessage?.meta?.error_summary).toContain("节点: orchestrator");
      expect(errorMessage?.meta?.error_summary).toContain("Model: qwen-plus");
      expect(errorMessage?.meta?.error_summary).toContain("原因: 401 Unauthorized");
    });
  });

  it("marks the stream as reconnecting before escalating to disconnected", async () => {
    vi.useFakeTimers();
    useAppStore.getState().setSession(initResponse.session_id, initResponse.summary);

    renderHook(() => useSSEStream());

    await act(async () => {
      MockEventSource.instances[0]?.connect();
    });
    expect(useAppStore.getState().eventStreamStatus).toBe("connected");

    await act(async () => {
      MockEventSource.instances[0]?.fail();
    });
    expect(useAppStore.getState().eventStreamStatus).toBe("reconnecting");

    await act(async () => {
      vi.advanceTimersByTime(1500);
    });
    expect(MockEventSource.instances).toHaveLength(2);

    await act(async () => {
      MockEventSource.instances[1]?.fail();
    });
    expect(useAppStore.getState().eventStreamStatus).toBe("reconnecting");

    await act(async () => {
      vi.advanceTimersByTime(1500);
    });
    expect(MockEventSource.instances).toHaveLength(3);

    await act(async () => {
      MockEventSource.instances[2]?.fail();
    });
    expect(useAppStore.getState().eventStreamStatus).toBe("disconnected");

    await act(async () => {
      vi.advanceTimersByTime(1500);
    });
    expect(MockEventSource.instances).toHaveLength(4);

    await act(async () => {
      MockEventSource.instances[3]?.connect();
    });
    expect(useAppStore.getState().eventStreamStatus).toBe("connected");
  });

  it("submits chat, uploads attachments, removes attachments, and starts generation", async () => {
    useAppStore.getState().setSession(initResponse.session_id, initResponse.summary);
    useAppStore.getState().setSummary({
      ...initResponse.summary,
      has_payload_final: true,
      stage: "prompt_ready",
    });

    const { result } = renderHook(() => useChatWorkflow());

    await act(async () => {
      await result.current.submitMessage("请生成一张科研流程图。");
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/chat/message"),
      expect.objectContaining({ method: "POST" })
    );

    const file = new File(["content"], "paper.md", { type: "text/markdown" });
    await act(async () => {
      await result.current.submitUploads(createFileList([file]));
    });

    await waitFor(() => {
      expect(useAppStore.getState().uploadedFiles).toHaveLength(1);
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/upload"),
      expect.objectContaining({ method: "POST" })
    );

    await act(async () => {
      await result.current.removeAttachment("file-1");
    });

    await waitFor(() => {
      expect(useAppStore.getState().uploadedFiles).toHaveLength(0);
    });

    await act(async () => {
      await result.current.confirmGeneration();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/generate/session-1"),
      expect.objectContaining({ method: "POST" })
    );
    expect(useAppStore.getState().generatedImageUrl).toBe("/api/download/session-1");
  });

  it("restartSession deletes the previous session before creating a new one", async () => {
    useAppStore.getState().setSession(initResponse.session_id, initResponse.summary);

    const { result } = renderHook(() => useChatWorkflow());

    await act(async () => {
      await result.current.restartSession();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/session/session-1"),
      expect.objectContaining({ method: "DELETE" })
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/session/init"),
      expect.objectContaining({ method: "POST" })
    );
    expect(useAppStore.getState().sessionId).toBe("session-1");
  });
});

function emitWorkflowEvent(eventId: number, data: SseEventData) {
  const source = MockEventSource.instances[MockEventSource.instances.length - 1];
  if (!source) {
    throw new Error("EventSource has not been created.");
  }

  source.emit(
    data.event_type,
    {
      event_id: eventId,
      event_type: data.event_type,
      data,
    },
    eventId
  );
}

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: {
        "Content-Type": "application/json",
      },
    })
  );
}

function uploadedFile(fileId: string, originalName: string): StoredFileMeta {
  return {
    file_id: fileId,
    original_name: originalName,
    stored_name: originalName,
    media_type: "text/markdown",
    size_bytes: 1200,
    relative_path: `session-1/uploads/${originalName}`,
    uploaded_at: "2026-04-17T08:05:00Z",
  };
}

function createFileList(files: File[]): FileList {
  const fileList: Partial<FileList> = {
    length: files.length,
    item: (index: number) => files[index] ?? null,
  };

  files.forEach((file, index) => {
    fileList[index] = file;
  });

  return fileList as FileList;
}
