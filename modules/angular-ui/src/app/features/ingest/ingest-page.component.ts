import { ChangeDetectionStrategy, Component, OnDestroy, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Subscription, switchMap, timer } from 'rxjs';
import { toAppHttpError } from '../../core/http/api-error';
import { IngestMetadata, JobErrorResponse, JobStatusResponse, JsonObject } from '../../core/models/api.models';
import { IngestApiService } from '../../core/services/ingest-api.service';
import { DiagnosticsPanelComponent } from '../../shared/components/diagnostics-panel.component';
import { JsonViewerComponent } from '../../shared/components/json-viewer.component';
import { StatePanelComponent } from '../../shared/components/state-panel.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';

@Component({
  imports: [ReactiveFormsModule, DiagnosticsPanelComponent, JsonViewerComponent, StatePanelComponent, StatusBadgeComponent],
  template: `
    <section class="page-heading"><div><p class="eyebrow">Authorized ingestion</p><h1>Ingest a document</h1><p>Upload TXT, PDF, DOCX, or EPUB with full metadata and indexing controls.</p></div></section>
    <section class="panel"><form [formGroup]="form" (ngSubmit)="upload()" class="filter-form"><label class="wide">File<input type="file" accept=".txt,.pdf,.docx,.epub,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/epub+zip" (change)="chooseFile($event)" required /></label>@if (file(); as selected) { <p class="hint full">{{ selected.name }} · {{ selected.size }} bytes</p> }<label>Title<input formControlName="title" /></label><label>Author<input formControlName="author" /></label><label>Category<input formControlName="category_name" /></label><label>Genre<input formControlName="genre" /></label><label>Publisher<input formControlName="publisher" /></label><label>Language<input formControlName="language" /></label><label>Business domain<input formControlName="business_domain" /></label><label>Tags<input formControlName="tags" placeholder="comma separated" /></label><label>ISBN<input formControlName="isbn" /></label><label>Page count<input type="number" min="0" formControlName="page_count" /></label><label>Published date<input type="date" formControlName="published_date" /></label><label>Indexing mode<select formControlName="indexing_mode"><option value="NONE">NONE — upload only</option><option value="STANDARD">STANDARD — embeddings</option><option value="GRAPH">GRAPH — Graph RAG</option><option value="BOTH">BOTH — embeddings + Graph RAG</option></select></label><label>Chunking strategy<select formControlName="strategy"><option value="INTELLIGENT_RECURSIVE">Intelligent recursive</option><option value="SEMANTIC_RECURSIVE">Semantic recursive</option></select></label><label>Chunk size (tokens)<input type="number" min="100" formControlName="chunk_size_tokens" /></label><label>Chunk overlap (tokens)<input type="number" min="0" formControlName="chunk_overlap_tokens" /></label><label class="wide">Description<textarea formControlName="description"></textarea></label><label class="wide">Custom metadata JSON<textarea formControlName="custom_metadata" placeholder='{"department":"architecture"}'></textarea></label><div class="button-row full"><button class="primary" type="submit" [disabled]="uploading()">{{ uploading() ? 'Uploading…' : 'Upload and ingest' }}</button></div></form><p class="hint">Embedding provider/model controls are service-level configuration; no ingest request field exists, so this UI does not invent one.</p></section>
    <section class="two-column"><article class="panel"><h2>Metadata preview</h2><app-json-viewer [value]="metadataPreview()" /></article><article class="panel"><h2>Ingestion job</h2>@if (error(); as message) { <app-state-panel kind="error" [message]="message" /> } @if (job(); as current) { <div class="panel-heading"><span>{{ current.job_id }}</span><app-status-badge [value]="current.status" /></div><p>{{ current.progress_message || current.message || 'Waiting for job status.' }}</p><dl class="detail-grid"><dt>Chunks</dt><dd>{{ current.processed_chunks }} / {{ current.total_chunks }}</dd><dt>Embeddings</dt><dd>{{ current.embedded_chunks }}</dd><dt>Graph entities / relationships</dt><dd>{{ current.graph_entities_count }} / {{ current.graph_relationships_count }}</dd><dt>Failure message</dt><dd>{{ current.error_message || '—' }}</dd></dl>@if (jobErrors().length) { <h3>Job errors</h3><app-json-viewer [value]="jobErrors()" /> }<app-diagnostics-panel [data]="current.profiling" /> } @else { <app-state-panel kind="empty" message="Upload a document to start and monitor an ingestion job." /> }</article></section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class IngestPageComponent implements OnDestroy {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly api = inject(IngestApiService);
  private polling?: Subscription;
  readonly file = signal<File | null>(null);
  readonly uploading = signal(false);
  readonly error = signal<string | null>(null);
  readonly job = signal<JobStatusResponse | null>(null);
  readonly jobErrors = signal<JobErrorResponse[]>([]);
  readonly form = this.fb.group({ title: '', description: '', author: '', category_name: '', genre: '', business_domain: '', publisher: '', language: '', tags: '', isbn: '', page_count: 0, published_date: '', indexing_mode: 'NONE', strategy: 'INTELLIGENT_RECURSIVE', chunk_size_tokens: 500, chunk_overlap_tokens: 50, custom_metadata: '{}' });
  readonly metadataPreview = computed(() => this.buildMetadata(false) ?? { validation: 'Provide valid custom metadata JSON.' });

  ngOnDestroy(): void { this.polling?.unsubscribe(); }
  chooseFile(event: Event): void { this.file.set((event.target as HTMLInputElement).files?.item(0) ?? null); }
  upload(): void {
    const file = this.file();
    const metadata = this.buildMetadata(true);
    if (!file) { this.error.set('Choose a document to upload.'); return; }
    if (!metadata) { this.error.set('Custom metadata must be a JSON object.'); return; }
    this.uploading.set(true); this.error.set(null); this.job.set(null); this.jobErrors.set([]);
    this.api.ingest(file, metadata).subscribe({
      next: (accepted) => { this.uploading.set(false); this.poll(accepted.job_id); },
      error: (error: unknown) => { this.uploading.set(false); this.error.set(toAppHttpError(error).message); },
    });
  }
  private poll(jobId: string): void {
    this.polling?.unsubscribe();
    this.polling = timer(0, 3000).pipe(switchMap(() => this.api.job(jobId))).subscribe({
      next: (job) => {
        this.job.set(job);
        if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(job.status)) {
          this.polling?.unsubscribe();
          if (job.status === 'FAILED') this.api.jobErrors(jobId).subscribe({ next: (errors) => this.jobErrors.set(errors), error: (error: unknown) => this.error.set(toAppHttpError(error).message) });
        }
      },
      error: (error: unknown) => { this.polling?.unsubscribe(); this.error.set(toAppHttpError(error).message); },
    });
  }
  private buildMetadata(strict: boolean): IngestMetadata | null {
    const value = this.form.getRawValue();
    const customMetadata = parseJsonObject(value.custom_metadata);
    if (strict && customMetadata === null) return null;
    const file = this.file();
    return {
      title: value.title.trim() || file?.name, description: value.description.trim() || undefined, resource_type: 'DOCUMENT', category_name: value.category_name.trim() || undefined, genre: value.genre.trim() || undefined, business_domain: value.business_domain.trim() || undefined, source_system: 'rag-agent-angular-ui', author: value.author.trim() || undefined, language: value.language.trim() || undefined, publisher: value.publisher.trim() || undefined, published_date: value.published_date || undefined, isbn: value.isbn.trim() || undefined, page_count: value.page_count || undefined, tags: splitTags(value.tags), custom_metadata: customMetadata ?? {}, chunking: { strategy: value.strategy as IngestMetadata['chunking']['strategy'], chunk_size_tokens: value.chunk_size_tokens, chunk_overlap_tokens: value.chunk_overlap_tokens }, indexing_mode: value.indexing_mode as IngestMetadata['indexing_mode'],
    };
  }
}

function splitTags(value: string): string[] { return value.split(',').map((tag) => tag.trim()).filter(Boolean); }
function parseJsonObject(value: string): JsonObject | null {
  try { const parsed: unknown = JSON.parse(value || '{}'); return isJsonObject(parsed) ? parsed : null; } catch { return null; }
}
function isJsonObject(value: unknown): value is JsonObject { return typeof value === 'object' && value !== null && !Array.isArray(value); }
