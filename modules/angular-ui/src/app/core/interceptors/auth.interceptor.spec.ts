import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  let client: HttpClient;
  let http: HttpTestingController;
  beforeEach(() => {
    localStorage.clear(); localStorage.setItem('secure_api_access_token', 'stored-token');
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(withInterceptors([authInterceptor])), provideHttpClientTesting()] });
    client = TestBed.inject(HttpClient); http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('adds bearer tokens only to gateway-relative API calls', () => {
    client.get('/api/rag/search').subscribe();
    const gateway = http.expectOne('/api/rag/search');
    expect(gateway.request.headers.get('Authorization')).toBe('Bearer stored-token'); gateway.flush({});
    client.get('https://example.test/public').subscribe();
    const external = http.expectOne('https://example.test/public');
    expect(external.request.headers.has('Authorization')).toBe(false); external.flush({});
  });
});
