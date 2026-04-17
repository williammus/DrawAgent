import { http } from "../lib/http";
import type { ArtifactResponse } from "../types/api";

export function getArtifacts(sessionId: string) {
  return http<ArtifactResponse>(`/api/artifacts/${sessionId}`);
}
