import { HttpErrorResponse } from '@angular/common/http';
import { ApiErrorBody, JsonObject } from '../models/api.models';

export interface AppHttpError {
  status: number;
  kind: 'validation' | 'unauthenticated' | 'unauthorized' | 'not-found' | 'conflict' | 'server' | 'network' | 'timeout' | 'unknown';
  message: string;
  diagnostics?: JsonObject | string;
}

export function toAppHttpError(error: unknown): AppHttpError {
  if (isAppHttpError(error)) return error;
  if (error instanceof HttpErrorResponse) {
    const body = error.error as ApiErrorBody | string | null;
    const message = messageFromBody(body) ?? defaultMessage(error.status);
    return {
      status: error.status,
      kind: errorKind(error.status, error.name),
      message,
      diagnostics: typeof body === 'string' ? body : (body ?? undefined) as JsonObject | undefined,
    };
  }
  return { status: 0, kind: 'unknown', message: error instanceof Error ? error.message : 'An unexpected error occurred.' };
}

export function isAppHttpError(value: unknown): value is AppHttpError {
  return typeof value === 'object' && value !== null && 'kind' in value && 'message' in value;
}

function errorKind(status: number, errorName: string): AppHttpError['kind'] {
  if (errorName === 'TimeoutError') return 'timeout';
  if (status === 0) return 'network';
  if (status === 400 || status === 422) return 'validation';
  if (status === 401) return 'unauthenticated';
  if (status === 403) return 'unauthorized';
  if (status === 404) return 'not-found';
  if (status === 409) return 'conflict';
  if (status >= 500) return 'server';
  return 'unknown';
}

function messageFromBody(body: ApiErrorBody | string | null): string | undefined {
  if (!body || typeof body === 'string') return undefined;
  if (body.error?.message) return body.error.message;
  if (body.message) return body.message;
  return typeof body.detail === 'string' ? body.detail : undefined;
}

function defaultMessage(status: number): string {
  switch (status) {
    case 400: case 422: return 'Please correct the highlighted request values.';
    case 401: return 'Your session has expired. Please sign in again.';
    case 403: return 'You do not have permission to perform this action.';
    case 404: return 'The requested item was not found.';
    case 409: return 'The request conflicts with the current server state.';
    case 502: case 503: case 504: return 'The gateway or a dependent service is unavailable.';
    default: return status >= 500 ? 'The server could not complete the request.' : 'The request could not be completed.';
  }
}
