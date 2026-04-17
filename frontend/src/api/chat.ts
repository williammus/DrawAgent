import { http } from "../lib/http";
import type { ChatMessageRequest, ChatMessageResponse } from "../types/api";

export function sendChatMessage(payload: ChatMessageRequest) {
  return http<ChatMessageResponse>("/api/chat/message", {
    method: "POST",
    bodyJson: payload,
  });
}
