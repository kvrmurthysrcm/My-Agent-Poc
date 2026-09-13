import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { ThemeService } from '../../core/theme/theme.service';

interface NavigationItem { label: string; route: string; roles?: readonly string[]; }

@Component({
  selector: 'app-shell',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <a class="skip-link" href="#main-content">Skip to main content</a>
    <header class="app-header">
      <a class="brand" routerLink="/books">RAG Agent Library</a>
      <nav aria-label="Primary navigation" class="primary-nav">
        @for (item of visibleNavigation(); track item.route) {
          <a [routerLink]="item.route" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: item.route === '/books' }">{{ item.label }}</a>
        }
      </nav>
      <div class="user-tools">
        @if (auth.user(); as user) {
          <span class="user-name">{{ auth.displayName() }}</span>
          <span class="role-pill" [attr.title]="user.roles.join(', ')">{{ user.roles.length ? user.roles.join(', ') : 'no roles' }}</span>
        }
        <button type="button" class="icon-button" (click)="theme.toggle()" [attr.aria-label]="'Use ' + (theme.theme() === 'dark' ? 'light' : 'dark') + ' theme'">{{ theme.theme() === 'dark' ? '☀' : '◐' }}</button>
        <button type="button" class="secondary" (click)="logout()">Log out</button>
      </div>
    </header>
    <main id="main-content" class="page-container"><router-outlet /></main>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ShellComponent {
  readonly auth = inject(AuthService);
  readonly theme = inject(ThemeService);
  private readonly router = inject(Router);
  private readonly navigation: readonly NavigationItem[] = [
    { label: 'Books', route: '/books' },
    { label: 'Catalog', route: '/catalog' },
    { label: 'Search', route: '/search', roles: ['rag_search_user', 'rag_user', 'rag_admin'] },
    { label: 'Answer', route: '/answer', roles: ['rag_user', 'rag_admin'] },
    { label: 'Compare', route: '/compare', roles: ['rag_user', 'rag_admin'] },
    { label: 'Library Search', route: '/library-search' },
    { label: 'Ingest', route: '/ingest', roles: ['rag_ingest_user', 'rag_admin'] },
    { label: 'Resource Admin', route: '/admin/resources', roles: ['rag_admin', 'system_admin'] },
    { label: 'Library Tools', route: '/admin/library-tools', roles: ['rag_admin', 'system_admin'] },
  ];

  readonly visibleNavigation = computed(() => this.navigation.filter((item) => !item.roles || this.auth.hasAnyRole(item.roles)));

  logout(): void {
    this.auth.logout().subscribe({ complete: () => void this.router.navigate(['/login']) });
  }
}
