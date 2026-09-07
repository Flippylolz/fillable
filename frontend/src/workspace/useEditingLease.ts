import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { newKey } from "../library/operationKey";
import type { Resource } from "../library/useLibrary";

type Access = { status: "checking" | "active" | "paused"; error: string };
export function useEditingLease(resource: Resource | null, csrfToken: string) {
  const identity = resource?.id, version = resource?.current_version_id;
  const key = `${identity}:${version}:${csrfToken}`;
  const held = useRef({ key: "", deadline: 0 });
  const retry = useRef(() => {});
  const release = useRef<Promise<unknown>>(Promise.resolve());
  const [access, setAccess] = useState<Access>({ status: "checking", error: "" });
  const canEdit = useCallback(() => held.current.key === key && performance.now() < held.current.deadline, [key]);
  useEffect(() => {
    held.current = { key, deadline: 0 };
    setAccess({ status: "checking", error: "" });
    if (!identity || !version) { retry.current = () => {}; return; }
    const client = newKey();
    let alive = true, busy = false, generation: string | undefined;
    let renewal: ReturnType<typeof setTimeout>, expiry: ReturnType<typeof setTimeout>;
    let controller: AbortController | undefined;
    const previousRelease = release.current;
    const stopTimers = () => { clearTimeout(renewal); clearTimeout(expiry); };
    function pause(error: string) {
      stopTimers(); held.current.deadline = 0;
      setAccess({ status: "paused", error });
    }
    function relinquish() {
      if (!generation) return Promise.resolve();
      return api.POST("/api/documents/{identity}/editing-lease", {
        params: { path: { identity: identity! } }, headers: { "X-CSRF-Token": csrfToken }, keepalive: true,
        body: { action: "release", source_version_id: version!, client_id: client, lease_id: generation },
      }).catch(() => {});
    }
    async function run(action: "acquire" | "renew") {
      if (!alive || busy) return;
      busy = true;
      const priorDeadline = held.current.deadline;
      if (action === "acquire") { stopTimers(); held.current.deadline = 0; setAccess({ status: "checking", error: "" }); }
      const started = performance.now();
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), 10000);
      try {
        const result = await api.POST("/api/documents/{identity}/editing-lease", {
          params: { path: { identity: identity! } }, headers: { "X-CSRF-Token": csrfToken }, signal: controller.signal,
          body: { action, source_version_id: version!, client_id: client, ...(action === "renew" ? { lease_id: generation } : {}) },
        });
        if (!alive) return;
        if (!result.data) { pause(result.error.error.code === "operation_conflict" ? String(result.error.error.parameters?.reason ?? "lease_lost") : result.error.error.code); return; }
        const next = result.data;
        const deadline = started + Math.min(next.valid_for_seconds, 60) * 1000;
        if (next.status !== "active" || next.source_version_id !== version || !next.lease_id || !Number.isFinite(deadline) || deadline <= performance.now()
          || (action === "renew" && (!held.current.deadline || performance.now() >= priorDeadline))) { pause("lease_lost"); return; }
        generation = next.lease_id; held.current.deadline = deadline;
        stopTimers(); setAccess({ status: "active", error: "" });
        renewal = setTimeout(() => void run("renew"), 20000);
        expiry = setTimeout(() => pause("lease_lost"), Math.max(0, deadline - performance.now()));
      } catch { if (alive) pause("internal_error"); }
      finally { clearTimeout(timeout); busy = false; }
    }
    retry.current = () => { void run("acquire"); };
    // StrictMode's immediate effect replay cancels this before a request is sent.
    const initial = setTimeout(() => { void previousRelease.then(() => { if (alive) void run("acquire"); }); }, 0);
    const check = () => { if (held.current.deadline && !canEdit()) pause("lease_lost"); };
    const leave = () => { controller?.abort(); pause("lease_lost"); release.current = relinquish(); };
    window.addEventListener("focus", check); document.addEventListener("visibilitychange", check);
    window.addEventListener("pagehide", leave);
    return () => {
      alive = false; held.current.deadline = 0; clearTimeout(initial); stopTimers(); controller?.abort();
      window.removeEventListener("focus", check); document.removeEventListener("visibilitychange", check); window.removeEventListener("pagehide", leave);
      release.current = relinquish();
    };
  }, [identity, version, csrfToken, key, canEdit]);
  return { ...access, canEdit, retry: () => retry.current() };
}
