import { create } from "zustand";

import type { ArtifactsBundle, SessionSummary, WorkflowWarning } from "../types/domain";
import type { ApiErrorDetail, SseEventData } from "../types/api";
import type {
  AppNotice,
  ComposerMode,
  EventStreamStatus,
  UIMessage,
  WorkspaceStatus,
} from "../types/ui";

interface AppState {
  sessionId: string | null;
  summary: SessionSummary | null;
  sourceText: string;
  sourceTextLocked: boolean;
  artifacts: ArtifactsBundle | null;
  latestEventId: number;
  eventStreamStatus: EventStreamStatus;
  generatedImageUrl: string | null;
  lastError: ApiErrorDetail | null;
  messages: UIMessage[];
  isWorkflowRunning: boolean;
  isGeneratingImage: boolean;
  isPromptReady: boolean;
  clarificationQuestion: string | null;
  workflowWarnings: WorkflowWarning[];
  artifactDrawerOpen: boolean;
  composerMode: ComposerMode;
  workspaceStatus: WorkspaceStatus;
  notice: AppNotice | null;
  bootstrapped: boolean;
  setSession: (sessionId: string, summary: SessionSummary) => void;
  setSummary: (summary: SessionSummary) => void;
  setSourceText: (text: string) => void;
  syncSourceTextLock: (locked: boolean) => void;
  setArtifacts: (artifacts: ArtifactsBundle | null) => void;
  setLatestEventId: (eventId: number) => void;
  setEventStreamStatus: (status: EventStreamStatus) => void;
  setGeneratedImageUrl: (url: string | null) => void;
  setLastError: (error: ApiErrorDetail | null) => void;
  addMessage: (message: UIMessage) => void;
  replaceThinkingMessage: (text: string) => void;
  clearThinkingMessages: () => void;
  setClarification: (question: string | null) => void;
  addWorkflowWarning: (warning: WorkflowWarning) => void;
  setArtifactDrawerOpen: (open: boolean) => void;
  setComposerMode: (mode: ComposerMode) => void;
  setWorkspaceStatus: (status: WorkspaceStatus) => void;
  setNotice: (notice: AppNotice | null) => void;
  markBootstrapped: () => void;
  resetForNewSession: () => void;
  applySseEvent: (eventId: number, event: SseEventData) => void;
}

export function createInitialAppState() {
  return {
    sessionId: null,
    summary: null,
    sourceText: "",
    sourceTextLocked: false,
    artifacts: null,
    latestEventId: 0,
    eventStreamStatus: "connecting" as EventStreamStatus,
    generatedImageUrl: null,
    lastError: null,
    messages: [] as UIMessage[],
    isWorkflowRunning: false,
    isGeneratingImage: false,
    isPromptReady: false,
    clarificationQuestion: null,
    workflowWarnings: [] as WorkflowWarning[],
    artifactDrawerOpen: false,
    composerMode: "default" as ComposerMode,
    workspaceStatus: "bootstrapping" as WorkspaceStatus,
    notice: null as AppNotice | null,
    bootstrapped: false,
  };
}

const initialState = createInitialAppState();

