import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize } from 'rxjs';
import { toAppHttpError } from '../../core/http/api-error';
import { CombinedSearchResponse, GraphSearchResponse, SearchMode, SearchRequest, SearchResponse } from '../../core/models/api.models';
import { SearchApiService } from '../../core/services/search-api.service';
import { DiagnosticsPanelComponent } from '../../shared/components/diagnostics-panel.component';
import { SearchResultsComponent } from '../../shared/components/search-results.component';
import { StatePanelComponent } from '../../shared/components/state-panel.component';

type SearchKind = 'standard' | 'graph' | 'combined';

@Component({
  imports: [DecimalPipe, ReactiveFormsModule, DiagnosticsPanelComponent, SearchResultsComponent, StatePanelComponent],
  template: `
    <section class="page-heading"><div><p class="eyebrow">RAG retrieval</p><h1>Content search</h1><p>Run lexical, vector, hybrid, Graph RAG, or combined retrieval through the secured gateway.</p></div></section>
    <section class="panel"><form [formGroup]="form" (ngSubmit)="search()" class="filter-form"><label class="wide">Query<textarea formControlName="query" required placeholder="Search ingested document content"></textarea></label><label>Search type<select formControlName="kind"><option value="standard">Standard RAG</option><option value="graph">Graph RAG</option><option value="combined">Combined</option></select></label><label>Standard mode<select formControlName="search_mode"><option value="hybrid">Hybrid</option><option value="vector">Vector</option><option value="keyword">Lexical / keyword</option></select></label><label>Top K<input type="number" min="1" max="50" formControlName="top_k" /></label><label>Minimum score<input type="number" min="0" max="1" step="0.01" formControlName="min_score" /></label><label>Resource ID<input formControlName="resource_id" /></label><label>Category<input formControlName="category" /></label><label>Tags<input formControlName="tags" placeholder="comma separated" /></label><label><input type="checkbox" formControlName="include_chunk_text" /> Include full chunk text</label><label><input type="checkbox" formControlName="debug" [disabled]="form.controls.kind.value !== 'standard'" /> Request debug data</label><div class="button-row full"><button type="submit" class="primary" [disabled]="form.invalid || loading()">{{ loading() ? 'Searching…' : 'Search' }}</button></div></form></section>
    @if (error(); as message) { <app-state-panel kind="error" [message]="message" /> }
    @if (loading()) { <app-state-panel kind="loading" message="Retrieving ranked content…" /> }
    @if (standard(); as result) { <section class="panel"><app-search-results [response]="result" /><app-diagnostics-panel [data]="result.observability" /></section> }
    @if (graph(); as result) { <section class="panel"><h2>Graph RAG results</h2><div class="result-summary">{{ result.matched_entities.length }} entities · {{ result.matched_relationships.length }} relationships · {{ result.graph_summaries.length }} summaries</div><h3>Entities</h3>@for (entity of result.matched_entities; track entity.entity_id) { <article class="result-card"><strong>{{ entity.name }}</strong><span>{{ entity.entity_type }} · {{ entity.score | number:'1.3-3' }}</span><p>{{ entity.description }}</p></article> } @empty { <p class="state-panel">No matching entities.</p> }<h3>Relationships</h3>@for (relationship of result.matched_relationships; track relationship.relationship_id) { <article class="result-card"><strong>{{ relationship.source_entity_name }} → {{ relationship.target_entity_name }}</strong><span>{{ relationship.relationship_type }} · {{ relationship.score | number:'1.3-3' }}</span><p>{{ relationship.description }}</p></article> } @empty { <p class="state-panel">No matching relationships.</p> }<h3>Summaries</h3>@for (summary of result.graph_summaries; track summary.summary_id) { <article class="result-card"><strong>{{ summary.summary_type }}</strong><p>{{ summary.summary_text }}</p></article> } @empty { <p class="state-panel">No graph summaries.</p> }<app-diagnostics-panel [data]="result" /></section> }
    @if (combined(); as result) { <section class="two-column"><article class="panel"><h2>Standard RAG</h2><app-search-results [response]="result.standard_results" /></article><article class="panel"><h2>Graph RAG</h2><p>{{ result.graph_results.matched_entities.length }} entities, {{ result.graph_results.matched_relationships.length }} relationships.</p><app-diagnostics-panel [data]="result.graph_results" /></article></section> }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SearchPageComponent {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly api = inject(SearchApiService);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly standard = signal<SearchResponse | null>(null);
  readonly graph = signal<GraphSearchResponse | null>(null);
  readonly combined = signal<CombinedSearchResponse | null>(null);
  readonly form = this.fb.group({ query: ['', Validators.required], kind: 'standard', search_mode: 'hybrid', top_k: 10, min_score: 0, resource_id: '', category: '', tags: '', include_chunk_text: false, debug: false });

  search(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    const value = this.form.getRawValue();
    const kind = value.kind as SearchKind;
    const standardRequest: SearchRequest = {
      query: value.query.trim(), search_mode: value.search_mode as SearchMode, top_k: value.top_k,
      min_score: value.min_score || undefined,
      filters: { resource_id: value.resource_id || null, category: value.category || null, tags: splitTags(value.tags) },
      include_metadata: true, include_chunk_text: value.include_chunk_text,
    };
    this.loading.set(true); this.error.set(null); this.standard.set(null); this.graph.set(null); this.combined.set(null);
    if (kind === 'graph') {
      this.api.graphSearch({ query: value.query.trim(), resource_ids: value.resource_id ? [value.resource_id] : [], top_k: value.top_k, include_entities: true, include_relationships: true, include_summaries: true }).pipe(finalize(() => this.loading.set(false))).subscribe({ next: (response) => this.graph.set(response), error: (error: unknown) => this.error.set(toAppHttpError(error).message) });
    } else if (kind === 'combined') {
      this.api.combinedSearch(standardRequest).pipe(finalize(() => this.loading.set(false))).subscribe({ next: (response) => this.combined.set(response), error: (error: unknown) => this.error.set(toAppHttpError(error).message) });
    } else {
      const request$ = value.debug ? this.api.debugSearch(standardRequest) : this.api.search(standardRequest);
      request$.pipe(finalize(() => this.loading.set(false))).subscribe({ next: (response) => this.standard.set(response), error: (error: unknown) => this.error.set(toAppHttpError(error).message) });
    }
  }
}

function splitTags(value: string): string[] { return value.split(',').map((tag) => tag.trim()).filter(Boolean); }
