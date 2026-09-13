import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { AuthService } from '../auth/auth.service';

// ANGULAR CONCEPT: route-level authorization. The backend remains the security boundary.
export const roleGuard: CanActivateFn = (route) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const roles = route.data['roles'];
  const requiredRoles = Array.isArray(roles) ? roles.filter((role): role is string => typeof role === 'string') : [];
  return auth.hasAnyRole(requiredRoles) ? true : router.createUrlTree(['/books']);
};
