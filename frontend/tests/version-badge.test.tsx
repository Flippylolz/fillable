import { act, render, screen } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import { VersionBadge, commitVersion } from '../src/VersionBadge';
import { i18n, setLanguage } from '../src/i18n';

test.each([undefined, null, 123, '', '  ', 'abc123', 'abc1234!', 'not-a-commit'])('rejects invalid build metadata %s', value => {
  expect(commitVersion(value)).toBeNull();
});

test('resolves a full or short hexadecimal commit without guessing its source', () => {
  expect(commitVersion('  aBc1234deadbeef  ')).toBe('aBc1234');
  expect(commitVersion('abcdef0')).toBe('abcdef0');
});

test.each(['abcdef0123456789', undefined])('renders exact catalog text and updates accessible locale with metadata %s', async commit => {
  vi.stubEnv('VITE_APP_COMMIT_SHA', commit);
  await setLanguage('uk');
  const version = commit ? 'abcdef0' : 'development';
  const { container } = render(<I18nextProvider i18n={i18n}><VersionBadge /></I18nextProvider>);
  const badge = screen.getByLabelText(`Версія застосунку ${version}`);
  expect(badge.textContent).toBe(`version: ${version}`);
  expect(badge.querySelector('code')).toHaveTextContent(version);
  await act(() => setLanguage('en'));
  expect(screen.getByLabelText(`Application version ${version}`)).toBe(badge);
  expect(badge.textContent).toBe(`version: ${version}`);
  expect(container.querySelectorAll('.version-badge')).toHaveLength(1);
  vi.unstubAllEnvs();
});
