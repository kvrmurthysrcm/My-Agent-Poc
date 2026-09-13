import { HttpContextToken } from '@angular/common/http';

/** Avoids attaching/retrying a bearer token on login, refresh, and logout requests. */
export const SKIP_AUTH = new HttpContextToken<boolean>(() => false);
