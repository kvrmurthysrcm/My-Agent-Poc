import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { gatewayUrl } from '../config/app-environment';
import { JsonObject, ToolCallRequest, ToolListResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class LibraryToolsApiService {
  private readonly http = inject(HttpClient);
  tools() { return this.http.get<ToolListResponse>(gatewayUrl('/library-tools/tools')); }
  call(request: ToolCallRequest) { return this.http.post<JsonObject>(gatewayUrl('/library-tools/call'), request); }
}
