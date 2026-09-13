import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { AuthService } from '../auth/auth.service';
import { gatewayUrl } from '../config/app-environment';
import { AppHttpError } from '../http/api-error';
import { AnswerComparisonResponse, AnswerRequest, AnswerResponse, CompareStreamEvent } from '../models/api.models';
import { TraceService } from '../observability/trace.service';

@Injectable({ providedIn: 'root' })
export class AnswerApiService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly trace = inject(TraceService);

  answer(request: AnswerRequest) { return this.http.post<AnswerResponse>(gatewayUrl('/rag/answer'), request); }
  compare(request: AnswerRequest) { return this.http.post<AnswerComparisonResponse>(gatewayUrl('/rag/answer/compare'), request); }

  // ANGULAR CONCEPT: Observable wraps a fetch ReadableStream because EventSource cannot POST a bearer token.
  streamCompare(request: AnswerRequest): Observable<CompareStreamEvent> {
    return new Observable<CompareStreamEvent>((subscriber) => {
      const controller = new AbortController();
      const trace = this.trace.create();
      const token = this.auth.accessToken();
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        traceparent: trace.traceparent,
        'X-Trace-Id': trace.traceId,
        'X-Span-Id': trace.spanId,
      };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      void fetch(gatewayUrl('/rag/answer/compare/stream'), {
        method: 'POST', headers, body: JSON.stringify(request), signal: controller.signal,
      }).then(async (response) => {
        this.trace.record(response.headers, trace);
        if (!response.ok) throw await streamError(response);
        if (!response.body) throw { status: 0, kind: 'network', message: 'The browser did not expose a streaming response body.' } satisfies AppHttpError;

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let pending = '';
        try {
          while (!subscriber.closed) {
            const chunk = await reader.read();
            if (chunk.done) break;
            pending += decoder.decode(chunk.value, { stream: true });
            const frames = pending.split(/\r?\n\r?\n/);
            pending = frames.pop() ?? '';
            frames.forEach((frame) => emitFrame(frame, subscriber));
          }
          if (pending.trim()) emitFrame(pending, subscriber);
          if (!subscriber.closed) subscriber.complete();
        } finally {
          reader.releaseLock();
        }
      }).catch((error: unknown) => {
        if (!subscriber.closed && !(error instanceof DOMException && error.name === 'AbortError')) subscriber.error(error);
      });
      return () => controller.abort();
    });
  }
}

function emitFrame(frame: string, subscriber: { next(value: CompareStreamEvent): void; error(error: unknown): void }): void {
  const data = frame.split(/\r?\n/).filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trimStart()).join('\n');
  if (!data) return;
  try {
    const parsed: unknown = JSON.parse(data);
    if (isCompareEvent(parsed)) subscriber.next(parsed);
    else subscriber.error({ status: 0, kind: 'unknown', message: 'The server emitted an invalid comparison event.', diagnostics: data } satisfies AppHttpError);
  } catch {
    subscriber.error({ status: 0, kind: 'unknown', message: 'The server emitted malformed SSE JSON.', diagnostics: data } satisfies AppHttpError);
  }
}

function isCompareEvent(value: unknown): value is CompareStreamEvent {
  return typeof value === 'object' && value !== null && 'event' in value && typeof (value as { event?: unknown }).event === 'string';
}

async function streamError(response: Response): Promise<AppHttpError> {
  const detail = await response.text();
  const kind = response.status === 401 ? 'unauthenticated' : response.status === 403 ? 'unauthorized' : response.status >= 500 ? 'server' : 'unknown';
  return { status: response.status, kind, message: `Comparison stream request failed (${response.status}).`, diagnostics: detail };
}
