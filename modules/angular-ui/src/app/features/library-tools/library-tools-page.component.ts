import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormControl, FormRecord, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize } from 'rxjs';
import { toAppHttpError } from '../../core/http/api-error';
import { JsonObject, JsonValue, ToolDefinition } from '../../core/models/api.models';
import { LibraryToolsApiService } from '../../core/services/library-tools-api.service';
import { JsonViewerComponent } from '../../shared/components/json-viewer.component';
import { StatePanelComponent } from '../../shared/components/state-panel.component';

type ArgumentControl = FormControl<string | number | boolean>;
interface ToolField { name: string; type: string; description?: string; required: boolean; defaultValue: string | number | boolean; }

@Component({
  imports: [ReactiveFormsModule, JsonViewerComponent, StatePanelComponent],
  template: `
    <section class="page-heading"><div><p class="eyebrow">Administrator diagnostics</p><h1>Raw Library Tools</h1><p>Inspect and call discoverable MCP-backed tools through the authorized gateway.</p></div><button type="button" class="secondary" (click)="load()" [disabled]="loading()">{{ loading() ? 'Loading…' : 'Load tools' }}</button></section>
    @if (error(); as message) { <app-state-panel kind="error" [message]="message" /> }
    <section class="two-column tool-layout"><aside class="panel"><h2>Tools</h2>@for (tool of tools(); track tool.name) { <button type="button" class="tool-button" [class.active]="selected()?.name === tool.name" (click)="select(tool)"><strong>{{ pretty(tool.name) }}</strong><small>{{ tool.description || '' }}</small></button> } @empty { <app-state-panel kind="empty" message="Load tools to inspect MCP capabilities." /> }</aside><article class="panel"><h2>{{ selected() ? pretty(selected()?.name ?? '') : 'Select a tool' }}</h2>@if (selected(); as tool) { <p>{{ tool.description || 'No description supplied.' }}</p><form [formGroup]="argumentForm" (ngSubmit)="call()" class="filter-form">@for (field of fields(); track field.name) { <label [class.wide]="field.type === 'object' || field.type === 'array'">{{ field.name }} @if (field.required) { <span aria-hidden="true">*</span> } @if (field.type === 'object' || field.type === 'array') { <textarea [formControl]="controlFor(field.name)" [placeholder]="field.description || ('JSON ' + field.type)"></textarea> } @else if (field.type === 'boolean') { <input type="checkbox" [formControl]="controlFor(field.name)" /> } @else { <input [type]="inputType(field.type)" [formControl]="controlFor(field.name)" [attr.min]="field.type === 'integer' || field.type === 'number' ? 0 : null" /> }<span class="hint">{{ field.description || field.type }}</span></label> } @empty { <p class="hint">This tool takes no arguments.</p> }<button class="primary" type="submit" [disabled]="calling()">{{ calling() ? 'Running…' : 'Run tool' }}</button></form> } @else { <app-state-panel kind="empty" message="Choose a tool to generate its argument form." /> }</article></section>
    @if (result(); as value) { <section class="panel"><h2>Tool result</h2><app-json-viewer [value]="value" /></section> }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LibraryToolsPageComponent implements OnInit {
  private readonly api = inject(LibraryToolsApiService);
  readonly tools = signal<ToolDefinition[]>([]);
  readonly selected = signal<ToolDefinition | null>(null);
  readonly loading = signal(false);
  readonly calling = signal(false);
  readonly error = signal<string | null>(null);
  readonly result = signal<JsonObject | null>(null);
  readonly argumentForm = new FormRecord<ArgumentControl>({});
  readonly fields = computed(() => fieldsFor(this.selected()));

  ngOnInit(): void { this.load(); }
  load(): void {
    this.loading.set(true); this.error.set(null);
    this.api.tools().pipe(finalize(() => this.loading.set(false))).subscribe({ next: (response) => { this.tools.set(response.tools); const first = response.tools[0]; if (first) this.select(first); }, error: (error: unknown) => this.error.set(toAppHttpError(error).message) });
  }
  select(tool: ToolDefinition): void {
    this.selected.set(tool); this.result.set(null); this.error.set(null);
    Object.keys(this.argumentForm.controls).forEach((key) => this.argumentForm.removeControl(key));
    fieldsFor(tool).forEach((field) => this.argumentForm.addControl(field.name, new FormControl(field.defaultValue, { nonNullable: true, validators: field.required ? [field.type === 'boolean' ? Validators.requiredTrue : Validators.required] : [] })));
  }
  controlFor(name: string): ArgumentControl { return this.argumentForm.controls[name] ?? new FormControl('', { nonNullable: true }); }
  inputType(type: string): 'text' | 'number' { return type === 'number' || type === 'integer' ? 'number' : 'text'; }
  pretty(name: string): string { return name.replace(/^get_/, '').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()); }
  call(): void {
    const tool = this.selected();
    if (!tool) return;
    if (this.argumentForm.invalid) { this.argumentForm.markAllAsTouched(); return; }
    const argumentsValue = this.buildArguments();
    if (!argumentsValue) return;
    this.calling.set(true); this.error.set(null); this.result.set(null);
    this.api.call({ name: tool.name, arguments: argumentsValue }).pipe(finalize(() => this.calling.set(false))).subscribe({ next: (result) => this.result.set(result), error: (error: unknown) => this.error.set(toAppHttpError(error).message) });
  }
  private buildArguments(): JsonObject | null {
    const result: JsonObject = {};
    for (const field of this.fields()) {
      const value = this.argumentForm.controls[field.name]?.value;
      if ((value === '' || value === null) && !field.required) continue;
      if (field.type === 'object' || field.type === 'array') {
        const parsed = parseJsonValue(String(value));
        if (parsed === null) { this.error.set(`${field.name} must contain valid JSON.`); return null; }
        result[field.name] = parsed;
      } else if (field.type === 'integer' || field.type === 'number') {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) { this.error.set(`${field.name} must be a number.`); return null; }
        result[field.name] = numeric;
      } else result[field.name] = value;
    }
    return result;
  }
}

function fieldsFor(tool: ToolDefinition | null): ToolField[] {
  if (!tool) return [];
  const schema = tool.inputSchema ?? tool.input_schema;
  if (!schema) return [];
  const properties = schema['properties'];
  if (!isJsonObject(properties)) return [];
  const requiredValues = schema['required'];
  const required = Array.isArray(requiredValues) ? new Set(requiredValues.filter((value): value is string => typeof value === 'string')) : new Set<string>();
  return Object.entries(properties).filter((entry): entry is [string, JsonObject] => isJsonObject(entry[1])).map(([name, property]) => {
    const type = typeof property['type'] === 'string' ? property['type'] : 'string';
    const defaultCandidate = property['default'];
    return { name, type, description: typeof property['description'] === 'string' ? property['description'] : undefined, required: required.has(name), defaultValue: defaultFor(type, defaultCandidate) };
  });
}
function defaultFor(type: string, candidate: JsonValue | undefined): string | number | boolean {
  if (typeof candidate === 'string' || typeof candidate === 'number' || typeof candidate === 'boolean') return candidate;
  if (type === 'boolean') return false;
  if (type === 'integer' || type === 'number') return 0;
  if (type === 'object') return '{}';
  if (type === 'array') return '[]';
  return '';
}
function parseJsonValue(value: string): JsonValue | null { try { return JSON.parse(value) as JsonValue; } catch { return null; } }
function isJsonObject(value: JsonValue | undefined): value is JsonObject { return typeof value === 'object' && value !== null && !Array.isArray(value); }
