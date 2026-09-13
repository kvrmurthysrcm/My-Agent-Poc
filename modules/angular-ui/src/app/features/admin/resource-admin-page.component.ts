import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { Subscription, finalize, timer } from 'rxjs';
import { toAppHttpError } from '../../core/http/api-error';
import { AdminResource } from '../../core/models/api.models';
import { AdminApiService } from '../../core/services/admin-api.service';
import { ResourceApiService } from '../../core/services/resource-api.service';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog.component';
import { StatePanelComponent } from '../../shared/components/state-panel.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';

@Component({
  imports: [FormsModule, ReactiveFormsModule, ConfirmDialogComponent, StatePanelComponent, StatusBadgeComponent],
  template: `
    <section class="page-heading"><div><p class="eyebrow">Administrator</p><h1>Resource administration</h1><p>Filter, delete, retry, reindex, and tune Graph RAG runtime settings.</p></div><button type="button" class="secondary" (click)="loadResources()">Refresh</button></section>
    <section class="panel"><h2>Graph RAG runtime settings</h2><form [formGroup]="settingsForm" (ngSubmit)="saveSettings()" class="inline-form"><label>Entity batch<input type="number" min="1" max="10" formControlName="entity_batch_size" /></label><label>Relationship batch<input type="number" min="1" max="10" formControlName="relationship_batch_size" /></label><button class="secondary" type="submit" [disabled]="settingsForm.invalid || savingSettings()">{{ savingSettings() ? 'Saving…' : 'Save settings' }}</button></form><p class="hint">These settings affect new Graph RAG jobs without exposing an internal service endpoint to the browser.</p></section>
    <section class="panel"><div class="toolbar"><label class="grow">Filter<input [ngModel]="filter()" (ngModelChange)="filter.set($event)" type="search" placeholder="Title, author, category, tag, status" /></label><label><input [ngModel]="forceDelete()" (ngModelChange)="forceDelete.set($event)" type="checkbox" /> Force processing deletes</label><button type="button" class="danger" [disabled]="!selectedIds().size || busy()" (click)="confirmingDelete.set(true)">Delete selected</button></div>@if (error(); as message) { <app-state-panel kind="error" [message]="message" /> } @if (loading()) { <app-state-panel kind="loading" message="Loading resources…" /> } @else { <div class="table-wrap"><table><thead><tr><th><input type="checkbox" [checked]="allSelected()" (change)="toggleAll($event)" aria-label="Select all filtered resources" /></th><th>Book</th><th>Status</th><th>Progress</th><th>Chunks / embeddings</th><th>Actions</th></tr></thead><tbody>@for (item of visible(); track item.resource_id) { <tr><td><input type="checkbox" [checked]="selectedIds().has(item.resource_id)" (change)="toggle(item.resource_id, $event)" /></td><td><strong>{{ item.title }}</strong><small>{{ item.resource_id }} · {{ item.author || 'Unknown author' }}</small></td><td><app-status-badge [value]="status(item)" /><small>{{ item.latest_error_message || '' }}</small></td><td>{{ item.latest_job_progress_message || '—' }}</td><td>{{ item.chunk_count }} / {{ item.embedding_count }}</td><td class="action-cell"><button class="small" type="button" [disabled]="busy() || status(item) !== 'FAILED'" (click)="retry(item)">Retry</button><button class="small" type="button" [disabled]="busy() || active(item)" (click)="index(item, 'STANDARD')">Embeddings</button><button class="small" type="button" [disabled]="busy() || active(item)" (click)="index(item, 'GRAPH')">Graph</button><button class="small" type="button" [disabled]="busy() || active(item)" (click)="index(item, 'BOTH')">Both</button></td></tr> } @empty { <tr><td colspan="6">No resources match the current filter.</td></tr> }</tbody></table></div> }</section>
    <app-confirm-dialog [open]="confirmingDelete()" title="Delete resources" [message]="'Delete ' + selectedIds().size + ' selected resource(s)? This cannot be undone.'" (confirm)="deleteResources()" (cancel)="confirmingDelete.set(false)" />
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ResourceAdminPageComponent implements OnInit, OnDestroy {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly resourcesApi = inject(ResourceApiService);
  private readonly adminApi = inject(AdminApiService);
  private refreshSubscription?: Subscription;
  readonly resources = signal<AdminResource[]>([]);
  readonly filter = signal('');
  readonly selectedIds = signal<ReadonlySet<string>>(new Set<string>());
  readonly forceDelete = signal(false);
  readonly loading = signal(false);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  readonly savingSettings = signal(false);
  readonly confirmingDelete = signal(false);
  readonly settingsForm = this.fb.group({ entity_batch_size: [1, [Validators.required, Validators.min(1), Validators.max(10)]], relationship_batch_size: [1, [Validators.required, Validators.min(1), Validators.max(10)]] });
  readonly visible = computed(() => { const needle = this.filter().trim().toLowerCase(); return this.resources().filter((resource) => !needle || [resource.title, resource.author, resource.category, resource.ingestion_status, resource.latest_job_status, ...resource.tags].filter(Boolean).join(' ').toLowerCase().includes(needle)); });

  ngOnInit(): void { this.loadResources(); this.loadSettings(); this.refreshSubscription = timer(5000, 5000).subscribe(() => { if (this.resources().some((resource) => this.active(resource))) this.loadResources(); }); }
  ngOnDestroy(): void { this.refreshSubscription?.unsubscribe(); }
  status(item: AdminResource): string { return item.latest_job_status || item.ingestion_status || 'UNKNOWN'; }
  active(item: AdminResource): boolean { return ['QUEUED', 'PROCESSING'].includes(this.status(item)); }
  allSelected(): boolean { return this.visible().length > 0 && this.visible().every((resource) => this.selectedIds().has(resource.resource_id)); }
  loadResources(): void { this.loading.set(true); this.resourcesApi.list().pipe(finalize(() => this.loading.set(false))).subscribe({ next: (response) => this.resources.set(response.resources), error: (error: unknown) => this.error.set(toAppHttpError(error).message) }); }
  loadSettings(): void { this.adminApi.graphSettings().subscribe({ next: (settings) => this.settingsForm.setValue({ entity_batch_size: settings.entity_batch_size, relationship_batch_size: settings.relationship_batch_size }), error: (error: unknown) => this.error.set(toAppHttpError(error).message) }); }
  saveSettings(): void { if (this.settingsForm.invalid) return; this.savingSettings.set(true); this.adminApi.saveGraphSettings(this.settingsForm.getRawValue()).pipe(finalize(() => this.savingSettings.set(false))).subscribe({ next: (settings) => this.settingsForm.setValue({ entity_batch_size: settings.entity_batch_size, relationship_batch_size: settings.relationship_batch_size }), error: (error: unknown) => this.error.set(toAppHttpError(error).message) }); }
  toggle(id: string, event: Event): void { this.selectedIds.update((current) => { const next = new Set(current); (event.target as HTMLInputElement).checked ? next.add(id) : next.delete(id); return next; }); }
  toggleAll(event: Event): void { const checked = (event.target as HTMLInputElement).checked; this.selectedIds.update((current) => { const next = new Set(current); this.visible().forEach((resource) => checked ? next.add(resource.resource_id) : next.delete(resource.resource_id)); return next; }); }
  retry(item: AdminResource): void { this.mutate(() => this.adminApi.retryResource(item.resource_id)); }
  index(item: AdminResource, mode: 'STANDARD' | 'GRAPH' | 'BOTH'): void { this.mutate(() => this.adminApi.indexResource(item.resource_id, mode)); }
  deleteResources(): void { const ids = [...this.selectedIds()]; this.confirmingDelete.set(false); if (ids.length) this.mutate(() => this.adminApi.deleteResources(ids, this.forceDelete()), () => this.selectedIds.set(new Set<string>())); }
  private mutate(request: () => import('rxjs').Observable<unknown>, onSuccess?: () => void): void { this.busy.set(true); this.error.set(null); request().pipe(finalize(() => this.busy.set(false))).subscribe({ next: () => { onSuccess?.(); this.loadResources(); }, error: (error: unknown) => this.error.set(toAppHttpError(error).message) }); }
}
