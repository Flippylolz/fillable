import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Authentication } from './accounts/Authentication';
import { SessionPages } from './SessionPages';

export function App() {
  const { t, i18n } = useTranslation();
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading');
  const [attempt, setAttempt] = useState(0);
  // The signed-in application replaces the public header with the gallery shell.
  const [signedIn, setSignedIn] = useState(false);

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

  return <main className={signedIn ? 'app-main-shell' : undefined}>
    {!signedIn && <header className="app-header">
      <a className="app-brand" href="/documents" aria-label={t('navigation.home')}><span className="app-document-icon" aria-hidden="true" /><h1>{t('app.title')}</h1></a>
      <p className="app-description">{t('app.description')}</p>
      <p className={`app-connection app-connection-${status}`} role="status">{t(`health.${status}`)}</p>
    </header>}
    <Authentication onPresenceChange={setSignedIn}>{(session, actions) => session.user && <SessionPages key={session.user.id}
      session={session} accept={actions.accept}
      setAuthBusy={actions.setBusy} authBusy={actions.busy} authPaused={actions.paused}
      setLeaveGuard={actions.setLeaveGuard} logout={actions.logout}
      connection={status} onRetry={() => setAttempt(value => value + 1)}
    />}</Authentication>
    {!signedIn && status === 'error' && <button onClick={() => setAttempt(value => value + 1)}>{t('health.retry')}</button>}
  </main>;
}
