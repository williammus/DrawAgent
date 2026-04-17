import { http } from "../lib/http";
import type { UploadDeleteResponse, UploadResponse } from "../types/api";

export async function uploadFiles(sessionId: string, files: File[]) {
  const formData = new FormData();
  formData.set("session_id", sessionId);
  for (const file of files) {
    formData.append("files", file);
  }

  return http<UploadResponse>("/api/upload", {
    method: "POST",
    body: formData,
  });
}

export function deleteUploadedFile(sessionId: string, fileId: string) {
  return http<UploadDeleteResponse>(`/api/upload/${sessionId}/${fileId}`, {
    method: "DELETE",
  });
}
