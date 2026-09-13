import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter, Router, RouterStateSnapshot } from '@angular/router';
import { AuthService } from '../auth/auth.service';
import { authGuard } from './auth.guard';
import { roleGuard } from './role.guard';

describe('route guards', () => {
  let auth: AuthService;
  let router: Router;
  beforeEach(() => { localStorage.clear(); TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient()] }); auth = TestBed.inject(AuthService); router = TestBed.inject(Router); });
  it('redirects an anonymous user to login', () => {
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, { url: '/search' } as RouterStateSnapshot));
    expect(router.serializeUrl(result as ReturnType<Router['createUrlTree']>)).toContain('/login');
  });
  it('allows a matching role and rejects a nonmatching role', () => {
    localStorage.setItem('secure_api_access_token', 'access');
    auth.user.set({ sub: 'u', roles: ['rag_search_user'], issuer: 'issuer' });
    const allowed = TestBed.runInInjectionContext(() => roleGuard({ data: { roles: ['rag_search_user'] } } as never, {} as never));
    const rejected = TestBed.runInInjectionContext(() => roleGuard({ data: { roles: ['rag_admin'] } } as never, {} as never));
    expect(allowed).toBe(true);
    expect(router.serializeUrl(rejected as ReturnType<Router['createUrlTree']>)).toBe('/books');
  });
});
