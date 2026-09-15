import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { components } from "../../generated/api";
import { api } from "../api";
import { mountEditor } from "../editor/adapter";
import { useSourceLayout } from "../editor/SourceLayout";
import type { Resource } from "./useLibrary";
import "../editor/editor.css";
import "prosemirror-view/style/prosemirror.css";

type Content = components["schemas"]["ContentInfo"];

function SavedCover({ content }: { content: Content }) {
  const host = useRef<HTMLDivElement>(null);
  const layout = useSourceLayout(content.presentation);
  useEffect(() => {
    const node = host.current!;
    const editor = mountEditor(node, content.document, {
      presentation: content.presentation, canEdit: () => false, onChange: () => {}, onUpdate: () => {},
    });
    // Keep source page geometry and source-node views (including drawn shapes).
    // The card clips the miniature document; it never becomes an editor surface.
    const fit = () => {
      node.style.zoom = "1";
      node.style.width = "794px";
      const width = node.querySelector<HTMLElement>('section[data-part="word/document.xml"]')?.offsetWidth || 794;
      node.style.width = `${width}px`;
      node.style.zoom = String(Math.min(0.25, (node.parentElement!.clientWidth || width) / Math.max(width, node.scrollWidth)));
    };
    fit();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(fit);
    observer?.observe(node.parentElement!);
    window.addEventListener("resize", fit);
    return () => { observer?.disconnect(); window.removeEventListener("resize", fit); editor.destroy(); };
  }, [content]);
  return <div className="library-preview" data-layout={layout.scope} inert>
    <style>{layout.rules}</style><div className="library-preview-content document-canvas" ref={host} />
  </div>;
}

export function DocumentCover({ item }: { item: Resource }) {
  const { t } = useTranslation();
  const [content, setContent] = useState<Content | null>(null);
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    setContent(null);
    if (!item.preview_ready || item.deletion_pending) return;
    const controller = new AbortController();
    let started = false;
    function load() {
      if (started) return;
      started = true;
      void api.GET("/api/documents/{identity}/preview", {
        params: { path: { identity: item.id }, query: { source_version_id: item.current_version_id } }, signal: controller.signal,
      }).then(result => {
        if (!controller.signal.aborted && result.data?.resource.id === item.id && result.data.resource.current_version_id === item.current_version_id) setContent(result.data);
      }).catch(() => {});
    }
    const observer = typeof IntersectionObserver === "undefined" ? null : new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) { load(); observer?.disconnect(); }
    });
    if (observer) observer.observe(host.current!);
    else load();
    return () => { controller.abort(); observer?.disconnect(); };
  }, [item.id, item.current_version_id, item.preview_ready, item.deletion_pending]);
  const current = !item.deletion_pending && content?.resource.id === item.id && content.resource.current_version_id === item.current_version_id;
  return <div className="library-document-cover" ref={host} aria-hidden="true">
    {current ? <SavedCover content={content} /> : <span className="library-paper library-preview-placeholder" />}
    <span className="library-format">{t("library.format")}</span>
  </div>;
}
