import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { finalize } from 'rxjs';
import { toAppHttpError } from '../../core/http/api-error';
import { CatalogFacets, CatalogResource, CatalogResourceListResponse } from '../../core/models/api.models';
import { CatalogApiService } from '../../core/services/catalog-api.service';
import { DiagnosticsPanelComponent } from '../../shared/components/diagnostics-panel.component';
import { StatePanelComponent } from '../../shared/components/state-panel.component';

@Component({
  imports: [ReactiveFormsModule, DiagnosticsPanelComponent, StatePanelComponent],
  template: `
    <section class="page-heading"><div><p class="eyebrow">Structured Online Library</p><h1>Catalog</h1><p>Search resource metadata without querying document chunks.</p></div></section>
    <section class="panel"><form [formGroup]="form" (ngSubmit)="search(true)" class="filter-form"><label class="wide">Search<input formControlName="q" placeholder="Title, author, tag, category, publisher, ISBN" /></label><label>Author<input formControlName="author" list="authors" /></label><label>Genre<input formControlName="genre" list="genres" /></label><label>Category<input formControlName="category" list="categories" /></label><label>Tag<input formControlName="tag" list="tags" /></label><label>Publisher<input formControlName="publisher" list="publishers" /></label><label>Language<input formControlName="language" list="languages" /></label><label>Tier<select formControlName="tier"><option value="">Any tier</option>@for (tier of facets().subscription_tiers ?? []; track tier.tier_code) { <option [value]="tier.tier_code">{{ tier.tier_name }}</option> }</select></label><label>Status<select formControlName="status"><option value="">Any</option><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></select></label><label>Published from<input type="date" formControlName="published_from" /></label><label>Published to<input type="date" formControlName="published_to" /></label><label>Sort<select formControlName="sort"><option value="title">Title</option><option value="created_desc">Newest added</option><option value="published_desc">Newest published</option><option value="published_asc">Oldest published</option></select></label><label>Page size<input type="number" min="1" max="100" formControlName="limit" /></label><div class="button-row full"><button class="primary" type="submit" [disabled]="loading()">Search catalog</button><button type="button" class="secondary" (click)="reset()">Reset</button></div></form>
      <datalist id="authors">@for (value of facets().authors ?? []; track value) { <option [value]="value"></option> }</datalist><datalist id="genres">@for (value of facets().genres ?? []; track value) { <option [value]="value"></option> }</datalist><datalist id="categories">@for (value of facets().categories ?? []; track value) { <option [value]="value"></option> }</datalist><datalist id="tags">@for (value of facets().tags ?? []; track value) { <option [value]="value"></option> }</datalist><datalist id="publishers">@for (value of facets().publishers ?? []; track value) { <option [value]="value"></option> }</datalist><datalist id="languages">@for (value of facets().languages ?? []; track value) { <option [value]="value"></option> }</datalist>
    </section>
    @if (error(); as message) { <app-state-panel kind="error" [message]="message" /> }
    @if (loading()) { <app-state-panel kind="loading" message="Searching catalog…" /> }
    @if (response(); as result) { <section class="two-column"><article class="panel"><div class="panel-heading"><h2>Resources</h2><span>{{ result.count }} of {{ result.total }}</span></div><div class="table-wrap"><table><thead><tr><th>Title</th><th>Authors</th><th>Genre / category</th><th>Tags</th><th>Tier</th></tr></thead><tbody>@for (item of result.resources; track item.resource_id) { <tr><td><button class="link-button" type="button" (click)="select(item.resource_id)">{{ item.title }}</button><small>{{ item.publisher || '' }}</small></td><td>{{ item.authors.join(', ') }}</td><td>{{ item.genre || item.category || '—' }}</td><td><div class="tag-row">@for (tag of item.tags.slice(0, 3); track tag) { <span class="tag">{{ tag }}</span> }</div></td><td>{{ item.minimum_tier_code || '—' }}</td></tr> } @empty { <tr><td colspan="5">No catalog resources matched these filters.</td></tr> }</tbody></table></div><div class="pagination"><button type="button" class="secondary" [disabled]="offset() === 0 || loading()" (click)="page(-1)">Previous</button><span>Offset {{ offset() }}</span><button type="button" class="secondary" [disabled]="offset() + result.limit >= result.total || loading()" (click)="page(1)">Next</button></div></article>
      <article class="panel"><h2>Resource detail</h2>@if (selected(); as item) { <h3>{{ item.title }}</h3><p>{{ item.description || 'No description is available.' }}</p><dl class="detail-grid"><dt>Authors</dt><dd>{{ item.authors.join(', ') || '—' }}</dd><dt>Tags</dt><dd>{{ item.tags.join(', ') || '—' }}</dd><dt>Publisher</dt><dd>{{ item.publisher || '—' }}</dd><dt>Language</dt><dd>{{ item.language || '—' }}</dd><dt>Publication</dt><dd>{{ item.published_date || '—' }}</dd><dt>ISBN / pages</dt><dd>{{ item.isbn || '—' }} / {{ item.page_count || '—' }}</dd></dl><app-diagnostics-panel [data]="item" /> } @else { <app-state-panel kind="empty" message="Select a resource to see its full metadata." /> }</article></section> }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogPageComponent implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly api = inject(CatalogApiService);
  readonly facets = signal<CatalogFacets>({});
  readonly response = signal<CatalogResourceListResponse | null>(null);
  readonly selected = signal<CatalogResource | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly offset = signal(0);
  readonly form = this.fb.group({ q: '', author: '', category: '', genre: '', tag: '', publisher: '', language: '', tier: '', status: 'ACTIVE', published_from: '', published_to: '', sort: 'title', limit: 20 });

  ngOnInit(): void {
    this.api.facets().subscribe({ next: (response) => this.facets.set(response.facets), error: (error: unknown) => this.error.set(toAppHttpError(error).message) });
  }
  search(resetOffset: boolean): void {
    if (resetOffset) this.offset.set(0);
    this.loading.set(true); this.error.set(null);
    this.api.search({ ...this.form.getRawValue(), offset: this.offset() }).pipe(finalize(() => this.loading.set(false))).subscribe({
      next: (response) => { this.response.set(response); const first = response.resources[0]; if (first) this.select(first.resource_id); else this.selected.set(null); },
      error: (error: unknown) => this.error.set(toAppHttpError(error).message),
    });
  }
  page(direction: number): void { this.offset.update((value) => Math.max(0, value + direction * this.form.controls.limit.value)); this.search(false); }
  select(resourceId: string): void {
    this.api.detail(resourceId).subscribe({ next: (response) => this.selected.set(response.resource), error: (error: unknown) => this.error.set(toAppHttpError(error).message) });
  }
  reset(): void { this.form.reset({ q: '', author: '', category: '', genre: '', tag: '', publisher: '', language: '', tier: '', status: 'ACTIVE', published_from: '', published_to: '', sort: 'title', limit: 20 }); this.offset.set(0); this.response.set(null); this.selected.set(null); this.error.set(null); }
}
