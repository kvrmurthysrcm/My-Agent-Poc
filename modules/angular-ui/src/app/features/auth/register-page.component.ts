import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { RegistrationOptionsResponse } from '../../core/models/api.models';
import { toAppHttpError } from '../../core/http/api-error';

@Component({
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <main class="auth-page"><section class="auth-card">
      <p class="eyebrow">New library account</p><h1>Register</h1>
      @if (error(); as message) { <p class="form-error" role="alert">{{ message }}</p> }
      @if (success(); as message) { <p class="form-success" role="status">{{ message }}</p> }
      <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <label>Full name<input formControlName="full_name" autocomplete="name" required /></label>
        <label>Email<input type="email" formControlName="email" autocomplete="email" required /></label>
        <label>Username<input formControlName="username" autocomplete="username" required /></label>
        <label>Password<input type="password" formControlName="password" autocomplete="new-password" required /></label>
        <label>Subscription tier<select formControlName="subscription_tier"><option value="">Select a tier</option>@for (tier of options()?.subscription_tiers ?? []; track tier.tier_code) { <option [value]="tier.tier_code">{{ tier.tier_name }} — {{ tier.description || tier.tier_code }}</option> }</select></label>
        @if (options(); as values) { <p class="hint">Assigned roles: {{ values.assigned_roles.join(', ') || 'automatic' }}</p> }
        <button class="primary wide" type="submit" [disabled]="form.invalid || submitting()">{{ submitting() ? 'Creating account…' : 'Create account' }}</button>
      </form>
      <p class="muted"><a routerLink="/login">Back to sign in</a></p>
    </section></main>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RegisterPageComponent implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  readonly options = signal<RegistrationOptionsResponse | null>(null);
  readonly error = signal<string | null>(null);
  readonly success = signal<string | null>(null);
  readonly submitting = signal(false);
  readonly form = this.fb.group({
    full_name: ['', [Validators.required, Validators.maxLength(200)]],
    email: ['', [Validators.required, Validators.email, Validators.maxLength(320)]],
    username: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(100)]],
    password: ['', [Validators.required, Validators.minLength(8)]],
    subscription_tier: ['', Validators.required],
  });

  ngOnInit(): void {
    this.auth.registrationOptions().subscribe({
      next: (options) => {
        this.options.set(options);
        const firstTier = options.subscription_tiers[0]?.tier_code;
        if (firstTier) this.form.controls.subscription_tier.setValue(firstTier);
      },
      error: (error: unknown) => this.error.set(toAppHttpError(error).message),
    });
  }

  submit(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.submitting.set(true); this.error.set(null);
    this.auth.register(this.form.getRawValue()).pipe(finalize(() => this.submitting.set(false))).subscribe({
      next: () => { this.success.set('Account created. You can now sign in.'); setTimeout(() => void this.router.navigate(['/login']), 750); },
      error: (error: unknown) => this.error.set(toAppHttpError(error).message),
    });
  }
}
