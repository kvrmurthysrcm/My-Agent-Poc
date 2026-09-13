import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-status-badge',
  template: '<span class="status-badge" [class]="cssClass()">{{ value() || "unknown" }}</span>',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatusBadgeComponent {
  readonly value = input<string | undefined>('');
  protected cssClass(): string {
    const value = (this.value() ?? '').toLowerCase();
    if (value.includes('failed') || value.includes('error')) return 'status-badge danger';
    if (value.includes('queued') || value.includes('processing')) return 'status-badge warning';
    if (value.includes('ready') || value.includes('complete') || value.includes('answered')) return 'status-badge success';
    return 'status-badge neutral';
  }
}
