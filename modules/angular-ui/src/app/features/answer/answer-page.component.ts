import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize } from 'rxjs';
import { toAppHttpError } from '../../core/http/api-error';
import { AnswerMode, AnswerRequest, AnswerResponse, SearchMode } from '../../core/models/api.models';
import { AnswerApiService } from '../../core/services/answer-api.service';
import { DiagnosticsPanelComponent } from '../../shared/components/diagnostics-panel.component';
import { StatePanelComponent } from '../../shared/components/state-panel.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';

@Component({
  imports: [ReactiveFormsModule, DiagnosticsPanelComponent, StatePanelComponent, StatusBadgeComponent],
  template: `
    <section class="page-heading"><div><p class="eyebrow">Grounded generation</p><h1>Ask books</h1><p>Generate an answer only from retrieved, cited library content.</p></div></section>
    <section class="panel"><form [formGroup]="form" (ngSubmit)="ask()" class="filter-form"><label class="wide">Question<textarea formControlName="query" required placeholder="Ask a question about ingested books"></textarea></label><label>Answer mode<select formControlName="answer_mode"><option value="concise">Concise</option><option value="detailed">Detailed</option><option value="quote-backed">Quote-backed</option></select></label><label>Search mode<select formControlName="search_mode"><option value="hybrid">Hybrid</option><option value="vector">Vector</option><option value="keyword">Lexical</option></select></label><label>Top K<input type="number" min="1" max="50" formControlName="top_k" /></label><label>Context Top K<input type="number" min="1" max="20" formControlName="context_top_k" /></label><label>Resource ID<input formControlName="resource_id" /></label><label>Category<input formControlName="category" /></label><label>Tags<input formControlName="tags" placeholder="comma separated" /></label><label class="wide">System instruction (optional)<textarea formControlName="system_instruction" maxlength="2000" placeholder="Only use if your backend policy permits it"></textarea></label><label><input type="checkbox" formControlName="include_sources" /> Include sources</label><label><input type="checkbox" formControlName="include_raw_prompt" /> Request developer diagnostics</label><div class="button-row full"><button type="submit" class="primary" [disabled]="form.invalid || loading()">{{ loading() ? 'Generating…' : 'Generate answer' }}</button></div></form></section>
    @if (error(); as message) { <app-state-panel kind="error" [message]="message" /> }
    @if (loading()) { <app-state-panel kind="loading" message="Generating a grounded answer; local models can take a while." /> }
    @if (response(); as answer) { <section class="two-column"><article class="panel"><div class="panel-heading"><h2>Answer</h2><app-status-badge [value]="answer.answer_status" /></div><p class="answer-text">{{ answer.answer }}</p><dl class="detail-grid"><dt>Provider / model</dt><dd>{{ answer.llm_provider }} / {{ answer.llm_model }}</dd><dt>Search / context sources</dt><dd>{{ answer.search_total_results }} / {{ answer.context_source_count }}</dd><dt>Cited ranks</dt><dd>{{ answer.cited_source_ranks.join(', ') || 'none' }}</dd></dl>@if (answer.answer_status === 'insufficient_context') { <app-state-panel kind="empty" message="The retrieved evidence was insufficient to support an answer." /> }<app-diagnostics-panel [data]="{ citation_verification: answer.citation_verification, observability: answer.observability, raw_search: answer.raw_search, raw_prompt: answer.raw_prompt }" /></article><article class="panel"><h2>Sources</h2>@for (source of answer.sources; track source.chunk_id) { <article class="result-card"><strong>#{{ source.rank }} {{ source.title }}</strong><p>{{ source.snippet }}</p><small>Chunk {{ source.chunk_index }} · score {{ source.score }}</small></article> } @empty { <app-state-panel kind="empty" message="No sources were returned." /> }</article></section> }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnswerPageComponent {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly api = inject(AnswerApiService);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly response = signal<AnswerResponse | null>(null);
  readonly form = this.fb.group({ query: ['', Validators.required], answer_mode: 'concise', search_mode: 'hybrid', top_k: 5, context_top_k: 5, resource_id: '', category: '', tags: '', include_sources: true, include_raw_prompt: false, system_instruction: '' });

  ask(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    const value = this.form.getRawValue();
    const request: AnswerRequest = {
      query: value.query.trim(), answer_mode: value.answer_mode as AnswerMode, search_mode: value.search_mode as SearchMode,
      top_k: value.top_k, context_top_k: value.context_top_k,
      filters: { resource_id: value.resource_id || null, category: value.category || null, tags: splitTags(value.tags) },
      include_sources: value.include_sources, include_raw_prompt: value.include_raw_prompt,
      system_instruction: value.system_instruction.trim() || undefined,
    };
    this.loading.set(true); this.error.set(null); this.response.set(null);
    this.api.answer(request).pipe(finalize(() => this.loading.set(false))).subscribe({ next: (response) => this.response.set(response), error: (error: unknown) => this.error.set(toAppHttpError(error).message) });
  }
}

function splitTags(value: string): string[] { return value.split(',').map((tag) => tag.trim()).filter(Boolean); }
