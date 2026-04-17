import { create } from "zustand";

import type {
  ArtifactsBundle,
  SessionSummary,
  StoredFileMeta,
} from "../types/domain";
import type { ApiErrorDetail, SseEventData } from "../types/api";
import type { AppNotice, ComposerMode, UIMessage, WorkspaceStatus } from "../types/ui";

interface AppState {
  sessionId: string | null;
  summary: SessionSummary | null;
  uploadedFiles: StoredFileMeta[];
  artifacts: ArtifactsBundle | null;
  latestEventId: number;
  eventStreamConnected: boolean;
  generatedImageUrl: string | null;
  lastError: ApiErrorDetail | null;
  messages: UIMessage[];
  isWorkflowRunning: boolean;
  isGeneratingImage: boolean;
  isPromptReady: boolean;
  clarificationQuestion: string | null;
  selectedAttachmentIds: string[];
  artifactDrawerOpen: boolean;
  composerMode: ComposerMode;
  workspaceStatus: WorkspaceStatus;
  notice: AppNotice | null;
  bootstrapped: boolean;
  setSession: (sessionId: string, summary: SessionSummary) => void;
  setSummary: (summary: SessionSummary) => void;
  setUploadedFiles: (files: StoredFileMeta[]) => void;
  addUploadedFiles: (files: StoredFileMeta[]) => void;
  removeUploadedFile: (fileId: string) => void;
  setArtifacts: (artifacts: ArtifactsBundle | null) => void;
  setLatestEventId: (eventId: number) => void;
  setEventStreamConnected: (connected: boolean) => void;
  setGeneratedImageUrl: (url: string | null) => void;
  setLastError: (error: ApiErrorDetail | null) => void;
  addMessage: (message: UIMessage) => void;
  replaceThinkingMessage: (text: string) => void;
  clearThinkingMessages: () => void;
  setClarification: (question: string | null) => void;
  setSelectedAttachmentIds: (fileIds: string[]) => void;
  toggleAttachmentSelection: (fileId: string) => void;
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
    uploadedFiles: [],
    artifacts: null,
    latestEventId: 0,
    eventStreamConnected: false,
    generatedImageUrl: null,
    lastError: null,
    messages: [] as UIMessage[],
    isWorkflowRunning: false,
    isGeneratingImage: false,
    isPromptReady: false,
    clarificationQuestion: null,
    selectedAttachmentIds: [] as string[],
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
    set({
      sessionId,
      summary,
    }),
  setSummary: (summary) =>
    set((state) => ({
      summary,
      workspaceStatus: deriveWorkspaceStatus(summary.stage, state.workspaceStatus),
      isPromptReady: summary.has_payload_final && summary.stage === "prompt_ready",
    })),
  setUploadedFiles: (files) =>
    set({
      uploadedFiles: files,
      selectedAttachmentIds: [],
    }),
  addUploadedFiles: (files) =>
    set((state) => ({
      uploadedFiles: [...state.uploadedFiles, ...files],
      selectedAttachmentIds: [],
    })),
  removeUploadedFile: (fileId) =>
    set((state) => ({
      uploadedFiles: state.uploadedFiles.filter((file) => file.file_id !== fileId),
      selectedAttachmentIds: state.selectedAttachmentIds.filter((id) => id !== fileId),
    })),
  setArtifacts: (artifacts) =>
    set({
      artifacts,
      isPromptReady: Boolean(artifacts?.payload_final?.ready_for_generation),
    }),
  setLatestEventId: (eventId) =>
    set((state) => ({
      latestEventId: Math.max(state.latestEventId, eventId),
    })),
  setEventStreamConnected: (connected) =>
    set({
      eventStreamConnected: connected,
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
  setSelectedAttachmentIds: (selectedAttachmentIds) =>
    set({
      selectedAttachmentIds,
    }),
  toggleAttachmentSelection: (fileId) =>
    set((state) => {
      const exists = state.selectedAttachmentIds.includes(fileId);
      return {
        selectedAttachmentIds: exists
          ? state.selectedAttachmentIds.filter((id) => id !== fileId)
          : [...state.selectedAttachmentIds, fileId],
      };
    }),
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
          nextState.clarificationQuestion = event.clarification_question;
          nextState.isWorkflowRunning = false;
          break;
        case "review_failed":
          nextState.workspaceStatus = "workflow_running";
          break;
        case "prompt_ready":
          nextState.workspaceStatus = "prompt_reviewing";
          nextState.isPromptReady = event.ready_for_generation;
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
