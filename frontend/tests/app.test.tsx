import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import { App } from '../src/App';
import { i18n, setLanguage, formatBytes, formatDate, formatNumber } from '../src/i18n';

// Connection/locale unit tests isolate auth; its real flows have separate tests and browser coverage.
vi.mock('../src/accounts/Authentication', () => ({ Authentication: () => null }));

beforeEach(async () => { await setLanguage('uk'); });
function mount() { return render(<I18nextProvider i18n={i18n}><App /></I18nextProvider>); }
const healthy = () => Promise.resolve({ ok: true, json: async () => ({ status: 'ok' }) });

test('storage sizes use readable decimal units and the selected locale', async () => {
  expect(formatBytes(0)).toBe('0 байтів');
  expect(formatBytes(999)).toBe('999 байтів');
  expect(formatBytes(1073741824)).toMatch(/1,07\s+ГБ/);
  await setLanguage('en');
  expect(formatBytes(1000)).toBe('1 kB');
  expect(formatBytes(2380376)).toBe('2.38 MB');
  expect(formatBytes(1073741824)).toBe('1.07 GB');
  expect(formatBytes(Number.MAX_SAFE_INTEGER)).toBe('9.01 PB');
});

test('defaults to Ukrainian and follows locale changes without remounting', async () => {
  const fetchMock = vi.fn(healthy);
  vi.stubGlobal('fetch', fetchMock);
  mount();
  expect(screen.getByRole('status')).toHaveTextContent('Перевіряємо');
  expect(await screen.findByText('З’єднання із сервером встановлено')).toBeVisible();
  await act(() => setLanguage('en'));
  expect(screen.getByRole('status')).toHaveTextContent('Connected to the server');
  expect(document.documentElement.lang).toBe('en');
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(formatNumber(1234.5)).toBe(new Intl.NumberFormat('en').format(1234.5));
  const date = new Date('2026-09-06T12:00:00Z');
  expect(formatDate(date, { timeZone: 'UTC' })).toBe(new Intl.DateTimeFormat('en', { timeZone: 'UTC' }).format(date));
  await act(() => setLanguage('invalid'));
  expect(document.documentElement.lang).toBe('uk');
  expect(formatNumber(1234.5)).toBe(new Intl.NumberFormat('uk-UA').format(1234.5));
  expect(formatDate(date)).toBe(new Intl.DateTimeFormat('uk-UA').format(date));
});

test.each([
  () => Promise.reject(new Error('offline')),
  () => Promise.resolve({ ok: false }),
  () => Promise.resolve({ ok: true, json: async () => ({ status: 'bad' }) }),
  () => Promise.resolve({ ok: true, json: async () => { throw new Error('invalid json'); } }),
])('shows a recoverable error and retries', async failure => {
  vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(failure).mockImplementation(healthy));
  mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Спробувати знову' }));
  expect(await screen.findByText('З’єднання із сервером встановлено')).toBeVisible();
});

test.each([true, false])('ignores late results after unmount', async success => {
  let resolve!: (value: unknown) => void;
  let reject!: (reason: Error) => void;
  const pending = new Promise((res, rej) => { resolve = res; reject = rej; });
  const mock = vi.fn().mockReturnValue(pending);
  vi.stubGlobal('fetch', mock);
  const view = mount();
  view.unmount();
  expect(mock.mock.calls[0][1].signal.aborted).toBe(true);
  await act(async () => {
    if (success) resolve(await healthy()); else reject(new Error('aborted'));
  });
});

test('times out an unresponsive request with a recoverable error', async () => {
  vi.useFakeTimers();
  vi.stubGlobal('fetch', vi.fn((_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('timeout')));
  })));
  try {
    mount();
    await act(() => vi.advanceTimersByTimeAsync(10000));
    expect(screen.getByRole('button')).toHaveTextContent('Спробувати знову');
  } finally { vi.useRealTimers(); }
});

test('real entry point mounts the application', async () => {
  vi.stubGlobal('fetch', vi.fn(healthy));
  document.body.innerHTML = '<div id="root"></div>';
  await act(async () => { await import('../src/main'); });
  await waitFor(() => expect(screen.getByRole('heading')).toHaveTextContent('Fillable'));
});
