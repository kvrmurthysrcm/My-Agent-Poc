import { HttpErrorResponse } from '@angular/common/http';
import { toAppHttpError } from './api-error';

describe('toAppHttpError', () => {
  it('classifies gateway validation and authorization errors for user-facing UI', () => {
    expect(toAppHttpError(new HttpErrorResponse({ status: 422, error: { error: { message: 'Invalid metadata' } } })).kind).toBe('validation');
    const forbidden = toAppHttpError(new HttpErrorResponse({ status: 403, error: { error: { message: 'Insufficient role' } } }));
    expect(forbidden.kind).toBe('unauthorized'); expect(forbidden.message).toBe('Insufficient role');
  });
});
