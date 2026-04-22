export type StageName =
  | "idle"
  | "clarifying"
  | "planning"
  | "logic_ready"
  | "style_ready"
  | "mapping_ready"
  | "reviewing"
  | "prompt_ready"
  | "generating_image"
  | "completed"
  | "failed";

export type IntentType =
  | "unknown"
  | "new_task"
  | "modify_logic"
  | "modify_style"
  | "modify_layout"
  | "modify_logic_and_style"
  | "clarify";

export type ReviewErrorStage =
  | "input_guard"
  | "orchestrator"
  | "logician"
  | "style_configurator"
  | "visual_mapper"
  | "critic"
  | "summary_agent"
  | "image_adapter"
  | "unknown";

export type EventType =
  | "stage_started"
  | "stage_completed"
  | "clarification_required"
  | "review_failed"
  | "prompt_ready"
  | "image_generated"
  | "workflow_warning"
  | "error";

export type ReviewPhase = "post_plan" | "post_mapper";

export type WorkflowWarningType = "clarification_limit_reached" | "review_limit_reached";

export type WorkflowOperation =
  | "run_source_text"
  | "run_user_feedback"
  | "resume_user_feedback";

export type GenerateStatus = "accepted" | "running" | "completed" | "failed";

export type ErrorCode =
  | "input_validation_error"
  | "session_not_found"
  | "session_expired"
  | "resource_conflict"
  | "file_not_found"
  | "image_not_ready"
  | "artifact_validation_error"
  | "prompt_render_error"
  | "llm_invocation_error"
  | "review_rejected"
  | "adapter_invocation_error"
  | "http_error"
  | "request_validation_error"
  | "internal_server_error";

export interface SessionSummary {
  session_id: string;
  stage: StageName;
  intent: IntentType;
  has_source_text: boolean;
  source_text_locked: boolean;
  has_logic_artifact: boolean;
  has_style_artifact: boolean;
  has_plan_review_artifact: boolean;
  has_mapper_artifact: boolean;
  has_final_review_artifact: boolean;
  has_final_prompt_artifact: boolean;
  has_bypass_warning: boolean;
  needs_clarification: boolean;
  interrupted: boolean;
  user_confirmed: boolean;
  error_count: number;
  updated_at: string;
  expires_at: string;
}

export interface StoredFileMeta {
  file_id: string;
  original_name: string;
  stored_name: string;
  media_type: string;
  size_bytes: number;
  relative_path: string;
  uploaded_at: string;
}

export interface GeneratedImageMeta {
  file_name: string;
  media_type: string;
  size_bytes: number;
  relative_path: string;
  provider: string;
  generated_at: string;
}

export interface TextArtifact {
  tool_name: string;
  content: string;
  prompt_version: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
}

export interface WorkflowWarning {
  warning_type: WorkflowWarningType;
  message: string;
  loop_id: string;
  review_phase: ReviewPhase | null;
  created_at: string;
}

export interface ArtifactsBundle {
  session_id: string;
  logic_artifact: TextArtifact | null;
  style_artifact: TextArtifact | null;
  plan_review_artifact: TextArtifact | null;
  mapper_artifact: TextArtifact | null;
  final_review_artifact: TextArtifact | null;
  final_prompt_artifact: TextArtifact | null;
}

export interface CleanupReport {
  ran_at: string;
  removed_sessions: string[];
  removed_directories: string[];
  failed_targets: string[];
  details: Record<string, unknown>;
}
