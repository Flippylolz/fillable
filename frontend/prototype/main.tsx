// Development-only corpus harness; Vite's production entry excludes this file.
import { createRoot } from "react-dom/client";
import { I18nextProvider, useTranslation } from "react-i18next";
import { i18n, setLanguage } from "../src/i18n";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import document from "./document.json";
function Prototype() {
  const { t } = useTranslation();
  return (
    <>
      <button onClick={() => void setLanguage("uk")}>{t("language.uk")}</button>
      <button onClick={() => void setLanguage("en")}>{t("language.en")}</button>
      <DocumentEditor initialDocument={document} />
    </>
  );
}
createRoot(window.document.getElementById("root")!).render(
  <I18nextProvider i18n={i18n}>
    <Prototype />
  </I18nextProvider>,
);
