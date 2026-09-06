import createClient from 'openapi-fetch';
import type { paths } from '../generated/api';
import { i18n } from './i18n';

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: 'same-origin',
  fetch: request => fetch(request),
});

export function apiErrorMessage(code: string) {
  switch (code) {
    case 'dependencies_unavailable': return i18n.t('errors.dependencies_unavailable');
    case 'not_found': return i18n.t('errors.not_found');
    case 'method_not_allowed': return i18n.t('errors.method_not_allowed');
    case 'invalid_request': return i18n.t('errors.invalid_request');
    default: return i18n.t('errors.internal_error');
  }
}
