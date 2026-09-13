import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { firstValueFrom, toArray } from 'rxjs';
import { AnswerApiService } from './answer-api.service';

describe('AnswerApiService streaming', () => {
  it('parses POST SSE events and completes cleanly', async () => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient()] });
    const service = TestBed.inject(AnswerApiService);
    const payload = 'event: search_complete\ndata: {"event":"search_complete","search_total_results":2,"context_source_count":1,"models":["model"],"sources":[]}\n\n';
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode(payload)); controller.close(); } }), { status: 200, headers: { 'content-type': 'text/event-stream' } }));
    const events = await firstValueFrom(service.streamCompare({ query: 'test', search_mode: 'hybrid', answer_mode: 'concise', filters: { tags: [] }, compare_models: ['model'] }).pipe(toArray()));
    expect(events[0].event).toBe('search_complete');
    expect(fetchSpy).toHaveBeenCalledWith('/api/rag/answer/compare/stream', expect.objectContaining({ method: 'POST' }));
    fetchSpy.mockRestore();
  });
});
