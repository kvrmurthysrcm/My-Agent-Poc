# State Management

## Boundary

```text
Component
  |
  v
Feature facade/page state (signals)
  |             |
  |             +--> computed view models/metrics
  v
Typed API service (Observable)
  |
  v
HttpClient -> Secure Gateway
```

- Local inputs, loading flags, selections, errors, theme, and current user use writable signals.
- Derived lists, counts, navigation, and metadata preview use `computed` signals.
- HTTP one-shots, token refresh coordination, polling, and SSE use RxJS Observables.
- No NgRx is used: the application has no need yet for global reducers, event replay, or a large normalized client cache.

## WHY

Signals are ergonomic for synchronous view state. Observables model time, cancellation, retries, and HTTP streams. Keeping them at this boundary prevents ad hoc subscriptions in templates.

## Example

```ts
readonly resources = signal<AdminResource[]>([]);
readonly visible = computed(() => this.resources().filter(matchesFilter));

this.api.list().subscribe(response => this.resources.set(response.resources));
```

## Interview takeaway

Signals do not replace RxJS. Use signals for state the template reads synchronously; use Observables for async streams and bridge them deliberately at the service/component boundary.
