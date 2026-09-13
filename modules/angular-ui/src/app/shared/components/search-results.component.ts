import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { JsonViewerComponent } from './json-viewer.component';
import { SearchResponse } from '../../core/models/api.models';

@Component({
  selector: 'app-search-results',
  imports: [DecimalPipe, JsonViewerComponent],
  template: `
    @if (response(); as result) {
      <div class="result-summary">{{ result.total_results }} result(s) · {{ result.search_mode }} · {{ result.embedding_provider }}/{{ result.embedding_model }}</div>
      @for (item of result.results; track item.chunk_id) {
        <article class="result-card"><header><strong>#{{ item.rank }} {{ item.title }}</strong><span>{{ item.score | number: '1.3-3' }}</span></header><p>{{ item.snippet }}</p><small>Chunk {{ item.chunk_index }} · {{ item.resource_id }} @if (item.page_start) { · page {{ item.page_start }} }</small>
          @if (item.chunk_text || item.metadata || item.debug) { <details><summary>Source and debug details</summary>@if (item.chunk_text) { <p class="source-text">{{ item.chunk_text }}</p> }<app-json-viewer [value]="{ metadata: item.metadata, debug: item.debug, vector_score: item.vector_score, keyword_score: item.keyword_score }" /></details> }
        </article>
      } @empty { <p class="state-panel">No matching content was found.</p> }
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SearchResultsComponent {
  readonly response = input<SearchResponse | null>(null);
}
