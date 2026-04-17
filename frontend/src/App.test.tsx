import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { AppProviders } from "./app/providers/AppProviders";
import { createInitialAppState, useAppStore } from "./store/useAppStore";
import type { SseEventData, SseEventEnvelope } from "./types/api";

class MockEventSource {
  static instances: MockEventSource[] = [];

  readonly url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private listeners = new Map<string, Array<(event: MessageEvent<string>) => void>>();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
    queueMicrotask(() => {
      this.onopen?.();
    });
  }

  addEventListener(type: string, handler: (event: MessageEvent<string>) => void) {
    const handlers = this.listeners.get(type) ?? [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  close() {
    // No-op for tests.
  }

  emit(eventType: string, envelope: SseEventEnvelope, eventId: number) {
    const handlers = this.listeners.get(eventType) ?? [];
    const event = {
      data: JSON.stringify(envelope),
      lastEventId: String(eventId),
    } as MessageEvent<string>;
    handlers.forEach((handler) => handler(event));
  }
}

const initResponse = {
  session_id: "session-1",
  summary: {
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
  },
};

function renderApp() {
  return render(
    <AppProviders>
      <App />
    </AppProviders>
  );
}

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

describe("DrawAgent frontend", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    useAppStore.setState(createInitialAppState());
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("open", vi.fn());
    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/session/init")) {
        return jsonResponse(initResponse, 201);
      }
      if (url.endsWith("/api/artifacts/session-1")) {
        return jsonResponse({
          session_id: "session-1",
          payload_logic: null,
          payload_style: null,
          payload_mapper: null,
          payload_review: null,
          payload_final: {
            final_prompt_en: "A clean scientific diagram.",
            final_prompt_cn: "一张清晰的科研图。",
            prompt_version: "v1",
            generation_notes: ["Use compact labels."],
            ready_for_generation: true,
          },
        });
      }
      if (url.endsWith("/api/generate/session-1")) {
        return jsonResponse({
          session_id: "session-1",
          stage: "generating_image",
          status: "accepted",
          generated_image_path: "/api/download/session-1",
          generated_image_meta: null,
          download_url: "/api/download/session-1",
        }, 202);
      }
      if (url.endsWith("/api/upload")) {
        return jsonResponse({
          session_id: "session-1",
          files: [
            {
              file_id: "file-1",
              original_name: "paper.md",
              stored_name: "paper.md",
              media_type: "text/markdown",
              size_bytes: 1200,
              relative_path: "session-1/uploads/paper.md",
              uploaded_at: "2026-04-17T08:05:00Z",
            },
          ],
        }, 201);
      }
      if (url.endsWith("/api/upload/session-1/file-1")) {
        return jsonResponse({
          session_id: "session-1",
          file_id: "file-1",
          deleted: true,
        });
      }
      if (url.endsWith("/api/chat/message")) {
        return jsonResponse({
          session_id: "session-1",
          stage: "idle",
          summary: initResponse.summary,
          accepted: true,
          stream_url: "/api/chat/stream/session-1",
          response_message: "Workflow request accepted.",
        }, 202);
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
    vi.unstubAllGlobals();
  });

  it("bootstraps a session and opens the SSE stream", async () => {
    renderApp();

    await screen.findByText("会话已创建。你可以直接描述需要绘制的科研图，或先上传论文摘要、截图和参考材料。");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/session/init"),
      expect.objectContaining({ method: "POST" })
    );
    await waitFor(() => {
      expect(MockEventSource.instances[0]?.url).toContain("/api/chat/stream/session-1");
    });
    expect(screen.getByText("SSE 已连接")).toBeInTheDocument();
  });

  it("switches to clarification mode when clarification_required arrives", async () => {
    renderApp();
    await screen.findByText("会话已创建。你可以直接描述需要绘制的科研图，或先上传论文摘要、截图和参考材料。");

    emitWorkflowEvent(2, {
      event_type: "clarification_required",
      session_id: "session-1",
      stage: "clarifying",
      timestamp: "2026-04-17T08:10:00Z",
      request_id: "req-1",
      message: "Clarification required.",
      clarification_question: "请补充论文摘要和目标期刊。",
    });

    await screen.findByText("当前待补充问题：请补充论文摘要和目标期刊。");
    expect(screen.getByText("继续流程")).toBeInTheDocument();
  });

  it("loads final prompt, triggers generation, and renders the generated image event", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByText("会话已创建。你可以直接描述需要绘制的科研图，或先上传论文摘要、截图和参考材料。");

    emitWorkflowEvent(3, {
      event_type: "prompt_ready",
      session_id: "session-1",
      stage: "prompt_ready",
      timestamp: "2026-04-17T08:12:00Z",
      request_id: "req-2",
      message: "Final prompt is ready.",
      prompt_version: "v1",
      ready_for_generation: true,
    });

    await screen.findByText("Prompt 已就绪，确认后即可生成图片");
    await user.click(screen.getByRole("button", { name: /确认生成/i }));

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/generate/session-1"),
      expect.objectContaining({ method: "POST" })
    );

    emitWorkflowEvent(4, {
      event_type: "image_generated",
      session_id: "session-1",
      stage: "completed",
      timestamp: "2026-04-17T08:13:00Z",
      request_id: "req-3",
      message: "Image generated successfully.",
      image_path: "session-1/outputs/final.png",
    });

    const image = await screen.findByAltText("生成后的科研图");
    expect(image).toHaveAttribute("src", expect.stringContaining("/api/download/session-1"));
  });

  it("uploads and deletes attachments from the current session", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByText("会话已创建。你可以直接描述需要绘制的科研图，或先上传论文摘要、截图和参考材料。");

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["content"], "paper.md", { type: "text/markdown" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await screen.findAllByText("paper.md");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/upload"),
      expect.objectContaining({ method: "POST" })
    );

    const deleteButton = screen.getAllByRole("button", { name: /删除附件 paper\.md/i })[0];
    await user.click(deleteButton);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/upload/session-1/file-1"),
      expect.objectContaining({ method: "DELETE" })
    );
  });
});

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
