import { useCallback } from "react";

import { getArtifacts } from "../api/artifacts";
import { ApiError } from "../lib/http";
import { useAppStore } from "../store/useAppStore";

export function useArtifacts() {
  const sessionId = useAppStore((state) => state.sessionId);
  const setArtifacts = useAppStore((state) => state.setArtifacts);
  const setLastError = useAppStore((state) => state.setLastError);
  const setNotice = useAppStore((state) => state.setNotice);

  const refreshArtifacts = useCallback(async () => {
    if (!sessionId) {
      return null;
    }

    try {
      const response = await getArtifacts(sessionId);
      setArtifacts(response);
      return response;
    } catch (error) {
      if (error instanceof ApiError) {
        setLastError(error.detail);
        setNotice({
          title: "获取结构化产物失败",
          description: error.detail?.message ?? error.message,
          tone: "error",
        });
      }
      return null;
    }
  }, [sessionId, setArtifacts, setLastError, setNotice]);

  return {
    refreshArtifacts,
  };
}
