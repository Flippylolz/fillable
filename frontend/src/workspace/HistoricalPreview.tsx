import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { mountEditor, type EditorAdapter, type FieldSummary } from "../editor/adapter";

export function HistoricalPreview({ document }: { document: object }) {
  const { t } = useTranslation();
  const host = useRef<HTMLDivElement>(null), editor = useRef<EditorAdapter | null>(null);
  const initial = useRef(document);
  const [fields, setFields] = useState<FieldSummary[]>([]), [unsupported, setUnsupported] = useState(false);
  useEffect(() => {
    const view = mountEditor(host.current!, initial.current, { canEdit: () => false, onChange: () => {},
      onUpdate: presentation => { setFields(presentation.fields); setUnsupported(presentation.unsupported); } });
    editor.current = view;
    return () => { view.destroy(); editor.current = null; };
  }, []);
  useEffect(() => { editor.current!.setDocumentLabel(t("history.document")); }, [t]);
  return <div className="history-preview">
    {unsupported && <p>{t("history.unsupported")}</p>}
    <div className="document-canvas" ref={host} />
    <details className="history-fields"><summary>{t("history.savedFields")}</summary>
      {!fields.length ? <p>{t("history.noFields")}</p> : <dl>{fields.map(field => <div key={field.id}>
        <dt>{field.label}</dt><dd>{field.value}</dd>
      </div>)}</dl>}
    </details>
  </div>;
}
