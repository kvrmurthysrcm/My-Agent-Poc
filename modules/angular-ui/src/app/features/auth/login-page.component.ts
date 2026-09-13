import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { toAppHttpError } from '../../core/http/api-error';

@Component({
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <main class="auth-page"><section class="auth-card">
      <p class="eyebrow">Secure API Gateway</p><h1>RAG Agent Library</h1><p>Sign in to search, answer, and manage library resources.</p>
      @if (error(); as message) { <p class="form-error" role="alert">{{ message }}</p> }
      <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <label>Username<input type="text" formControlName="username" autocomplete="username" required /></label>
        @if (form.controls.username.touched && form.controls.username.invalid) { <span class="field-error">Username is required.</span> }
        <label>Password<input type="password" formControlName="password" autocomplete="current-password" required /></label>
        @if (form.controls.password.touched && form.controls.password.invalid) { <span class="field-error">Password is required.</span> }
        <button class="primary wide" type="submit" [disabled]="form.invalid || submitting()">{{ submitting() ? 'Signing in…' : 'Sign in' }}</button>
      </form>
      <p class="muted">Need an account? <a routerLink="/register">Register</a></p>
    </section></main>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginPageComponent {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  readonly submitting = signal(false);
  readonly error = signal<string | null>(null);
  // ANGULAR CONCEPT: strictly typed reactive form.
  readonly form = this.fb.group({ username: ['', Validators.required], password: ['', Validators.required] });

  submit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.submitting.set(true); this.error.set(null);
    this.auth.authenticate(this.form.getRawValue()).pipe(finalize(() => this.submitting.set(false))).subscribe({
      next: () => {
        const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl');
        void this.router.navigateByUrl(returnUrl?.startsWith('/') ? returnUrl : '/books');
      },
      error: (error: unknown) => this.error.set(toAppHttpError(error).message),
    });
  }
}
