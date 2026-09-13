import { ApplicationConfig, inject, provideAppInitializer, provideBrowserGlobalErrorListeners, provideZonelessChangeDetection } from '@angular/core';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { AuthService } from './core/auth/auth.service';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { correlationInterceptor } from './core/interceptors/correlation.interceptor';
import { errorInterceptor } from './core/interceptors/error.interceptor';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZonelessChangeDetection(),
    // The order lets auth see native 401 errors before the outer error interceptor normalizes them.
    provideHttpClient(withFetch(), withInterceptors([correlationInterceptor, errorInterceptor, authInterceptor])),
    provideRouter(routes),
    provideAppInitializer(() => firstValueFrom(inject(AuthService).restoreSession())),
  ],
};
