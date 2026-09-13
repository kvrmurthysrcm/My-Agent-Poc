import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from '../auth/auth.service';
import { isGatewayUrl } from '../config/app-environment';
import { SKIP_AUTH } from '../http/http-context';

// ANGULAR CONCEPT: functional interceptor. It never sends a bearer token to a non-gateway URL.
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const shouldSkip = request.context.get(SKIP_AUTH) || !isGatewayUrl(request.url);
  if (shouldSkip) return next(request);

  const withToken = (token: string) => request.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
  const initialToken = auth.accessToken();
  const authenticatedRequest = initialToken ? withToken(initialToken) : request;

  return next(authenticatedRequest).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse) || error.status !== 401 || request.url.includes('/auth/')) {
        return throwError(() => error);
      }
      // AuthService shares this refresh Observable to prevent concurrent refresh storms.
      return auth.refreshAccessToken().pipe(
        switchMap(() => {
          const refreshedToken = auth.accessToken();
          return refreshedToken ? next(withToken(refreshedToken)) : throwError(() => new Error('Refresh completed without an access token.'));
        }),
        catchError((refreshError: unknown) => {
          auth.expireSession();
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
