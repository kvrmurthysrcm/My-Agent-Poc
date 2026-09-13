import { Injectable } from '@angular/core';
import { TokenResponse } from '../models/api.models';

const ACCESS_TOKEN_KEY = 'secure_api_access_token';
const REFRESH_TOKEN_KEY = 'secure_api_refresh_token';

/** Isolates the legacy localStorage decision so it can be replaced by a BFF cookie later. */
@Injectable({ providedIn: 'root' })
export class TokenStorageService {
  accessToken(): string | null { return this.read(ACCESS_TOKEN_KEY); }
  refreshToken(): string | null { return this.read(REFRESH_TOKEN_KEY); }

  save(tokens: TokenResponse): void {
    this.write(ACCESS_TOKEN_KEY, tokens.access_token);
    if (tokens.refresh_token) this.write(REFRESH_TOKEN_KEY, tokens.refresh_token);
  }

  clear(): void {
    this.remove(ACCESS_TOKEN_KEY);
    this.remove(REFRESH_TOKEN_KEY);
  }

  private read(key: string): string | null {
    try { return localStorage.getItem(key); } catch { return null; }
  }
  private write(key: string, value: string): void {
    try { localStorage.setItem(key, value); } catch { /* storage can be unavailable */ }
  }
  private remove(key: string): void {
    try { localStorage.removeItem(key); } catch { /* storage can be unavailable */ }
  }
}
