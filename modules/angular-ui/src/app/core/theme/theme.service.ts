import { Injectable, effect, signal } from '@angular/core';

export type Theme = 'light' | 'dark';
const THEME_KEY = 'secure_api_theme';

// ANGULAR CONCEPT: effect persists a UI-only signal side effect.
@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly theme = signal<Theme>(this.readInitialTheme());

  constructor() {
    effect(() => {
      const theme = this.theme();
      document.documentElement.dataset['theme'] = theme;
      try { localStorage.setItem(THEME_KEY, theme); } catch { /* unavailable storage */ }
    });
  }

  toggle(): void { this.theme.update((value) => value === 'dark' ? 'light' : 'dark'); }

  private readInitialTheme(): Theme {
    try { return localStorage.getItem(THEME_KEY) === 'dark' ? 'dark' : 'light'; } catch { return 'light'; }
  }
}
