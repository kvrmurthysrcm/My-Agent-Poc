import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('persists tokens then obtains current-user roles after authentication', () => {
    let userName = '';
    service.authenticate({ username: 'reader', password: 'secret' }).subscribe((user) => userName = user.preferred_username ?? '');
    const login = http.expectOne('/api/auth/login');
    expect(login.request.body).toEqual({ username: 'reader', password: 'secret' });
    login.flush({ access_token: 'access', refresh_token: 'refresh', token_type: 'bearer' });
    const me = http.expectOne('/api/auth/me');
    expect(me.request.headers.get('Authorization')).toBeNull();
    me.flush({ sub: 'u-1', preferred_username: 'reader', roles: ['rag_user'], issuer: 'issuer' });
    expect(userName).toBe('reader');
    expect(service.authenticated()).toBe(true);
    expect(service.hasAnyRole(['rag_user'])).toBe(true);
  });
});
