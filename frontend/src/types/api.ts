import type {
  ArtifactsBundle,
  CleanupReport,
  ErrorCode,
  EventType,
  GenerateStatus,
  GeneratedImageMeta,
  SessionSummary,
  StoredFileMeta,
} from "./domain";

export interface ApiErrorDetail {
  code: ErrorCode;
  message: string;
  details?: Record<string, unknown> | null;
  request_id: string;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

export interface SessionInitResponse {
  session_id: string;
  summary: SessionSummary;
}

export interface SessionDeleteResponse {
  session_id: string;
  deleted: boolean;
  cleanup: CleanupReport | null;
}

export interface ChatMessageRequest {
  session_id: string;
  message: string;
  attachments?: string[];
}

export interface ChatMessageResponse {
  session_id: string;
  stage: SessionSummary["stage"];
  summary: SessionSummary;
  accepted: boolean;
  stream_url: string;
  response_message: string | null;
}

export interface UploadResponse {
  session_id: string;
  files: StoredFileMeta[];
}

export interface UploadDeleteResponse {
  session_id: string;
  file_id: string;
  deleted: boolean;
}

export type ArtifactResponse = ArtifactsBundle;

export interface GenerateResponse {
  session_id: string;
  stage: SessionSummary["stage"];
  status: GenerateStatus;
  generated_image_path: string | null;
  generated_image_meta: GeneratedImageMeta | null;
  download_url: string | null;
}

export interface SseEventEnvelope<TData extends SseEventData = SseEventData> {
  event_id: number;
  event_type: EventType;
  data: TData;
}

export interface BaseSseEvent {
  event_type: EventType;
  session_id: string;
  stage: SessionSummary["stage"];
  timestamp: string;
  request_id: string;
  message: string;
}

export interface StageStartedEvent extends BaseSseEvent {
  event_type: "stage_started";
}

export interface StageCompletedEvent extends BaseSseEvent {
  event_type: "stage_completed";
}

export interface ClarificationRequiredEvent extends BaseSseEvent {
  event_type: "clarification_required";
  clarification_question: string;
}

export interface ReviewFailedEvent extends BaseSseEvent {
  event_type: "review_failed";
  reason: string;
  error_stage: NonNullable<ArtifactsBundle["payload_review"]>["error_stage"];
  fix_suggestion: string[];
}

export interface PromptReadyEvent extends BaseSseEvent {
  event_type: "prompt_ready";
  prompt_version: string;
  ready_for_generation: boolean;
}

export interface ImageGeneratedEvent extends BaseSseEvent {
  event_type: "image_generated";
  image_path: string;
}

export interface WorkflowErrorEvent extends BaseSseEvent {
  event_type: "error";
  error_code: ErrorCode;
  details?: Record<string, unknown> | null;
}

export type SseEventData =
  | StageStartedEvent
  | StageCompletedEvent
  | ClarificationRequiredEvent
  | ReviewFailedEvent
  | PromptReadyEvent
  | ImageGeneratedEvent
  | WorkflowErrorEvent;
