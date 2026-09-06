import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Authentication } from './accounts/Authentication';
import { SessionPages } from './SessionPages';

export function App() {
  const { t, i18n } = useTranslation();
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    document.documentElement.lang = i18n.language;
    document.title = t('app.title');
  }, [i18n.language, t]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    setStatus('loading');
    void fetch('/api/health', { signal: controller.signal })
      .then(async response => {
        if (!response.ok || (await response.json()).status !== 'ok') {
          throw new Error('health_unavailable');
        }
        if (active) setStatus('ok');
      })
      .catch(() => { if (active) setStatus('error'); })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; controller.abort(); clearTimeout(timeout); };
  }, [attempt]);

  return <main>
    <header className="app-header">
      <div className="app-brand"><span className="app-document-icon" aria-hidden="true" /><h1>{t('app.title')}</h1></div>
      <p className="app-description">{t('app.description')}</p>
      <p className={`app-connection app-connection-${status}`} role="status">{t(`health.${status}`)}</p>
    </header>
    <Authentication>{(session, actions) => session.user && <SessionPages
      session={session} accept={actions.accept}
      setAuthBusy={actions.setBusy} authBusy={actions.busy}
      setLeaveGuard={actions.setLeaveGuard}
    />}</Authentication>
    {status === 'error' && <button onClick={() => setAttempt(value => value + 1)}>{t('health.retry')}</button>}
  </main>;
}
