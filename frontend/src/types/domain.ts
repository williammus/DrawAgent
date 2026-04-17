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
  | "error";

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
  has_payload_logic: boolean;
  has_payload_style: boolean;
  has_payload_mapper: boolean;
  has_payload_review: boolean;
  has_payload_final: boolean;
  needs_clarification: boolean;
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

export interface LogicSpec {
  chart_title: string;
  core_method_summary: string;
  containers: Array<{
    container_id: string;
    name: string;
    description: string | null;
    children: string[];
  }>;
  nodes: Array<{
    node_id: string;
    label: string;
    description: string | null;
    node_type: string | null;
  }>;
  edges: Array<{
    source: string;
    target: string;
    label: string | null;
    relation: string | null;
  }>;
}

export interface StyleSpec {
  discipline: string;
  target_journal: string | null;
  primary_palette: string[];
  secondary_palette: string[];
  font_family: string;
  line_style: string;
  node_shape_rules: Record<string, string>;
  layout_style: string;
  legend_style: string;
  forbidden_visual_elements: string[];
  style_keywords: string[];
}

export interface MapperSpec {
  narrative_direction: string;
  section_layout: string[];
  module_positions: Record<string, string>;
  grouping_strategy: string;
  edge_style_mapping: Record<string, string>;
  visual_hierarchy: string[];
  annotation_strategy: string;
  legend_placement: string | null;
}

export interface ReviewSpec {
  passed: boolean;
  error_stage: ReviewErrorStage | null;
  reason: string;
  fix_suggestion: string[];
}

export interface PayloadFinal {
  final_prompt_en: string;
  final_prompt_cn: string;
  prompt_version: string;
  generation_notes: string[];
  ready_for_generation: boolean;
}

export interface ArtifactsBundle {
  session_id: string;
  payload_logic: LogicSpec | null;
  payload_style: StyleSpec | null;
  payload_mapper: MapperSpec | null;
  payload_review: ReviewSpec | null;
  payload_final: PayloadFinal | null;
}

export interface CleanupReport {
  ran_at: string;
  removed_sessions: string[];
  removed_directories: string[];
  failed_targets: string[];
  details: Record<string, unknown>;
}
