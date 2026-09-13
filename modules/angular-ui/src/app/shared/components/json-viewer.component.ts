import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-json-viewer',
  template: '<pre class="json-viewer">{{ formatted() }}</pre>',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class JsonViewerComponent {
  readonly value = input<unknown>(null);
  protected formatted(): string { return JSON.stringify(this.value(), null, 2) ?? ''; }
}
