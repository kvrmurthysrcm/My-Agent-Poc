import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { gatewayUrl } from '../config/app-environment';
import { AdminActionResponse, AdminDeleteResponse, GraphRagSettings, IndexingMode } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class AdminApiService {
  private readonly http = inject(HttpClient);

  deleteResources(resourceIds: string[], force: boolean) {
    return this.http.post<AdminDeleteResponse>(gatewayUrl('/rag/resources/delete'), { resource_ids: resourceIds, force });
  }
  retryResource(resourceId: string) {
    return this.http.post<AdminActionResponse>(gatewayUrl(`/rag/resources/${encodeURIComponent(resourceId)}/retry`), {});
  }
  indexResource(resourceId: string, indexingMode: Exclude<IndexingMode, 'NONE'>) {
    return this.http.post<AdminActionResponse>(gatewayUrl(`/rag/resources/${encodeURIComponent(resourceId)}/index`), { indexing_mode: indexingMode });
  }
  graphSettings() { return this.http.get<GraphRagSettings>(gatewayUrl('/rag/admin/settings/graph-rag')); }
  saveGraphSettings(settings: Pick<GraphRagSettings, 'entity_batch_size' | 'relationship_batch_size'>) {
    return this.http.put<GraphRagSettings>(gatewayUrl('/rag/admin/settings/graph-rag'), settings);
  }
}
