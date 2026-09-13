import { ChangeDetectionStrategy, Component, output, input } from '@angular/core';

@Component({
  selector: 'app-confirm-dialog',
  template: `
    @if (open()) {
      <div class="dialog-backdrop" (click)="cancel.emit()">
        <section class="dialog" role="alertdialog" aria-modal="true" [attr.aria-labelledby]="titleId" (click)="$event.stopPropagation()">
          <h2 [id]="titleId">{{ title() }}</h2>
          <p>{{ message() }}</p>
          <div class="button-row"><button type="button" class="secondary" (click)="cancel.emit()">Cancel</button><button type="button" class="danger" (click)="confirm.emit()">Confirm</button></div>
        </section>
      </div>
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConfirmDialogComponent {
  readonly open = input(false);
  readonly title = input('Confirm action');
  readonly message = input.required<string>();
  readonly confirm = output<void>();
  readonly cancel = output<void>();
  protected readonly titleId = `confirmation-${crypto.randomUUID()}`;
}
