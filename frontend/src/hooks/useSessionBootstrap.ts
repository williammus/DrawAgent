import { useEffect } from "react";

import { initSession } from "../api/session";
import { ApiError } from "../lib/http";
import { useAppStore } from "../store/useAppStore";

export function useSessionBootstrap() {
  const sessionId = useAppStore((state) => state.sessionId);
  const setSession = useAppStore((state) => state.setSession);
  const setWorkspaceStatus = useAppStore((state) => state.setWorkspaceStatus);
  const setLastError = useAppStore((state) => state.setLastError);
  const addMessage = useAppStore((state) => state.addMessage);
  const bootstrapped = useAppStore((state) => state.bootstrapped);
  const markBootstrapped = useAppStore((state) => state.markBootstrapped);

  useEffect(() => {
    if (bootstrapped || sessionId) {
      return;
    }

    let active = true;

    const bootstrap = async () => {
      setWorkspaceStatus("bootstrapping");
      try {
        const response = await initSession();
        if (!active) {
          return;
        }
        setSession(response.session_id, response.summary);
        setWorkspaceStatus("idle");
        addMessage({
          id: crypto.randomUUID(),
          kind: "assistant",
          timestamp: new Date().toISOString(),
          text: "会话已创建。请先在上方输入完整绘图内容，系统会在需要时主动追问，并在 Prompt 准备好后让你确认是否出图。",
        });
      } catch (error) {
        if (!active) {
          return;
        }
        setWorkspaceStatus("failed");
        if (error instanceof ApiError) {
          setLastError(error.detail);
          addMessage({
            id: crypto.randomUUID(),
            kind: "error",
            timestamp: new Date().toISOString(),
            text: error.detail?.message ?? "会话初始化失败。",
          });
        }
      } finally {
        if (active) {
          markBootstrapped();
        }
      }
    };

    void bootstrap();

    return () => {
      active = false;
    };
  }, [
    addMessage,
    bootstrapped,
    markBootstrapped,
    sessionId,
    setLastError,
    setSession,
    setWorkspaceStatus,
  ]);
}
