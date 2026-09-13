import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize } from 'rxjs';
import { toAppHttpError } from '../../core/http/api-error';
import { JsonObject, JsonValue, LibraryAskResponse } from '../../core/models/api.models';
import { LibraryAgentApiService } from '../../core/services/library-agent-api.service';
import { DiagnosticsPanelComponent } from '../../shared/components/diagnostics-panel.component';
import { StatePanelComponent } from '../../shared/components/state-panel.component';

@Component({
  imports: [ReactiveFormsModule, DiagnosticsPanelComponent, StatePanelComponent],
  template: `
    <section class="page-heading"><div><p class="eyebrow">MCP-backed library agent</p><h1>Library Search</h1><p>Ask natural-language questions about catalog, users, subscriptions, and approvals.</p></div></section>
    <section class="two-column"><article class="panel"><form [formGroup]="form" (ngSubmit)="ask()"><label>Question<textarea formControlName="question" required placeholder="Ask about books, authors, users, tags, subscriptions, or approvals"></textarea></label><div class="button-row"><button type="button" class="secondary small" (click)="guided('List available books and resources.')">Books</button><button type="button" class="secondary small" (click)="guided('List authors.')">Authors</button><button type="button" class="secondary small" (click)="guided('Show pending user approval requests.')">Approvals</button><button type="button" class="secondary small" (click)="guided('Show user bookshelf records.')">Bookshelf</button></div><div class="form-grid"><label>Limit<input type="number" min="1" max="100" formControlName="limit" /></label><label>Offset<input type="number" min="0" formControlName="offset" /></label></div><button class="primary" type="submit" [disabled]="form.invalid || loading()">{{ loading() ? 'Searching…' : 'Ask library agent' }}</button></form></article><article class="panel"><h2>Agent answer</h2>@if (error(); as message) { <app-state-panel kind="error" [message]="message" /> } @else if (loading()) { <app-state-panel kind="loading" message="Selecting and running a library tool…" /> } @else if (response(); as answer) { <strong>{{ answer.selected_tool || 'No matching tool' }}</strong><p class="answer-text">{{ answer.answer }}</p><small>Question: {{ answer.question }}</small><app-diagnostics-panel [data]="{ tool_arguments: answer.tool_arguments, debug: answer.debug }" /> } @else { <app-state-panel kind="empty" message="Ask a question to use the Library Search agent." /> }</article></section>
    @if (rows().length) { <section class="panel"><h2>Returned data</h2><div class="table-wrap"><table><thead><tr>@for (column of columns(); track column) { <th>{{ column }}</th> }</tr></thead><tbody>@for (row of rows(); track $index) { <tr>@for (column of columns(); track column) { <td>{{ format(row[column]) }}</td> }</tr> }</tbody></table></div></section> }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LibrarySearchPageComponent {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly api = inject(LibraryAgentApiService);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly response = signal<LibraryAskResponse | null>(null);
  readonly rows = computed(() => rowsFrom(this.response()?.raw_tool_result));
  readonly columns = computed(() => [...new Set(this.rows().flatMap((row) => Object.keys(row)))]);
  readonly form = this.fb.group({ question: ['', Validators.required], limit: 10, offset: 0 });

  guided(question: string): void { this.form.controls.question.setValue(question); }
  ask(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.loading.set(true); this.error.set(null); this.response.set(null);
    const value = this.form.getRawValue();
    this.api.ask({ ...value, question: value.question.trim(), include_raw: true }).pipe(finalize(() => this.loading.set(false))).subscribe({ next: (response) => this.response.set(response), error: (error: unknown) => this.error.set(toAppHttpError(error).message) });
  }
  format(value: JsonValue | undefined): string { return typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value ?? ''); }
}

function rowsFrom(raw: JsonObject | undefined): JsonObject[] {
  if (!raw) return [];
  const candidate = raw['rows'] ?? raw['resources'];
  return Array.isArray(candidate) ? candidate.filter(isJsonObject) : [];
}
function isJsonObject(value: JsonValue): value is JsonObject { return typeof value === 'object' && value !== null && !Array.isArray(value); }
