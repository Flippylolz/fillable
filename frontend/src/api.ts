import createClient from 'openapi-fetch';
import type { paths } from '../generated/api';
import { i18n } from './i18n';
import { sessionFetch } from './accounts/requestBoundary';

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: 'same-origin',
  fetch: sessionFetch,
});

export type ApiErrorParameters = Record<string, string | number>;

export function apiErrorMessage(code: string, parameters: ApiErrorParameters = {}) {
  switch (code) {
    case 'invalid_document': return i18n.t('errors.invalid_document');
    case 'unsupported_document': return i18n.t('errors.unsupported_document');
    case 'document_limit': return i18n.t('errors.document_limit');
    case 'quota_exceeded': return i18n.t('errors.quota_exceeded');
    case 'file_too_large': return i18n.t('errors.file_too_large');
    case 'storage_unavailable': return i18n.t('errors.storage_unavailable');
    case 'operation_conflict': return i18n.t('errors.operation_conflict');
    case 'operation_in_progress': return i18n.t('errors.operation_in_progress');
    case 'operation_aborted': return i18n.t('errors.operation_aborted');
    case 'upload_busy': return i18n.t('errors.upload_busy');
    case 'upload_timeout': return i18n.t('errors.upload_timeout');
    case 'current_password_invalid': return i18n.t('errors.current_password_invalid');
    case 'authentication_required': return i18n.t('errors.authentication_required');
    case 'invalid_credentials': return i18n.t('errors.invalid_credentials');
    case 'forbidden': return i18n.t('errors.forbidden');
    case 'rate_limited': return i18n.t('errors.rate_limited');
    case 'account_exists': return i18n.t('errors.account_exists');
    case 'dependencies_unavailable': return i18n.t('errors.dependencies_unavailable');
    case 'not_found': return i18n.t('errors.not_found');
    case 'method_not_allowed': return i18n.t('errors.method_not_allowed');
    case 'invalid_request': return typeof parameters.parameter === 'string' && parameters.parameter
      ? i18n.t('errors.invalid_request_parameter', { parameter: parameters.parameter })
      : i18n.t('errors.invalid_request');
    default: return i18n.t('errors.internal_error');
  }
}
