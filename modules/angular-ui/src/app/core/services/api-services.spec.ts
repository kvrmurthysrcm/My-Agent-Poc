import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AnswerApiService } from './answer-api.service';
import { SearchApiService } from './search-api.service';

describe('typed API services', () => {
  let search: SearchApiService; let answer: AnswerApiService; let http: HttpTestingController;
  beforeEach(() => { TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] }); search = TestBed.inject(SearchApiService); answer = TestBed.inject(AnswerApiService); http = TestBed.inject(HttpTestingController); });
  afterEach(() => http.verify());
  it('posts a strongly shaped standard search request', () => {
    search.search({ query: 'architecture', search_mode: 'hybrid', top_k: 5, filters: { tags: [] }, include_metadata: true }).subscribe();
    const request = http.expectOne('/api/rag/search');
    expect(request.request.method).toBe('POST'); expect(request.request.body.query).toBe('architecture');
    request.flush({ query: 'architecture', spelling_normalized: false, search_mode: 'hybrid', top_k: 5, total_results: 0, embedding_provider: 'ollama', embedding_model: 'test', results: [] });
  });
  it('posts a grounded-answer request to the gateway', () => {
    answer.answer({ query: 'What is RAG?', search_mode: 'hybrid', answer_mode: 'concise', filters: { tags: [] } }).subscribe();
    const request = http.expectOne('/api/rag/answer');
    expect(request.request.method).toBe('POST'); request.flush({ query: 'What is RAG?', answer: 'Answer', answer_status: 'answered', answer_mode: 'concise', llm_provider: 'ollama', llm_model: 'test', search_mode: 'hybrid', search_total_results: 1, context_source_count: 1, cited_source_ranks: [1], citation_verification: {}, sources: [] });
  });
});
