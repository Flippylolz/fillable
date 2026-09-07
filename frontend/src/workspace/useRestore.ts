import { useEffect, useRef, useState } from "react";
import type { components } from "../../generated/api";
import { api } from "../api";
import { newKey } from "../library/operationKey";
import type { EditingCredentials } from "./useEditingLease";

type Version = components["schemas"]["VersionInfo"];
type Attempt = { selected: Version; body: EditingCredentials; key: string };
const initial = () => ({ busy: false, pending: null as Version | null, error: "", conflict: false });

/** Keep the original request and live draft until the restored pair is loaded. */
export function useRestore({ identity, csrfToken, credentials, onAccessLost, onRestored }: {
  identity: string; csrfToken: string; credentials: () => EditingCredentials | undefined;
  onAccessLost: (error: string) => void; onRestored: (content: components["schemas"]["ContentInfo"]) => void;
}) {
  const [state, setState] = useState(initial);
  const pending = useRef<Attempt | null>(null), running = useRef(false);
  const lifetime = useRef(new AbortController());
  useEffect(() => {
    const controller = new AbortController(); lifetime.current = controller;
    return () => controller.abort();
  }, [identity]);
  function reset() {
    lifetime.current.abort(); lifetime.current = new AbortController();
    pending.current = null; running.current = false; setState(initial());
  }
  async function restore(selected: Version) {
    if (running.current || state.conflict) return;
    let attempt = pending.current;
    if (!attempt) {
      const lease = credentials();
      if (!lease) { setState(previous => ({ ...previous, error: "lease_lost" })); return; }
      attempt = { selected, body: { ...lease }, key: newKey() }; pending.current = attempt;
    }
    const session = lifetime.current, controller = new AbortController();
    const cancel = () => controller.abort();
    session.signal.addEventListener("abort", cancel, { once: true });
    const timeout = setTimeout(cancel, 45000);
    let committed = false;
    running.current = true;
    setState({ busy: true, pending: attempt.selected, error: "", conflict: false });
    function conflict() {
      pending.current = null;
      setState(previous => ({ ...previous, pending: null, conflict: true, error: "revision" }));
      onAccessLost("revision");
    }
    try {
      const result = await api.POST("/api/documents/{identity}/versions/{version}/restore", {
        params: { path: { identity, version: attempt.selected.id }, header: { "idempotency-key": attempt.key } },
        headers: { "X-CSRF-Token": csrfToken }, body: attempt.body, signal: controller.signal,
      });
      if (session.signal.aborted) return;
      if (!result.data) {
        const failure = result.error.error;
        const error = failure.code === "operation_conflict" ? String(failure.parameters?.reason ?? "revision") : failure.code;
        const uncertain = result.response.status >= 500 || failure.code === "operation_in_progress";
        if (!uncertain) pending.current = null;
        setState(previous => ({ ...previous, pending: uncertain ? attempt.selected : null, error, conflict: error === "revision" }));
        if (["revision", "lease_lost", "authentication_required", "forbidden"].includes(error)) onAccessLost(error);
        return;
      }
      committed = true;
      if (result.data.saved_version_id !== result.data.resource.current_version_id) { conflict(); return; }
      const content = await api.GET("/api/documents/{identity}/versions/{version}/content", {
        params: { path: { identity, version: result.data.saved_version_id } }, signal: controller.signal,
      });
      if (session.signal.aborted) return;
      if (!content.data) { setState(previous => ({ ...previous, error: "restore_load" })); onAccessLost("revision"); return; }
      if (content.data.version.id !== result.data.saved_version_id || !content.data.version.is_current || content.data.version.restored_from_version_id !== attempt.selected.id) { conflict(); return; }
      pending.current = null; setState(initial());
      onRestored({ resource: result.data.resource, document: content.data.document });
    } catch {
      if (!session.signal.aborted) {
        setState(previous => ({ ...previous, error: committed ? "restore_load" : "internal_error" }));
        if (committed) onAccessLost("revision");
      }
    } finally {
      clearTimeout(timeout); session.signal.removeEventListener("abort", cancel);
      if (!session.signal.aborted) { running.current = false; setState(previous => ({ ...previous, busy: false })); }
    }
  }
  return { ...state, restore, reset };
}
