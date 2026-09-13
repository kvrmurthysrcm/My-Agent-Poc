import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { gatewayUrl } from '../config/app-environment';
import { LibraryAskRequest, LibraryAskResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class LibraryAgentApiService {
  private readonly http = inject(HttpClient);
  ask(request: LibraryAskRequest) { return this.http.post<LibraryAskResponse>(gatewayUrl('/library-search/ask'), request); }
}
