import { useEffect, useState } from "react";

import { getHealthStatus } from "../../lib/api";
import type { HealthResponse } from "../../types/health";


type LoadState = "idle" | "loading" | "success" | "error";


export function HealthStatus() {
  const [state, setState] = useState<LoadState>("idle");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    let active = true;

    const load = async () => {
      setState("loading");
      try {
        const response = await getHealthStatus();
        if (!active) {
          return;
        }
        setHealth(response);
        setState("success");
      } catch (error) {
        if (!active) {
          return;
        }
        const message = error instanceof Error ? error.message : "Unknown error";
        setErrorMessage(message);
        setState("error");
      }
    };

    void load();

    return () => {
      active = false;
    };
  }, []);

  if (state === "loading" || state === "idle") {
    return <StatusCard tone="neutral" title="Checking backend" detail="Waiting for /healthz response." />;
  }

  if (state === "error") {
    return <StatusCard tone="error" title="Backend unavailable" detail={errorMessage} />;
  }

  return (
    <StatusCard
      tone="success"
      title="Backend reachable"
      detail={`${health?.service} · ${health?.environment} · v${health?.version}`}
    />
  );
}


type StatusCardProps = {
  tone: "neutral" | "success" | "error";
  title: string;
  detail: string;
};


function StatusCard({ tone, title, detail }: StatusCardProps) {
  const palette =
    tone === "success"
      ? "border-emerald-200 bg-emerald-50 text-emerald-900"
      : tone === "error"
        ? "border-rose-200 bg-rose-50 text-rose-900"
        : "border-slate-200 bg-slate-50 text-slate-700";

  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm ${palette}`}>
      <div className="font-semibold">{title}</div>
      <div className="mt-1 text-xs opacity-80">{detail}</div>
    </div>
  );
}
