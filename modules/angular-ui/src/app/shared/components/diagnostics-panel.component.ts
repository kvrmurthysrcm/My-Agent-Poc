import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { TraceService } from '../../core/observability/trace.service';
import { JsonViewerComponent } from './json-viewer.component';

@Component({
  selector: 'app-diagnostics-panel',
  imports: [JsonViewerComponent],
  template: `
    <details class="diagnostics">
      <summary>Developer diagnostics</summary>
      @if (trace.latest(); as latest) { <dl><dt>Trace ID</dt><dd>{{ latest.traceId }}</dd><dt>Span ID</dt><dd>{{ latest.spanId }}</dd><dt>Request ID</dt><dd>{{ latest.requestId || 'not returned' }}</dd></dl> }
      @if (data() !== null) { <app-json-viewer [value]="data()" /> }
    </details>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DiagnosticsPanelComponent {
  protected readonly trace = inject(TraceService);
  readonly data = input<unknown>(null);
}
