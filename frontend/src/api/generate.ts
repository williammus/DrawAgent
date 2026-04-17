import { http } from "../lib/http";
import type { GenerateResponse } from "../types/api";

export function generateImage(sessionId: string) {
  return http<GenerateResponse>(`/api/generate/${sessionId}`, {
    method: "POST",
  });
}
