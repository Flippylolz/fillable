import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { I18nextProvider } from 'react-i18next';
/* Self-hosted interface fonts (OFL): Manrope covers Latin+Cyrillic UI text,
   Sora covers Latin headings; Ukrainian headings fall back to Manrope. */
import '@fontsource-variable/manrope/wght.css';
import '@fontsource-variable/sora/wght.css';
import './base.css';
import { App } from './App';
import { i18n } from './i18n';
import { VersionBadge } from './VersionBadge';

createRoot(document.getElementById('root')!).render(
  <StrictMode><I18nextProvider i18n={i18n}><App /><VersionBadge /></I18nextProvider></StrictMode>,
);
