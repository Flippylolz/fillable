import { useEffect, useRef, useState } from "react";
import type { components } from "../../generated/api";
import { api } from "../api";

type Resource = components["schemas"]["ResourceInfo"];
type Result = components["schemas"]["FieldsResult"];
type State = { key: string; status: Result["status"] | "loading"; snapshot: Result["snapshot"];
  error: string; busy: boolean; paused: boolean };
const initial = (key: string): State => ({ key, status: "loading", snapshot: null, error: "", busy: true, paused: false });

export function useDiscovery(resource: Resource | null, csrfToken: string) {
  const identity = resource?.id, version = resource?.current_version_id;
  const key = `${identity}:${version}`;
  const [state, setState] = useState(() => initial(key));
  const [request, setRequest] = useState({ start: false, revision: 0 });
  const consumed = useRef(-1);
  useEffect(() => {
    if (!identity || !version) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>, reads = 0;
    setState(initial(key));
    async function load(start: boolean) {
      try {
        const options = { params: { path: { identity: identity! } }, signal: controller.signal };
        if (start) {
          const intent = await api.POST("/api/documents/{identity}/processing", {
            ...options, headers: { "X-CSRF-Token": csrfToken },
          });
          if (controller.signal.aborted) return;
          if (intent.error) { setState({ ...initial(key), busy: false, error: intent.error.error.code }); return; }
        }
        const result = await api.GET("/api/documents/{identity}/fields", options);
        if (controller.signal.aborted) return;
        if (result.error) { setState({ ...initial(key), busy: false, error: result.error.error.code }); return; }
        const data = result.data;
        const status = data.source_version_id === version ? data.status : "stale";
        if (status === "succeeded" && !data.snapshot) throw new Error("invalid_result");
        const pending = status === "queued" || status === "running";
        const paused = pending && ++reads >= 60;
        setState({ key, status, snapshot: status === "succeeded" ? data.snapshot : null, error: "", busy: false, paused });
        if (pending && !paused) timer = setTimeout(() => void load(false), 2000);
      } catch {
        if (!controller.signal.aborted) setState({ ...initial(key), busy: false, error: "internal_error" });
      }
    }
    const start = request.start && consumed.current !== request.revision;
    consumed.current = request.revision;
    void load(start);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [identity, version, key, csrfToken, request]);
  return { ...(state.key === key ? state : initial(key)), reload: (start = false) => setRequest(previous => ({ start, revision: previous.revision + 1 })) };
}
