import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { toAppHttpError } from '../../core/http/api-error';
import { AdminResource } from '../../core/models/api.models';
import { AdminApiService } from '../../core/services/admin-api.service';
import { ResourceApiService } from '../../core/services/resource-api.service';
import { BytesPipe } from '../../shared/pipes/bytes.pipe';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog.component';
import { DiagnosticsPanelComponent } from '../../shared/components/diagnostics-panel.component';
import { JsonViewerComponent } from '../../shared/components/json-viewer.component';
import { StatePanelComponent } from '../../shared/components/state-panel.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';

@Component({
  imports: [DatePipe, FormsModule, BytesPipe, ConfirmDialogComponent, DiagnosticsPanelComponent, JsonViewerComponent, StatePanelComponent, StatusBadgeComponent],
  template: `
    <section class="page-heading"><div><p class="eyebrow">Resource dashboard</p><h1>Books</h1><p>Monitor ingested resources, chunks, embeddings, and Graph RAG state.</p></div><button type="button" class="secondary" (click)="load()" [disabled]="loading()">{{ loading() ? 'Refreshing…' : 'Refresh books' }}</button></section>
    <section class="metrics" aria-label="Book metrics"><article><strong>{{ metrics().total }}</strong><span>Total</span></article><article><strong>{{ metrics().ready }}</strong><span>Ready</span></article><article><strong>{{ metrics().active }}</strong><span>Queued / processing</span></article><article><strong>{{ metrics().failed }}</strong><span>Failed</span></article></section>
    <section class="panel"><div class="toolbar"><label class="grow">Filter resources<input [ngModel]="filter()" (ngModelChange)="filter.set($event)" type="search" placeholder="Title, author, category, status, tag" /></label>@if (isAdmin()) { <button type="button" class="danger" [disabled]="!selectedIds().size || mutating()" (click)="pendingDelete.set(true)">Delete selected ({{ selectedIds().size }})</button> }</div>
      @if (error(); as message) { <app-state-panel kind="error" [message]="message" /> }
      @if (loading()) { <app-state-panel kind="loading" message="Loading resources…" /> }
      @if (!loading() && !error()) {
        <div class="table-wrap"><table><thead><tr>@if (isAdmin()) { <th><input type="checkbox" [checked]="allVisibleSelected()" (change)="toggleAll($event)" aria-label="Select all visible resources" /></th> }<th>Book</th><th>Status</th><th>Chunks / embeddings</th><th>Latest job</th><th>Created</th>@if (isAdmin()) { <th>Actions</th> }</tr></thead>
          <tbody>@for (item of visibleResources(); track item.resource_id) { <tr [class.selected-row]="selectedResource()?.resource_id === item.resource_id">@if (isAdmin()) { <td><input type="checkbox" [checked]="selectedIds().has(item.resource_id)" (change)="toggleSelected(item.resource_id, $event)" [attr.aria-label]="'Select ' + item.title" /></td> }<td><button type="button" class="link-button" (click)="selectedResource.set(item)">{{ item.title }}</button><small>{{ item.author || 'Unknown author' }} · {{ item.category || 'Uncategorized' }}</small><div class="tag-row">@for (tag of item.tags; track tag) { <span class="tag">{{ tag }}</span> }</div></td><td><app-status-badge [value]="effectiveStatus(item)" /><small>RAG {{ item.rag_enabled ? 'enabled' : 'disabled' }}</small></td><td>{{ item.chunk_count }} / {{ item.embedding_count }}</td><td><small>{{ item.latest_job_id || '—' }}</small><br /><app-status-badge [value]="item.latest_job_status" /><small>{{ progress(item) }}</small></td><td>{{ item.created_at | date:'medium' }}</td>@if (isAdmin()) { <td class="action-cell"><button type="button" class="small" [disabled]="mutating() || !canRetry(item)" (click)="retry(item)">Retry</button><button type="button" class="small" [disabled]="mutating() || active(item)" (click)="index(item, 'STANDARD')">Embeddings</button><button type="button" class="small" [disabled]="mutating() || active(item)" (click)="index(item, 'GRAPH')">Graph index</button></td> }</tr> } @empty { <tr><td [attr.colspan]="isAdmin() ? 7 : 5"><app-state-panel kind="empty" message="No resources match this filter." /></td></tr> }</tbody></table></div>
      }
    </section>
    @if (selectedResource(); as resource) { <section class="panel detail-panel"><div class="panel-heading"><h2>{{ resource.title }}</h2><button type="button" class="secondary small" (click)="selectedResource.set(null)">Close</button></div><dl class="detail-grid"><dt>Resource ID</dt><dd>{{ resource.resource_id }}</dd><dt>File</dt><dd>{{ resource.file_name || '—' }} {{ resource.file_size_bytes | bytes }}</dd><dt>Graph entities / relationships</dt><dd>{{ resource.latest_job_graph_entities_count }} / {{ resource.latest_job_graph_relationships_count }}</dd><dt>Latest error</dt><dd>{{ resource.latest_error_message || '—' }}</dd></dl><app-json-viewer [value]="resource.metadata" /><app-diagnostics-panel [data]="resource" /></section> }
    <app-confirm-dialog [open]="pendingDelete()" title="Delete selected resources" [message]="'Delete ' + selectedIds().size + ' selected resource(s)? This is a destructive action.'" (confirm)="deleteSelected()" (cancel)="pendingDelete.set(false)" />
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BooksPageComponent implements OnInit {
  private readonly resourcesApi = inject(ResourceApiService);
  private readonly adminApi = inject(AdminApiService);
  private readonly auth = inject(AuthService);
  readonly resources = signal<AdminResource[]>([]);
  readonly loading = signal(false);
  readonly mutating = signal(false);
  readonly error = signal<string | null>(null);
  readonly filter = signal('');
  readonly selectedIds = signal<ReadonlySet<string>>(new Set<string>());
  readonly selectedResource = signal<AdminResource | null>(null);
  readonly pendingDelete = signal(false);
  readonly visibleResources = computed(() => {
    const needle = this.filter().trim().toLowerCase();
    return this.resources().filter((resource) => !needle || [resource.title, resource.author, resource.category, resource.ingestion_status, resource.latest_job_status, ...resource.tags].filter(Boolean).join(' ').toLowerCase().includes(needle));
  });
  readonly metrics = computed(() => this.resources().reduce((summary, item) => {
    const status = this.effectiveStatus(item);
    summary.total += 1;
    if (status === 'FAILED') summary.failed += 1;
    else if (status === 'QUEUED' || status === 'PROCESSING') summary.active += 1;
    else summary.ready += 1;
    return summary;
  }, { total: 0, ready: 0, active: 0, failed: 0 }));

  ngOnInit(): void { this.load(); }
  isAdmin(): boolean { return this.auth.hasAnyRole(['rag_admin', 'system_admin']); }
  allVisibleSelected(): boolean { const visible = this.visibleResources(); return visible.length > 0 && visible.every((resource) => this.selectedIds().has(resource.resource_id)); }
  active(item: AdminResource): boolean { return ['QUEUED', 'PROCESSING'].includes(this.effectiveStatus(item)); }
  canRetry(item: AdminResource): boolean { return this.effectiveStatus(item) === 'FAILED'; }
  effectiveStatus(item: AdminResource): string { return item.latest_job_status || item.ingestion_status || 'UNKNOWN'; }
  progress(item: AdminResource): string { return item.latest_job_progress_message || (item.latest_job_total_chunks ? `${item.latest_job_processed_chunks}/${item.latest_job_total_chunks} chunks` : ''); }

  load(): void {
    this.loading.set(true); this.error.set(null);
    this.resourcesApi.list().pipe(finalize(() => this.loading.set(false))).subscribe({
      next: (response) => this.resources.set(response.resources),
      error: (error: unknown) => this.error.set(toAppHttpError(error).message),
    });
  }
  toggleSelected(id: string, event: Event): void { this.selectedIds.update((current) => { const next = new Set(current); (event.target as HTMLInputElement).checked ? next.add(id) : next.delete(id); return next; }); }
  toggleAll(event: Event): void { const checked = (event.target as HTMLInputElement).checked; this.selectedIds.update((current) => { const next = new Set(current); this.visibleResources().forEach((item) => checked ? next.add(item.resource_id) : next.delete(item.resource_id)); return next; }); }
  retry(item: AdminResource): void { this.runMutation(() => this.adminApi.retryResource(item.resource_id)); }
  index(item: AdminResource, mode: 'STANDARD' | 'GRAPH'): void { this.runMutation(() => this.adminApi.indexResource(item.resource_id, mode)); }
  deleteSelected(): void {
    const ids = [...this.selectedIds()];
    if (!ids.length) { this.pendingDelete.set(false); return; }
    this.pendingDelete.set(false);
    this.runMutation(() => this.adminApi.deleteResources(ids, true), () => this.selectedIds.set(new Set<string>()));
  }
  private runMutation(request: () => import('rxjs').Observable<unknown>, onSuccess?: () => void): void {
    this.mutating.set(true); this.error.set(null);
    request().pipe(finalize(() => this.mutating.set(false))).subscribe({ next: () => { onSuccess?.(); this.load(); }, error: (error: unknown) => this.error.set(toAppHttpError(error).message) });
  }
}
