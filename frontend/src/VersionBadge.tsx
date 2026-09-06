import { Trans, useTranslation } from 'react-i18next';
import './version-badge.css';

export function commitVersion(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const commit = value.trim();
  return /^[a-fA-F0-9]{7,}$/.test(commit) ? commit.slice(0, 7) : null;
}

export function VersionBadge() {
  const { t } = useTranslation();
  const version = commitVersion(import.meta.env.VITE_APP_COMMIT_SHA) ?? t('versionBadge.development');
  return <div className="version-badge" aria-label={t('versionBadge.ariaLabel', { version })}>
    <Trans i18nKey="versionBadge.text" values={{ version }} components={{ value: <code /> }} />
  </div>;
}
