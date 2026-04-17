import { useEffect, useState } from "react";

import { formatRelativeTime } from "../lib/format";

export function useCountdown(targetIso: string | null): string {
  const [value, setValue] = useState(() => (targetIso ? formatRelativeTime(targetIso) : "--:--"));

  useEffect(() => {
    if (!targetIso) {
      setValue("--:--");
      return;
    }

    setValue(formatRelativeTime(targetIso));
    const timer = window.setInterval(() => {
      setValue(formatRelativeTime(targetIso));
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, [targetIso]);

  return value;
}
