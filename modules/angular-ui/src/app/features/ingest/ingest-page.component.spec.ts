import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { IngestApiService } from '../../core/services/ingest-api.service';
import { IngestPageComponent } from './ingest-page.component';

describe('IngestPageComponent', () => {
  it('requires a selected file before submission', async () => {
    await TestBed.configureTestingModule({ imports: [IngestPageComponent], providers: [{ provide: IngestApiService, useValue: { ingest: () => of({}) } }] }).compileComponents();
    const fixture = TestBed.createComponent(IngestPageComponent);
    fixture.componentInstance.upload();
    expect(fixture.componentInstance.error()).toContain('Choose a document');
  });
});
