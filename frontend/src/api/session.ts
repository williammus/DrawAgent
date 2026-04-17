import { http } from "../lib/http";
import type { SessionDeleteResponse, SessionInitResponse } from "../types/api";

export function initSession() {
  return http<SessionInitResponse>("/api/session/init", {
    method: "POST",
  });
}

export function deleteSession(sessionId: string) {
  return http<SessionDeleteResponse>(`/api/session/${sessionId}`, {
    method: "DELETE",
  });
}