export const useAppStore = create<AppState>((set) => ({
  ...initialState,
  setSession: (sessionId, summary) =>
    set((state) => ({
      sessionId,
      summary,
      sourceTextLocked: summary.source_text_locked,
      sourceText: summary.has_source_text ? state.sourceText : "",
    })),
  setSummary: (summary) =>
    set((state) => ({
      summary,
      sourceTextLocked: summary.source_text_locked,
      workspaceStatus: deriveWorkspaceStatus(summary.stage, state.workspaceStatus),
      isPromptReady: summary.has_final_prompt_artifact && summary.stage === "prompt_ready",
    })),
  setSourceText: (sourceText) =>
    set({
      sourceText,
    }),
  syncSourceTextLock: (sourceTextLocked) =>
    set({
      sourceTextLocked,
    }),
  setArtifacts: (artifacts) =>
    set({
      artifacts,
      isPromptReady: Boolean(artifacts?.final_prompt_artifact),
    }),
  setLatestEventId: (eventId) =>
    set((state) => ({
      latestEventId: Math.max(state.latestEventId, eventId),
    })),
  setEventStreamStatus: (eventStreamStatus) =>
    set({
      eventStreamStatus,
    }),
  setGeneratedImageUrl: (generatedImageUrl) =>
    set({
      generatedImageUrl,
    }),
  setLastError: (lastError) =>
    set({
      lastError,
    }),
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),
  replaceThinkingMessage: (text) =>
    set((state) => {
      const existingIndex = state.messages.findIndex((message) => message.kind === "thinking");
      if (existingIndex === -1) {
        return {
          messages: [
            ...state.messages,
            {
              id: crypto.randomUUID(),
              kind: "thinking",
              text,
              timestamp: new Date().toISOString(),
            },
          ],
        };
      }

      const nextMessages = [...state.messages];
      nextMessages[existingIndex] = {
        ...nextMessages[existingIndex],
        text,
        timestamp: new Date().toISOString(),
      };
      return { messages: nextMessages };
    }),
  clearThinkingMessages: () =>
    set((state) => ({
      messages: state.messages.filter((message) => message.kind !== "thinking"),
    })),
  setClarification: (question) =>
    set({
      clarificationQuestion: question,
      composerMode: question ? "clarification" : "default",
    }),
  addWorkflowWarning: (warning) =>
    set((state) => ({
      workflowWarnings: [...state.workflowWarnings, warning],
    })),
  setArtifactDrawerOpen: (artifactDrawerOpen) =>
    set({
      artifactDrawerOpen,
    }),
  setComposerMode: (composerMode) =>
    set({
      composerMode,
    }),
  setWorkspaceStatus: (workspaceStatus) =>
    set({
      workspaceStatus,
      isWorkflowRunning: workspaceStatus === "workflow_running",
      isGeneratingImage: workspaceStatus === "image_generating",
    }),
  setNotice: (notice) =>
    set({
      notice,
    }),
  markBootstrapped: () =>
    set({
      bootstrapped: true,
    }),
  resetForNewSession: () =>
    set({
      ...createInitialAppState(),
      bootstrapped: true,
    }),
  applySseEvent: (eventId, event) =>
    set((state) => {
      const nextState: Partial<AppState> = {
        latestEventId: Math.max(state.latestEventId, eventId),
      };

      if (state.summary && event.session_id === state.summary.session_id) {
        nextState.summary = {
          ...state.summary,
          stage: event.stage,
          updated_at: event.timestamp,
          needs_clarification: event.event_type === "clarification_required",
          interrupted: event.event_type === "clarification_required",
        };
      }

      switch (event.event_type) {
        case "stage_started":
          nextState.isWorkflowRunning = true;
          nextState.workspaceStatus = event.stage === "generating_image" ? "image_generating" : "workflow_running";
          nextState.isGeneratingImage = event.stage === "generating_image";
          break;
        case "stage_completed":
          nextState.workspaceStatus = deriveWorkspaceStatus(event.stage, state.workspaceStatus);
          break;
        case "clarification_required":
          nextState.workspaceStatus = "waiting_clarification";
          nextState.composerMode = "clarification";
          nextState.clarificationQuestion = event.question;
          nextState.isWorkflowRunning = false;
          break;
        case "review_failed":
          nextState.workspaceStatus = "workflow_running";
          break;
        case "workflow_warning": {
          const warning = {
            warning_type: event.warning_type,
            message: event.message,
            loop_id: event.loop_id,
            review_phase: event.review_phase,
            created_at: event.timestamp,
          };
          nextState.workflowWarnings = [...state.workflowWarnings, warning];
          if (nextState.summary) {
            nextState.summary = {
              ...nextState.summary,
              has_bypass_warning: true,
            };
          }
          break;
        }
        case "prompt_ready":
          nextState.workspaceStatus = "prompt_reviewing";
          nextState.isPromptReady = true;
          nextState.isWorkflowRunning = false;
          nextState.clarificationQuestion = null;
          nextState.composerMode = "default";
          break;
        case "image_generated":
          nextState.workspaceStatus = "completed";
          nextState.isGeneratingImage = false;
          nextState.isWorkflowRunning = false;
          nextState.generatedImageUrl = `/api/download/${event.session_id}`;
          break;
        case "error":
          nextState.workspaceStatus = "failed";
          nextState.isGeneratingImage = false;
          nextState.isWorkflowRunning = false;
          break;
      }

      return nextState as AppState;
    }),
}));

function deriveWorkspaceStatus(stage: SessionSummary["stage"], current: WorkspaceStatus): WorkspaceStatus {
  switch (stage) {
    case "idle":
      return "idle";
    case "clarifying":
      return "waiting_clarification";
    case "prompt_ready":
      return "prompt_reviewing";
    case "generating_image":
      return "image_generating";
    case "completed":
      return "completed";
    case "failed":
      return "failed";
    default:
      return current === "bootstrapping" ? "idle" : "workflow_running";
  }
}
