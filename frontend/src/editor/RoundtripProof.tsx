import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { DocumentEditor } from "./DocumentEditor";

interface Snapshot {
  source: string;
  digest: string;
  model: object;
}

// Used only by the opt-in development entry, not the production application.
export function RoundtripProof() {
  const { t } = useTranslation();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [saved, setSaved] = useState<Blob | null>(null);
  const [generation, setGeneration] = useState(0);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [fieldValuesValid, setFieldValuesValid] = useState(true);
  const draft = useRef<object>({});
  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/prototype", { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("load_failed");
        const value = (await response.json()) as Snapshot;
        draft.current = value.model;
        setSnapshot(value);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, []);
  async function process(reopen: boolean) {
    setBusy(true);
    setFailed(false);
    try {
      const response = await fetch(
        `/api/prototype/${reopen ? "reopen" : "export"}`,
        {
          method: "POST",
          headers: {
            "Content-Type": reopen
              ? "application/octet-stream"
              : "application/json",
          },
          body: reopen
            ? saved
            : JSON.stringify({ ...snapshot, model: draft.current }),
        },
      );
      if (!response.ok) throw new Error("processing_failed");
      if (reopen) {
        const value = (await response.json()) as Snapshot;
        draft.current = value.model;
        setSnapshot(value);
        setGeneration((current) => current + 1);
      } else {
        const blob = await response.blob();
        setSaved(blob);
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "editor-proof.docx";
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button disabled={!snapshot || busy || !fieldValuesValid} onClick={() => void process(false)}>
        {t("editor.export")}
      </button>
      <button disabled={!saved || busy} onClick={() => void process(true)}>
        {t("editor.reopen")}
      </button>
      {failed && <p role="alert">{t("editor.failed")}</p>}
      {snapshot && (
        <DocumentEditor
          key={generation}
          initialDocument={snapshot.model}
          onFieldValidityChange={setFieldValuesValid}
          onDocumentChange={(value) => {
            draft.current = value;
          }}
        />
      )}
    </>
  );
}
