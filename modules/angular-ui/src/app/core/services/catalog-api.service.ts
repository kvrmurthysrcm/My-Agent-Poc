import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { gatewayUrl } from '../config/app-environment';
import { CatalogFacetsResponse, CatalogQuery, CatalogResourceDetailResponse, CatalogResourceListResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class CatalogApiService {
  private readonly http = inject(HttpClient);
  facets() { return this.http.get<CatalogFacetsResponse>(gatewayUrl('/library/catalog/facets')); }
  search(query: CatalogQuery) {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') params = params.set(key, String(value));
    }
    return this.http.get<CatalogResourceListResponse>(gatewayUrl('/library/catalog/resources'), { params });
  }
  detail(resourceId: string) { return this.http.get<CatalogResourceDetailResponse>(gatewayUrl(`/library/catalog/resources/${encodeURIComponent(resourceId)}`)); }
}
