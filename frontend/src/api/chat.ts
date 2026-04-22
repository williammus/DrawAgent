import { http } from "../lib/http";
import type { ChatResumeRequest, ChatRunRequest, ChatWorkflowResponse } from "../types/api";

export function runWorkflow(payload: ChatRunRequest) {
  return http<ChatWorkflowResponse>("/api/chat/run", {
    method: "POST",
    bodyJson: payload,
  });
}

export function resumeWorkflow(payload: ChatResumeRequest) {
  return http<ChatWorkflowResponse>("/api/chat/resume", {
    method: "POST",
    bodyJson: payload,
  });
}
