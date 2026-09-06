import { api, apiErrorMessage } from '../src/api';
import { i18n, setLanguage } from '../src/i18n';

test('generated client carries the typed success and error contracts', async () => {
  const mock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'ok' })))
    .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'dependencies_unavailable', parameters: { retry_seconds: 5 } } }), { status: 503 }));
  vi.stubGlobal('fetch', mock);
  expect((await api.GET('/api/health')).data?.status).toBe('ok');
  const result = await api.GET('/api/ready');
  expect(result.error?.error.code).toBe('dependencies_unavailable');
  expect(mock.mock.calls[0][0].url).toBe(`${window.location.origin}/api/health`);
  expect(mock.mock.calls[0][0].credentials).toBe('same-origin');
});

test.each(['uk', 'en'])('maps all codes and unknown failures to localized copy in %s', async language => {
  await setLanguage(language);
  for (const code of ['authentication_required', 'invalid_credentials', 'forbidden', 'rate_limited', 'account_exists', 'dependencies_unavailable', 'not_found', 'method_not_allowed', 'invalid_request', 'internal_error']) {
    expect(apiErrorMessage(code)).toBe(i18n.t(`errors.${code}`));
  }
  expect(apiErrorMessage('private unexpected response')).toBe(i18n.t('errors.internal_error'));
});
