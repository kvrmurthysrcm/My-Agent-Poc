import { ChangeDetectionStrategy, Component, OnDestroy, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Subscription, finalize } from 'rxjs';
import { toAppHttpError } from '../../core/http/api-error';
import { AnswerComparisonResponse, AnswerMode, AnswerRequest, AnswerResponse, CompareStreamEvent, SearchMode } from '../../core/models/api.models';
import { AnswerApiService } from '../../core/services/answer-api.service';
import { DiagnosticsPanelComponent } from '../../shared/components/diagnostics-panel.component';
import { StatePanelComponent } from '../../shared/components/state-panel.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge.component';

interface ModelCard { model: string; status: 'waiting' | 'loading' | 'answered' | 'failed'; message: string; result?: AnswerResponse; }

@Component({
  imports: [ReactiveFormsModule, DiagnosticsPanelComponent, StatePanelComponent, StatusBadgeComponent],
  template: `
    <section class="page-heading"><div><p class="eyebrow">Multi-model evaluation</p><h1>Compare answers</h1><p>Run one grounded question against multiple models, with secure POST-based SSE progress when enabled.</p></div></section>
    <section class="panel"><form [formGroup]="form" (ngSubmit)="compare()" class="filter-form"><label class="wide">Question<textarea formControlName="query" required placeholder="Ask one question to compare model answers"></textarea></label><label class="wide">Models<input formControlName="models" placeholder="mistral:7b,gemma:7b" required /><span class="hint">Comma-separated model names; maximum eight.</span></label><label>Answer mode<select formControlName="answer_mode"><option value="concise">Concise</option><option value="detailed">Detailed</option><option value="quote-backed">Quote-backed</option></select></label><label>Top K<input type="number" min="1" max="50" formControlName="top_k" /></label><label>Context Top K<input type="number" min="1" max="20" formControlName="context_top_k" /></label><label><input type="checkbox" formControlName="streaming" /> Stream progress with SSE</label><div class="button-row full"><button type="submit" class="primary" [disabled]="form.invalid || running()">{{ running() ? 'Comparing…' : 'Compare models' }}</button>@if (running()) { <button type="button" class="danger" (click)="cancel()">Cancel browser request</button> }</div></form></section>
    @if (error(); as message) { <app-state-panel kind="error" [message]="message" /> }
    @if (running()) { <app-state-panel kind="loading" [message]="progress()" /> }
    @if (cards().length) { <section class="compare-grid">@for (card of cards(); track card.model) { <article class="panel model-card"><div class="panel-heading"><h2>{{ card.model }}</h2><app-status-badge [value]="card.status" /></div><p class="muted">{{ card.message }}</p>@if (card.result; as result) { <p class="answer-text">{{ result.answer }}</p><dl class="detail-grid"><dt>Provider / model</dt><dd>{{ result.llm_provider }} / {{ result.llm_model }}</dd><dt>Sources</dt><dd>{{ result.context_source_count }}</dd><dt>Citations</dt><dd>{{ result.cited_source_ranks.join(', ') || 'none' }}</dd></dl> }</article> }</section> }
    @if (sources().length) { <section class="panel"><h2>Shared sources</h2>@for (source of sources(); track source.chunk_id) { <article class="result-card"><strong>#{{ source.rank }} {{ source.title }}</strong><p>{{ source.snippet }}</p></article> }</section> }
    @if (diagnostics(); as data) { <app-diagnostics-panel [data]="data" /> }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ComparePageComponent implements OnDestroy {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly api = inject(AnswerApiService);
  private activeSubscription?: Subscription;
  readonly running = signal(false);
  readonly error = signal<string | null>(null);
  readonly progress = signal('Waiting to compare models…');
  readonly cardsByModel = signal<Record<string, ModelCard>>({});
  readonly sources = signal<AnswerResponse['sources']>([]);
  readonly diagnostics = signal<unknown>(null);
  readonly cards = signal<ModelCard[]>([]);
  readonly form = this.fb.group({ query: ['', Validators.required], models: ['', Validators.required], answer_mode: 'concise', top_k: 5, context_top_k: 5, streaming: true });

  ngOnDestroy(): void { this.cancel(); }
  compare(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    const value = this.form.getRawValue();
    const models = value.models.split(',').map((model) => model.trim()).filter(Boolean).filter((model, index, all) => all.indexOf(model) === index);
    if (!models.length || models.length > 8) { this.error.set('Provide between one and eight unique model names.'); return; }
    const request: AnswerRequest = { query: value.query.trim(), search_mode: 'hybrid' as SearchMode, answer_mode: value.answer_mode as AnswerMode, top_k: value.top_k, context_top_k: value.context_top_k, filters: { tags: [] }, include_sources: true, compare_models: models };
    this.running.set(true); this.error.set(null); this.progress.set('Preparing shared retrieval context…'); this.sources.set([]); this.diagnostics.set(null);
    this.cardsByModel.set(Object.fromEntries(models.map((model) => [model, { model, status: 'waiting' as const, message: 'Waiting for model start.' }]))); this.refreshCards();
    if (value.streaming) {
      this.activeSubscription = this.api.streamCompare(request).pipe(finalize(() => this.finishRun())).subscribe({
        next: (event) => this.handleStreamEvent(event),
        error: (error: unknown) => this.error.set(toAppHttpError(error).message),
      });
    } else {
      this.activeSubscription = this.api.compare(request).pipe(finalize(() => this.finishRun())).subscribe({
        next: (response) => this.handleComparison(response),
        error: (error: unknown) => this.error.set(toAppHttpError(error).message),
      });
    }
  }
  cancel(): void { this.activeSubscription?.unsubscribe(); this.activeSubscription = undefined; this.running.set(false); if (this.cards().length) this.progress.set('The browser stream was cancelled. Server-side generation may continue if the backend has no cancellation API.'); }
  private handleStreamEvent(event: CompareStreamEvent): void {
    switch (event.event) {
      case 'search_complete': this.sources.set(event.sources); this.progress.set(`Retrieved ${event.search_total_results} results; running ${event.models.length} model(s).`); break;
      case 'model_started': this.updateCard(event.model, { status: 'loading', message: `Generating (${event.completed}/${event.total} complete)…` }); this.progress.set(`Running ${event.model} (${event.completed}/${event.total} complete).`); break;
      case 'model_result': {
        const name = `${event.result.llm_provider}:${event.result.llm_model}`;
        this.updateCard(name, { status: event.result.answer_status === 'failed' ? 'failed' : 'answered', message: `${event.completed}/${event.total} model(s) complete.`, result: event.result });
        this.progress.set(`${event.completed}/${event.total} model(s) complete.`); break;
      }
      case 'complete': this.progress.set(`Completed ${event.completed}/${event.total} model(s) in ${Math.round(event.total_ms)} ms.`); break;
      case 'error': this.error.set(`${event.error_type}: ${event.message}`); break;
    }
  }
  private handleComparison(response: AnswerComparisonResponse): void {
    this.sources.set(response.sources); this.diagnostics.set({ raw_search: response.raw_search, observability: response.observability });
    response.results.forEach((result) => this.updateCard(`${result.llm_provider}:${result.llm_model}`, { status: result.answer_status === 'failed' ? 'failed' : 'answered', message: 'Completed.', result }));
    this.progress.set(`Completed ${response.results.length} model(s).`);
  }
  private finishRun(): void { this.running.set(false); this.activeSubscription = undefined; }
  private updateCard(model: string, update: Partial<ModelCard>): void {
    this.cardsByModel.update((current) => {
      const previous = current[model];
      const card: ModelCard = {
        model,
        status: update.status ?? previous?.status ?? 'waiting',
        message: update.message ?? previous?.message ?? 'Waiting for model start.',
        result: update.result ?? previous?.result,
      };
      return { ...current, [model]: card };
    });
    this.refreshCards();
  }
  private refreshCards(): void { this.cards.set(Object.values(this.cardsByModel())); }
}
