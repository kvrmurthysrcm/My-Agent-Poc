import { Injectable, signal } from '@angular/core';

export interface TraceContext { traceId: string; spanId: string; traceparent: string; requestId?: string; }

@Injectable({ providedIn: 'root' })
export class TraceService {
  readonly latest = signal<TraceContext | null>(null);

  create(): TraceContext {
    const traceId = hex(32);
    const spanId = hex(16);
    return { traceId, spanId, traceparent: `00-${traceId}-${spanId}-01` };
  }

  record(responseHeaders: Headers | { get(name: string): string | null }, fallback: TraceContext): void {
    this.latest.set({
      traceId: responseHeaders.get('X-Trace-Id') ?? fallback.traceId,
      spanId: responseHeaders.get('X-Span-Id') ?? fallback.spanId,
      traceparent: responseHeaders.get('traceparent') ?? fallback.traceparent,
      requestId: responseHeaders.get('X-Request-ID') ?? undefined,
    });
  }
}

function hex(length: number): string {
  return globalThis.crypto.randomUUID().replaceAll('-', '').slice(0, length);
}
