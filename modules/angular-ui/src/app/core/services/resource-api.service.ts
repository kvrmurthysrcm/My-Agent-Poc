import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { gatewayUrl } from '../config/app-environment';
import { AdminResourceListResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class ResourceApiService {
  private readonly http = inject(HttpClient);
  list() { return this.http.get<AdminResourceListResponse>(gatewayUrl('/rag/resources')); }
}
