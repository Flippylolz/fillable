import { useEffect, useRef } from "react";

/** Debounce edits, not polling renders. The caller rechecks live editor authority. */
export function useAutosave({ enabled, revision, acknowledged, paused, save }: {
  enabled: boolean; revision: number; acknowledged: number; paused: boolean; save: () => void;
}) {
  const latest = useRef(save); latest.current = save;
  useEffect(() => {
    if (!enabled || paused || revision === acknowledged) return;
    const timer = setTimeout(() => latest.current(), 2000);
    return () => clearTimeout(timer);
  }, [enabled, revision, acknowledged, paused]);
}
