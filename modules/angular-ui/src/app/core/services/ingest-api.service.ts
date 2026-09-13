import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { gatewayUrl } from '../config/app-environment';
import { IngestAcceptedResponse, IngestMetadata, JobErrorResponse, JobStatusResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class IngestApiService {
  private readonly http = inject(HttpClient);

  ingest(file: File, metadata: IngestMetadata) {
    const form = new FormData();
    form.append('file', file, file.name);
    form.append('metadata', JSON.stringify(metadata));
    // Deliberately do not set Content-Type: the browser supplies the multipart boundary.
    return this.http.post<IngestAcceptedResponse>(gatewayUrl('/rag/ingest'), form);
  }
  job(jobId: string) { return this.http.get<JobStatusResponse>(gatewayUrl(`/rag/ingest/jobs/${encodeURIComponent(jobId)}`)); }
  jobErrors(jobId: string) { return this.http.get<JobErrorResponse[]>(gatewayUrl(`/rag/ingest/jobs/${encodeURIComponent(jobId)}/errors`)); }
}
