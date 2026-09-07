import { useEffect, useRef, useState } from "react";
import type { paths } from "../../generated/api";
import { api } from "../api";
import type { EditorSnapshot } from "../editor/adapter";
import { newKey } from "../library/operationKey";
import type { Resource } from "../library/useLibrary";
import type { EditingCredentials } from "./useEditingLease";

type Body = paths["/api/documents/{identity}/versions"]["post"]["requestBody"]["content"]["application/json"];
type Attempt = { key: string; body: Body; revision: number; review: boolean };
const initial = () => ({ busy: false, pending: false, error: "", acknowledged: 0, reviewSaved: false, conflict: false });

/** A retry owns its original detached snapshot even when the live draft advances. */
export function useDocumentSave({ identity, csrfToken, read, credentials, onSaved, onAccessLost }: {
  identity: string; csrfToken: string; read: () => EditorSnapshot | null;
  credentials: () => EditingCredentials | undefined; onSaved: (resource: Resource) => void;
  onAccessLost: (error: string) => void;
}) {
  const [state, setState] = useState(initial);
  const pending = useRef<Attempt | null>(null);
  const running = useRef(false);
  const lifetime = useRef(new AbortController());
  useEffect(() => {
    const controller = new AbortController(); lifetime.current = controller;
    return () => controller.abort();
  }, [identity]);
  function reset() {
    lifetime.current.abort(); lifetime.current = new AbortController();
    pending.current = null; running.current = false; setState(initial());
  }
  async function save() {
    if (running.current || state.conflict) return;
    let attempt = pending.current;
    if (!attempt) {
      const snapshot = read(), lease = credentials();
      if (!snapshot || !lease) { setState(previous => ({ ...previous, error: "lease_lost" })); return; }
      if (snapshot.composing || !snapshot.fieldValuesValid) {
        setState(previous => ({ ...previous, error: snapshot.composing ? "composing" : "invalid_fields" })); return;
      }
      if (snapshot.revision === state.acknowledged) return;
      const document = snapshot.document as Record<string, unknown>;
      attempt = { key: newKey(), body: { ...lease, document }, revision: snapshot.revision,
        review: !!(document.attrs as { review?: unknown } | undefined)?.review };
      pending.current = attempt;
    }
    const controller = new AbortController(), session = lifetime.current;
    const cancel = () => controller.abort();
    session.signal.addEventListener("abort", cancel, { once: true });
    const timeout = setTimeout(cancel, 45000);
    running.current = true;
    setState(previous => ({ ...previous, busy: true, pending: true, error: "" }));
    try {
      const result = await api.POST("/api/documents/{identity}/versions", {
        params: { path: { identity }, header: { "idempotency-key": attempt.key } }, headers: { "X-CSRF-Token": csrfToken },
        body: attempt.body, signal: controller.signal,
      });
      if (session.signal.aborted) return;
      if (result.data) {
        pending.current = null;
        if (result.data.saved_version_id !== result.data.resource.current_version_id) {
          setState(previous => ({ ...previous, pending: false, error: "revision", conflict: true }));
          onAccessLost("revision"); return;
        }
        setState(previous => ({ ...previous, pending: false, acknowledged: attempt.revision,
          reviewSaved: previous.reviewSaved || attempt.review }));
        onSaved(result.data.resource);
      } else {
        const failure = result.error.error;
        const error = failure.code === "operation_conflict" ? String(failure.parameters?.reason ?? "revision") : failure.code;
        const uncertain = result.response.status >= 500 || failure.code === "operation_in_progress";
        if (!uncertain) pending.current = null;
        setState(previous => ({ ...previous, pending: uncertain, error, conflict: error === "revision" }));
        if (["revision", "lease_lost", "authentication_required", "forbidden"].includes(error)) onAccessLost(error);
      }
    } catch {
      if (!session.signal.aborted) setState(previous => ({ ...previous, error: "internal_error" }));
    } finally {
      clearTimeout(timeout); session.signal.removeEventListener("abort", cancel);
      if (!session.signal.aborted) { running.current = false; setState(previous => ({ ...previous, busy: false })); }
    }
  }
  return { ...state, save, reset };
}
