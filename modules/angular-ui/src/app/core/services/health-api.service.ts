import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { gatewayUrl } from '../config/app-environment';
import { JsonObject } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class HealthApiService {
  private readonly http = inject(HttpClient);
  downstream() { return this.http.get<JsonObject>(gatewayUrl('/rag/test-downstream')); }
  gateway() { return this.http.get<JsonObject>(gatewayUrl('/health')); }
}
