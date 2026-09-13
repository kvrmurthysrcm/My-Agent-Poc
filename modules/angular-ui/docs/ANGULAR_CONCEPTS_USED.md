# Angular Concepts Used

Each implementation file labels important examples with `ANGULAR CONCEPT` comments. This guide is a map from concept to the working POC.

| Concept | What / why | Where used | Small example | Interview question / concise answer |
| --- | --- | --- | --- | --- |
| Architecture | Feature/core/shared separation keeps responsibilities local. | `src/app/core`, `shared`, `features` | `feature -> API service -> HttpClient` | How would you structure an enterprise SPA? Separate cross-cutting core, reusable shared UI, and lazy feature slices. |
| Components | Classes plus templates render reusable UI. | All pages/components | `@Component({ standalone: true })` | What is a component? A view unit with behavior, template, providers, and lifecycle. |
| Standalone | Components import their own dependencies; fewer NgModules. | Every component | `imports: [ReactiveFormsModule]` | Why standalone? Explicit dependencies and simpler lazy loading. |
| Templates | Declarative DOM from component state. | Inline templates | `{{ answer.answer }}` | Why avoid DOM mutation? Templates stay safe, testable, and synchronized with state. |
| Property binding | Pushes component values to elements. | Forms/buttons | `[disabled]="loading()"` | Difference from interpolation? Property binding writes a DOM/component property. |
| Event binding | Receives user/browser events. | All forms | `(ngSubmit)="search()"` | Why use it? It keeps event handling in component code. |
| Two-way binding | Combines input/event binding; use sparingly. | Admin filters | `[ngModel]="filter()" (ngModelChange)="filter.set($event)"` | When not use it? Avoid it for complex domain forms; use reactive forms. |
| Signals | Synchronous reactive state primitives. | Auth, books, pages | `readonly loading = signal(false)` | What benefit? Fine-grained state without manual subscriptions. |
| Computed | Derives state from other signals. | Books metrics/navigation | `computed(() => resources().filter(...))` | Why not store derived values? Avoid stale duplicate state. |
| Effect | Performs side effects when signals change. | Theme service | `effect(() => localStorage.setItem(...))` | When use it? For non-state side effects, not derived data. |
| RxJS Observable | Models async values over time. | API service return types | `http.get<T>(url)` | Signals vs Observables? Signals hold current state; Observables model time/streams. |
| Subject/BehaviorSubject | Multicast event/current-value primitives. | Not needed in this POC; refresh uses shared Observable. | `shareReplay(1)` | When use BehaviorSubject? When an Observable API needs an immediately available current value. |
| Dependency injection | Provides collaborators without manual construction. | Services/components | `private api = inject(SearchApiService)` | Why DI? Testability, substitution, lifecycle, and configuration. |
| Providers | Register services/config at injector scope. | `app.config.ts` | `provideHttpClient(...)` | Root vs component provider? Root is singleton; component creates a local instance. |
| `inject()` | Functional/field injection API. | Services/interceptors/guards | `const auth = inject(AuthService)` | Why use it? Enables functional APIs and concise constructor-free injection. |
| HttpClient | Typed, cancellable HTTP Observable client. | Dedicated API services | `http.post<AnswerResponse>(...)` | Why not fetch everywhere? Interceptors, testing, type consistency, and shared policy. |
| Interceptors | Cross-cutting request/response middleware. | `core/interceptors` | `withInterceptors([...])` | How do interceptors work? They compose around HttpClient requests and can clone/retry/transform. |
| Routing | Maps URLs to components. | `app.routes.ts` | `{ path: 'search', loadComponent: ... }` | Why routing? Deep links, browser history, authorization, lazy chunks. |
| Lazy loading | Defers feature code until route use. | All feature routes | `loadComponent: () => import(...)` | Performance benefit? Lower initial JS; it does not secure an endpoint. |
| Guards | Decide whether route navigation proceeds. | `auth.guard.ts`, `role.guard.ts` | `return router.createUrlTree(...)` | Guard vs backend auth? Guard is UX/navigation; backend enforces security. |
| Reactive forms | Programmatic typed form model/validation. | Login, ingest, answer, catalog | `fb.group({ query: ['', Validators.required] })` | Why reactive forms? Predictable validation and testable state. |
| Validation | Client feedback before a request; server remains authoritative. | Forms/pages | `Validators.min(1)` | Why validate on server too? Client validation is mutable/bypassable. |
| Pipes | Presentation transforms. | `BytesPipe`, built-in date/number | `{{ size | bytes }}` | Why pipes? Reusable display formatting without mutating data. |
| Directives | Template behavior extensions. | Built-in `formControlName`, router directives | `[formGroup]="form"` | Component vs directive? A component has a view; a directive augments an existing element. |
| Lifecycle | Hooks manage setup/teardown. | Ingest/admin/compare | `ngOnDestroy() { subscription.unsubscribe() }` | How prevent leaks? AsyncPipe/`takeUntilDestroyed`/unsubscribe/AbortController. |
| OnPush | Optimizes checks around input/signal/event boundaries. | All components | `changeDetection: ChangeDetectionStrategy.OnPush` | Why it helps? Reduces unnecessary view checking and encourages immutable updates. |
| Control flow | Modern template syntax for conditions/loops. | All templates | `@if`, `@for`, `@empty` | Why prefer it? Clearer compiled control flow and type narrowing. |
| Environment/config | Browser-safe endpoint configuration only. | `app-environment.ts`, proxy | `apiBaseUrl: '/api'` | What must not be there? Secrets/internal API keys. |
| Authentication | Establishes identity/session. | AuthService | `POST /auth/login` | Token storage choice? POC uses local storage; production should prefer BFF cookies. |
| Authorization | Determines permission to perform an action. | role guard/gateway | `hasAnyRole(['rag_admin'])` | Why backend enforcement? Any browser check can be bypassed. |
| CORS | Browser cross-origin policy. | proxy/runbook | `/api` proxy in dev | Does proxy solve production CORS? No; gateway origin policy must be configured. |
| Unit/component/HTTP testing | Verifies logic/view/contracts in isolation. | `*.spec.ts` | `HttpTestingController` | Why mock HTTP? Deterministic endpoint/DTO/error tests. |
| Accessibility | Keyboard/screen-reader usable semantic UI. | shell/forms/dialog | skip link, labels, live errors | What basics matter? Labels, focus, semantic buttons, contrast, error announcement. |
| Performance | Minimize startup/render/network work. | lazy routes, OnPush, signals | lazy feature chunks | First optimization? Measure, then split routes/cache/track lists. |

## Representative code

```ts
// signal + computed
readonly resources = signal<AdminResource[]>([]);
readonly readyCount = computed(() => this.resources().filter(isReady).length);

// functional interceptor
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  return next(request.clone({ setHeaders: { Authorization: `Bearer ${auth.accessToken()}` } }));
};

// typed reactive form
readonly form = this.fb.group({ query: ['', Validators.required], top_k: 5 });

// lazy route
{ path: 'search', loadComponent: () => import('./features/search/search-page.component').then(m => m.SearchPageComponent) }
```

## How to study this repository

1. Start at `app.config.ts` and `app.routes.ts`.
2. Follow one workflow from a page into its typed API service.
3. Inspect the related interceptor/guard and its test.
4. Compare it to the corresponding gateway route and Pydantic schema.

## Architect takeaway

Angular concepts are useful when they make an operational boundary explicit: components own views, services own transport, signals own state, Observables own time, and the gateway owns authorization/security.
