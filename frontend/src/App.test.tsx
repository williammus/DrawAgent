import React, { StrictMode } from "react";
import { render, renderHook, waitFor, act, cleanup, screen, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { AppProviders } from "./app/providers/AppProviders";
import { useChatWorkflow } from "./hooks/useChatWorkflow";
import { useSessionBootstrap } from "./hooks/useSessionBootstrap";
import { useSSEStream } from "./hooks/useSSEStream";
import { createInitialAppState, useAppStore } from "./store/useAppStore";
import type { SessionInitResponse, SseEventData, SseEventEnvelope } from "./types/api";
import type { ArtifactsBundle, SessionSummary } from "./types/domain";

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
  has_source_text: false,
  source_text_locked: false,
  has_logic_artifact: false,
  has_style_artifact: false,
  has_plan_review_artifact: false,
  has_mapper_artifact: false,
  has_final_review_artifact: false,
  has_final_prompt_artifact: false,
  has_bypass_warning: false,
  needs_clarification: false,
  interrupted: false,
  user_confirmed: false,
  error_count: 0,
  updated_at: "2026-04-17T08:00:00Z",
  expires_at: "2026-04-17T08:30:00Z",
};

const lockedSummary: SessionSummary = {
  ...initSummary,
  has_source_text: true,
  source_text_locked: true,
};

const initResponse: SessionInitResponse = {
  session_id: "session-1",
  summary: initSummary,
};

