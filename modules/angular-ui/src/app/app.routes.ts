import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { roleGuard } from './core/guards/role.guard';
import { ShellComponent } from './layout/shell/shell.component';

export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./features/auth/login-page.component').then((m) => m.LoginPageComponent) },
  { path: 'register', loadComponent: () => import('./features/auth/register-page.component').then((m) => m.RegisterPageComponent) },
  {
    path: '', component: ShellComponent, canActivate: [authGuard], children: [
      { path: 'books', loadComponent: () => import('./features/books/books-page.component').then((m) => m.BooksPageComponent) },
      { path: 'catalog', loadComponent: () => import('./features/catalog/catalog-page.component').then((m) => m.CatalogPageComponent) },
      { path: 'search', canActivate: [roleGuard], data: { roles: ['rag_search_user', 'rag_user', 'rag_admin'] }, loadComponent: () => import('./features/search/search-page.component').then((m) => m.SearchPageComponent) },
      { path: 'answer', canActivate: [roleGuard], data: { roles: ['rag_user', 'rag_admin'] }, loadComponent: () => import('./features/answer/answer-page.component').then((m) => m.AnswerPageComponent) },
      { path: 'compare', canActivate: [roleGuard], data: { roles: ['rag_user', 'rag_admin'] }, loadComponent: () => import('./features/compare/compare-page.component').then((m) => m.ComparePageComponent) },
      { path: 'library-search', loadComponent: () => import('./features/library-search/library-search-page.component').then((m) => m.LibrarySearchPageComponent) },
      { path: 'ingest', canActivate: [roleGuard], data: { roles: ['rag_ingest_user', 'rag_admin'] }, loadComponent: () => import('./features/ingest/ingest-page.component').then((m) => m.IngestPageComponent) },
      { path: 'admin/resources', canActivate: [roleGuard], data: { roles: ['rag_admin', 'system_admin'] }, loadComponent: () => import('./features/admin/resource-admin-page.component').then((m) => m.ResourceAdminPageComponent) },
      { path: 'admin/library-tools', canActivate: [roleGuard], data: { roles: ['rag_admin', 'system_admin'] }, loadComponent: () => import('./features/library-tools/library-tools-page.component').then((m) => m.LibraryToolsPageComponent) },
      { path: '', pathMatch: 'full', redirectTo: 'books' },
    ],
  },
  { path: '**', redirectTo: 'books' },
];
