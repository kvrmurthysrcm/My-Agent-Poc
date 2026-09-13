import { HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { toAppHttpError } from '../http/api-error';

// ANGULAR CONCEPT: centralized cross-cutting HTTP error handling.
export const errorInterceptor: HttpInterceptorFn = (request, next) => next(request).pipe(
  catchError((error: unknown) => throwError(() => toAppHttpError(error))),
);