const promptArtifacts: ArtifactsBundle = {
  session_id: "session-1",
  logic_artifact: null,
  style_artifact: null,
  plan_review_artifact: null,
  mapper_artifact: null,
  final_review_artifact: null,
  final_prompt_artifact: {
    tool_name: "summary_tool",
    content: "Create a clean academic diagram with a clear left-to-right story.",
    prompt_version: "v2",
    updated_at: "2026-04-17T08:12:00Z",
    metadata: {
      ready_for_generation: true,
    },
  },
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

    fetchMock.mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();

      if (url.endsWith("/api/session/init")) {
        return jsonResponse(initResponse, 201);
      }
      if (url.endsWith("/api/chat/run")) {
        const payload = parseJsonBody(init?.body);
        const summary = payload?.source_text
          ? {
              ...lockedSummary,
              stage: "planning",
            }
          : {
              ...lockedSummary,
              stage: "planning",
            };

        return jsonResponse(
          {
            session_id: "session-1",
            stage: summary.stage,
            summary,
            accepted: true,
            stream_url: "/api/chat/stream/session-1",
            operation: payload?.source_text ? "run_source_text" : "run_user_feedback",
            response_message: "Workflow request accepted.",
          },
          202
        );
      }
      if (url.endsWith("/api/chat/resume")) {
        return jsonResponse(
          {
            session_id: "session-1",
            stage: "planning",
            summary: {
              ...lockedSummary,
              interrupted: false,
              needs_clarification: false,
              stage: "planning",
            },
            accepted: true,
            stream_url: "/api/chat/stream/session-1",
            operation: "resume_user_feedback",
            response_message: "Clarification response accepted.",
          },
          202
        );
      }
      if (url.includes("/api/artifacts/")) {
        return jsonResponse(promptArtifacts, 200);
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

  it("bootstraps a session and exposes source_text-first UI without upload entry", async () => {
    render(
      <StrictMode>
        <AppProviders>
          <App />
        </AppProviders>
      </StrictMode>
    );

    await waitFor(() => {
      expect(useAppStore.getState().sessionId).toBe("session-1");
    });

    expect(screen.getByLabelText("请在此处输入用于绘图的完整内容(论文/代码)")).toBeInTheDocument();
    expect(screen.getByLabelText("输入补充反馈")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "上传附件" })).not.toBeInTheDocument();
    expect(screen.queryByText("当前附件")).not.toBeInTheDocument();
    expect(useAppStore.getState().messages[0]?.text).toContain("请先在上方输入完整绘图内容");
  });

  it("submits source_text via run and only unlocks the feedback composer after locking", async () => {
    render(
      <StrictMode>
        <AppProviders>
          <App />
        </AppProviders>
      </StrictMode>
    );

    await waitFor(() => {
      expect(useAppStore.getState().sessionId).toBe("session-1");
    });

    fireEvent.change(screen.getByLabelText("请在此处输入用于绘图的完整内容(论文/代码)"), {
      target: { value: "这里是一段完整的论文摘要。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "开始绘图流程" }));

    await waitFor(() => {
      expect(useAppStore.getState().sourceTextLocked).toBe(true);
    });

    const runCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/api/chat/run"));
    expect(runCall).toBeDefined();
    expect(parseJsonBody(runCall?.[1]?.body)?.source_text).toBe("这里是一段完整的论文摘要。");
    expect(useAppStore.getState().messages.map((message) => message.text)).not.toContain("这里是一段完整的论文摘要。");
    expect(screen.getByLabelText("输入补充反馈")).toBeEnabled();
  });

  it("uses resume for clarification replies and run(user_feedback) for normal feedback", async () => {
    useAppStore.getState().setSession(initResponse.session_id, lockedSummary);
    useAppStore.getState().setSummary(lockedSummary);
    useAppStore.getState().setSourceText("已经锁定的完整绘图内容");

    const { result } = renderHook(() => useChatWorkflow());

    await act(async () => {
      await result.current.submitFeedback("请把整体配色调整得更克制。");
    });

    const runFeedbackCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/api/chat/run") && parseJsonBody(init?.body)?.user_feedback === "请把整体配色调整得更克制。"
    );
    expect(runFeedbackCall).toBeDefined();

    useAppStore.getState().setClarification("请补充目标期刊。");

    await act(async () => {
      await result.current.resumeClarification("目标期刊是 Nature Biomedical Engineering。");
    });

    const resumeCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/api/chat/resume"));
    expect(resumeCall).toBeDefined();
    expect(parseJsonBody(resumeCall?.[1]?.body)?.user_feedback).toBe("目标期刊是 Nature Biomedical Engineering。");
  });

  it("shows workflow warnings and marks prompt preview as risk-bypassed after prompt_ready", async () => {
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

    act(() => {
      useAppStore.getState().setSourceText("已经锁定的完整绘图内容");
      useAppStore.getState().setSummary(lockedSummary);
    });

    await act(async () => {
      MockEventSource.instances[0]?.connect();
    });

    await act(async () => {
      emitWorkflowEvent(2, {
        event_type: "workflow_warning",
        session_id: "session-1",
        stage: "reviewing",
        timestamp: "2026-04-17T08:11:00Z",
        request_id: "req-warning",
        message: "审查达到上限，当前流程带风险放行。",
        warning_type: "review_limit_reached",
        loop_id: "loop-1",
        review_phase: "post_mapper",
      });
    });

    await act(async () => {
      emitWorkflowEvent(3, {
        event_type: "prompt_ready",
        session_id: "session-1",
        stage: "prompt_ready",
        timestamp: "2026-04-17T08:12:00Z",
        request_id: "req-prompt",
        message: "Final prompt is ready.",
        prompt_version: "v2",
        ready_for_generation: true,
      });
    });

    await waitFor(() => {
      expect(useAppStore.getState().workflowWarnings[0]?.message).toBe("审查达到上限，当前流程带风险放行。");
      expect(screen.getByText("带风险放行")).toBeInTheDocument();
      expect(screen.getAllByText("Create a clean academic diagram with a clear left-to-right story.").length).toBeGreaterThan(0);
    });
  });

  it("restartSession clears source text and disables the feedback composer again", async () => {
    useAppStore.getState().setSession(initResponse.session_id, lockedSummary);
    useAppStore.getState().setSummary(lockedSummary);
    useAppStore.getState().setSourceText("需要被清空的原文");

    const { result } = renderHook(() => useChatWorkflow());

    await act(async () => {
      await result.current.restartSession();
    });

    expect(useAppStore.getState().sourceText).toBe("");
    expect(useAppStore.getState().sourceTextLocked).toBe(false);
  });

  it("opens the SSE stream and applies clarification events to composer mode", async () => {
    useAppStore.getState().setSession(initResponse.session_id, lockedSummary);
    useAppStore.getState().setSummary(lockedSummary);

    renderHook(() => useSSEStream());

    await act(async () => {
      MockEventSource.instances[0]?.connect();
    });

    await act(async () => {
      emitWorkflowEvent(5, {
        event_type: "clarification_required",
        session_id: "session-1",
        stage: "clarifying",
        timestamp: "2026-04-17T08:10:00Z",
        request_id: "req-clarify",
        message: "Clarification required.",
        question: "请补充目标会议和所属领域。",
        reason: "missing_required_context",
        missing_fields: ["parsed_discipline", "parsed_target_venue"],
      });
    });

    await waitFor(() => {
      expect(useAppStore.getState().clarificationQuestion).toBe("请补充目标会议和所属领域。");
      expect(useAppStore.getState().composerMode).toBe("clarification");
      expect(useAppStore.getState().workspaceStatus).toBe("waiting_clarification");
    });
  });

  it("bootstraps a session through the dedicated hook", async () => {
    renderHook(() => useSessionBootstrap());

    await waitFor(() => {
      expect(useAppStore.getState().sessionId).toBe("session-1");
    });
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

function parseJsonBody(body: BodyInit | null | undefined) {
  if (typeof body !== "string") {
    return null;
  }
  return JSON.parse(body) as Record<string, string>;
}
