# Authentication Prompt

Review or improve the Angular auth implementation. Preserve gateway contracts for login/register/options/refresh/logout/me. Keep legacy local-storage behavior behind `TokenStorageService`, implement single-flight refresh in the functional interceptor, add tests for token URL scoping and expired session behavior, and update security documentation. Do not make client-side role checks a security boundary.
