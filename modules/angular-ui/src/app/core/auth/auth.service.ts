import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, finalize, map, of, shareReplay, switchMap, tap, throwError } from 'rxjs';
import { gatewayUrl } from '../config/app-environment';
import { SKIP_AUTH } from '../http/http-context';
import { CurrentUser, LoginRequest, RegistrationOptionsResponse, RegistrationRequest, RegistrationResponse, TokenResponse } from '../models/api.models';
import { TokenStorageService } from './token-storage.service';

// ANGULAR CONCEPT: signal + computed signal for shared session state.
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly storage = inject(TokenStorageService);
  private refreshInFlight$?: Observable<TokenResponse>;

  readonly user = signal<CurrentUser | null>(null);
  readonly restoring = signal(true);
  readonly authenticated = computed(() => this.user() !== null && !!this.storage.accessToken());
  readonly roles = computed(() => this.user()?.roles ?? []);
  readonly displayName = computed(() => this.user()?.preferred_username ?? this.user()?.name ?? this.user()?.sub ?? '');

  accessToken(): string | null { return this.storage.accessToken(); }

  restoreSession(): Observable<void> {
    const token = this.storage.accessToken();
    if (!token) {
      this.restoring.set(false);
      return of(void 0);
    }
    return this.http.get<CurrentUser>(gatewayUrl('/auth/me')).pipe(
      tap((user) => this.user.set(user)),
      map(() => void 0),
      catchError(() => {
        this.clearSession();
        return of(void 0);
      }),
      finalize(() => this.restoring.set(false)),
    );
  }

  authenticate(request: LoginRequest): Observable<CurrentUser> {
    return this.http.post<TokenResponse>(gatewayUrl('/auth/login'), request, { context: skipAuthContext() }).pipe(
      tap((tokens) => this.storage.save(tokens)),
      // The profile is the authoritative source of roles for browser UI decisions.
      switchMap(() => this.http.get<CurrentUser>(gatewayUrl('/auth/me'))),
      tap((user) => this.user.set(user)),
    );
  }

  registrationOptions(): Observable<RegistrationOptionsResponse> {
    return this.http.get<RegistrationOptionsResponse>(gatewayUrl('/auth/register/options'), { context: skipAuthContext() });
  }

  register(request: RegistrationRequest): Observable<RegistrationResponse> {
    return this.http.post<RegistrationResponse>(gatewayUrl('/auth/register'), request, { context: skipAuthContext() });
  }

  refreshAccessToken(): Observable<TokenResponse> {
    const refreshToken = this.storage.refreshToken();
    if (!refreshToken) return throwError(() => new Error('No refresh token is available.'));
    if (this.refreshInFlight$) return this.refreshInFlight$;

    this.refreshInFlight$ = this.http.post<TokenResponse>(
      gatewayUrl('/auth/refresh'),
      { refresh_token: refreshToken },
      { context: skipAuthContext() },
    ).pipe(
      tap((tokens) => this.storage.save(tokens)),
      finalize(() => { this.refreshInFlight$ = undefined; }),
      shareReplay({ bufferSize: 1, refCount: false }),
    );
    return this.refreshInFlight$;
  }

  logout(): Observable<void> {
    const refreshToken = this.storage.refreshToken();
    const request$ = refreshToken
      ? this.http.post<unknown>(gatewayUrl('/auth/logout'), { refresh_token: refreshToken }, { context: skipAuthContext() })
      : of(null);
    return request$.pipe(
      catchError(() => of(null)),
      map(() => void 0),
      finalize(() => this.clearSession()),
    );
  }

  expireSession(): void {
    this.clearSession();
    void this.router.navigate(['/login']);
  }

  hasAnyRole(requiredRoles: readonly string[]): boolean {
    const roleSet = new Set(this.roles());
    return requiredRoles.some((role) => roleSet.has(role));
  }

  clearSession(): void {
    this.storage.clear();
    this.user.set(null);
  }
}

function skipAuthContext(): HttpContext {
  return new HttpContext().set(SKIP_AUTH, true);
}
