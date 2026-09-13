import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-state-panel',
  template: `<div class="state-panel" [class.error]="kind() === 'error'" [attr.role]="kind() === 'error' ? 'alert' : 'status'">{{ message() }}</div>`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatePanelComponent {
  readonly message = input.required<string>();
  readonly kind = input<'loading' | 'empty' | 'error' | 'success'>('empty');
}
