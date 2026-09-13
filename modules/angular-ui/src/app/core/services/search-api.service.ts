import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { gatewayUrl } from '../config/app-environment';
import { CombinedSearchResponse, GraphSearchRequest, GraphSearchResponse, SearchRequest, SearchResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class SearchApiService {
  private readonly http = inject(HttpClient);
  search(request: SearchRequest) { return this.http.post<SearchResponse>(gatewayUrl('/rag/search'), request); }
  graphSearch(request: GraphSearchRequest) { return this.http.post<GraphSearchResponse>(gatewayUrl('/rag/graph/search'), request); }
  combinedSearch(request: SearchRequest) { return this.http.post<CombinedSearchResponse>(gatewayUrl('/rag/search/combined'), request); }
  debugSearch(request: SearchRequest) { return this.http.post<SearchResponse>(gatewayUrl('/rag/search/debug'), request); }
}
