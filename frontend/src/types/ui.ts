import type { EventType } from "./domain";

export type MessageKind =
  | "user"
  | "assistant"
  | "thinking"
  | "clarification"
  | "stage_status"
  | "review_failed"
  | "error"
  | "final_prompt"
  | "image_result";

export type ComposerMode = "default" | "clarification";

export type EventStreamStatus = "connecting" | "connected" | "reconnecting" | "disconnected";

export type WorkspaceStatus =
  | "bootstrapping"
  | "idle"
  | "workflow_running"
  | "waiting_clarification"
  | "prompt_reviewing"
  | "image_generating"
  | "completed"
  | "failed";

export interface UIMessage {
  id: string;
  kind: MessageKind;
  text?: string;
  timestamp: string;
  meta?: Record<string, unknown>;
}

export interface AppNotice {
  title: string;
  description: string;
  tone: "info" | "success" | "error";
}

export interface EventSummary {
  eventId: number;
  eventType: EventType;
  message: string;
}
