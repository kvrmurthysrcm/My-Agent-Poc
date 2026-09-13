import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { AdminApiService } from '../../core/services/admin-api.service';
import { AuthService } from '../../core/auth/auth.service';
import { ResourceApiService } from '../../core/services/resource-api.service';
import { BooksPageComponent } from './books-page.component';

describe('BooksPageComponent', () => {
  it('derives dashboard metrics from loaded resource statuses', async () => {
    await TestBed.configureTestingModule({
      imports: [BooksPageComponent],
      providers: [
        { provide: AuthService, useValue: { hasAnyRole: () => false } },
        { provide: AdminApiService, useValue: {} },
        { provide: ResourceApiService, useValue: { list: () => of({ total: 2, resources: [
          { resource_id: 'ready', title: 'Ready book', tags: [], ingestion_status: 'COMPLETED', rag_enabled: true, chunk_count: 3, embedding_count: 3, job_count: 1, latest_job_total_chunks: 3, latest_job_processed_chunks: 3, latest_job_embedded_chunks: 3, latest_job_graph_entities_count: 0, latest_job_graph_relationships_count: 0, metadata: {} },
          { resource_id: 'failed', title: 'Failed book', tags: [], ingestion_status: 'FAILED', rag_enabled: false, chunk_count: 0, embedding_count: 0, job_count: 1, latest_job_total_chunks: 0, latest_job_processed_chunks: 0, latest_job_embedded_chunks: 0, latest_job_graph_entities_count: 0, latest_job_graph_relationships_count: 0, metadata: {} },
        ] }) } },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(BooksPageComponent);
    fixture.detectChanges();
    expect(fixture.componentInstance.metrics()).toEqual({ total: 2, ready: 1, active: 0, failed: 1 });
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Ready book');
  });
});
