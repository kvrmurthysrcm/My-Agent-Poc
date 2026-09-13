import { Pipe, PipeTransform } from '@angular/core';

// ANGULAR CONCEPT: standalone reusable pipe for presentation-only formatting.
@Pipe({ name: 'bytes' })
export class BytesPipe implements PipeTransform {
  transform(value: number | undefined | null): string {
    if (!value) return '';
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
    return `${(value / 1024 / 1024).toFixed(1)} MB`;
  }
}
