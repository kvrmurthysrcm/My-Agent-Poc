import { HttpInterceptorFn, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { tap } from 'rxjs';
import { isGatewayUrl } from '../config/app-environment';
import { TraceService } from '../observability/trace.service';

// ANGULAR CONCEPT: functional interceptor + dependency injection with inject().
export const correlationInterceptor: HttpInterceptorFn = (request, next) => {
  if (!isGatewayUrl(request.url)) return next(request);

  const trace = inject(TraceService);
  const context = trace.create();
  const tracedRequest = request.clone({
    setHeaders: {
      traceparent: context.traceparent,
      'X-Trace-Id': context.traceId,
      'X-Span-Id': context.spanId,
    },
  });
  return next(tracedRequest).pipe(
    tap((event) => {
      if (event instanceof HttpResponse) trace.record(event.headers, context);
    }),
  );
};
