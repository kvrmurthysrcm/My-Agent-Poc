export type JsonValue = string | number | boolean | null | JsonObject | JsonValue[];
export interface JsonObject {
  [key: string]: JsonValue | undefined;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in?: number;
  refresh_expires_in?: number;
  scope?: string;
}

export interface LoginRequest { username: string; password: string; }
export interface RegistrationRequest {
  full_name: string;
  email: string;
  username: string;
  password: string;
  subscription_tier: string;
}
export interface RegistrationTier { tier_code: string; tier_name: string; description?: string; }
export interface RegistrationOptionsResponse {
  subscription_tiers: RegistrationTier[];
  assigned_roles: string[];
  role_assignment_mode: string;
}
export interface RegistrationResponse {
  status: string;
  keycloak_user_id: string;
  library_user_id: string;
  username: string;
  email: string;
  assigned_roles: string[];
  subscription_tier: string;
  approval_status: string;
}
export interface CurrentUser {
  sub: string;
  preferred_username?: string;
  email?: string;
  name?: string;
  roles: string[];
  issuer: string;
}

export type SearchMode = 'vector' | 'keyword' | 'hybrid';
export type IndexingMode = 'NONE' | 'STANDARD' | 'GRAPH' | 'BOTH';
export type AnswerMode = 'concise' | 'detailed' | 'quote-backed';

export interface SearchFilters {
  resource_id?: string | null;
  category?: string | null;
  tags: string[];
  metadata?: JsonObject;
}
export interface SearchRequest {
  query: string;
  search_mode?: SearchMode;
  top_k?: number;
  min_score?: number;
  filters: SearchFilters;
  include_metadata: boolean;
  include_chunk_text?: boolean;
}
export interface SearchResult {
  rank: number;
  resource_id: string;
  chunk_id: string;
  title: string;
  chunk_index: number;
  page_start?: number;
  page_end?: number;
  section_title?: string;
  heading_path: string[];
  score: number;
  vector_score?: number;
  keyword_score?: number;
  snippet: string;
  chunk_text?: string;
  metadata?: JsonObject;
  debug?: JsonObject;
}
export interface SearchResponse {
  query: string;
  original_query?: string;
  query_intent?: string;
  spelling_normalized: boolean;
  search_mode: string;
  top_k: number;
  total_results: number;
  embedding_provider: string;
  embedding_model: string;
  results: SearchResult[];
  observability?: JsonObject;
}
export interface GraphSearchRequest {
  query: string;
  resource_ids: string[];
  top_k: number;
  include_entities?: boolean;
  include_relationships?: boolean;
  include_summaries?: boolean;
}
export interface GraphEntity { entity_id: string; resource_id: string; name: string; normalized_name: string; entity_type: string; description?: string; confidence_score?: number; score: number; metadata: JsonObject; resource_title?: string; }
export interface GraphRelationship { relationship_id: string; resource_id: string; source_entity_id: string; source_entity_name: string; target_entity_id: string; target_entity_name: string; relationship_type: string; description?: string; confidence_score?: number; score: number; metadata: JsonObject; resource_title?: string; }
export interface GraphSummary { summary_id: string; resource_id: string; summary_type: string; summary_text: string; metadata: JsonObject; resource_title?: string; }
export interface GraphSearchResponse { query: string; top_k: number; matched_entities: GraphEntity[]; matched_relationships: GraphRelationship[]; graph_summaries: GraphSummary[]; related_chunks: Array<{ chunk_id: string; resource_id: string; chunk_index: number; snippet: string; resource_title?: string }>; }
export interface CombinedSearchResponse { standard_results: SearchResponse; graph_results: GraphSearchResponse; }

export interface AnswerRequest {
  query: string;
  search_mode: SearchMode;
  top_k?: number;
  context_top_k?: number;
  filters: SearchFilters;
  include_sources?: boolean;
  answer_mode: AnswerMode;
  include_raw_prompt?: boolean;
  system_instruction?: string;
  compare_models?: string[];
}
export interface AnswerSource { rank: number; resource_id: string; chunk_id: string; title: string; chunk_index: number; page_start?: number; page_end?: number; section_title?: string; score: number; snippet: string; }
export interface AnswerResponse {
  query: string;
  answer: string;
  answer_status: 'answered' | 'insufficient_context' | 'failed';
  answer_mode: string;
  llm_provider: string;
  llm_model: string;
  search_mode: string;
  search_total_results: number;
  context_source_count: number;
  cited_source_ranks: number[];
  citation_verification: JsonObject;
  sources: AnswerSource[];
  raw_search?: JsonObject;
  raw_prompt?: string;
  observability?: JsonObject;
}
export interface AnswerComparisonResponse { query: string; search_mode: string; search_total_results: number; context_source_count: number; models: string[]; results: AnswerResponse[]; sources: AnswerSource[]; raw_search?: JsonObject; observability?: JsonObject; }
export type CompareStreamEvent =
  | { event: 'search_complete'; search_total_results: number; context_source_count: number; models: string[]; sources: AnswerSource[] }
  | { event: 'model_started'; model: string; completed: number; total: number }
  | { event: 'model_result'; result: AnswerResponse; completed: number; total: number }
  | { event: 'complete'; completed: number; total: number; total_ms: number }
  | { event: 'error'; error_type: string; message: string };

export interface ChunkingOptions { strategy?: 'INTELLIGENT_RECURSIVE' | 'SEMANTIC_RECURSIVE'; chunk_size_tokens?: number; chunk_overlap_tokens?: number; }
export interface IngestMetadata {
  title?: string;
  description?: string;
  resource_type: string;
  category_name?: string;
  genre?: string;
  business_domain?: string;
  source_system: string;
  author?: string;
  language?: string;
  publisher?: string;
  published_date?: string;
  isbn?: string;
  page_count?: number;
  tags: string[];
  created_date_from_file?: string;
  custom_metadata: JsonObject;
  chunking: ChunkingOptions;
  indexing_mode: IndexingMode;
}
export interface IngestAcceptedResponse { resource_id: string; job_id: string; status: string; message: string; }
export interface JobStatusResponse { job_id: string; resource_id: string; status: string; indexing_mode: string; parser_name?: string; total_chunks: number; processed_chunks: number; embedded_chunks: number; graph_entities_count: number; graph_relationships_count: number; failed_chunks: number; started_at?: string; completed_at?: string; message?: string; progress_message?: string; error_message?: string; profiling: Array<{ step: string; status: string; elapsed_ms: number; details: JsonObject }>; }
export interface JobErrorResponse { error_id: string; job_id: string; resource_id: string; chunk_id?: string; stage: string; error_type: string; error_message: string; error_details: JsonObject; created_at: string; }

export interface AdminResource {
  resource_id: string; title: string; author?: string; category?: string; tags: string[]; ingestion_status: string; rag_enabled: boolean; file_name?: string; file_size_bytes?: number; chunk_count: number; embedding_count: number; job_count: number; latest_job_id?: string; latest_job_status?: string; latest_job_indexing_mode?: string; latest_job_progress_message?: string; latest_job_total_chunks: number; latest_job_processed_chunks: number; latest_job_embedded_chunks: number; latest_job_graph_entities_count: number; latest_job_graph_relationships_count: number; latest_error_message?: string; latest_error_stage?: string; latest_error_type?: string; created_at?: string; metadata: JsonObject;
}
export interface AdminResourceListResponse { total: number; resources: AdminResource[]; }
export interface AdminDeleteResponse { requested: number; deleted: number; results: Array<{ resource_id: string; deleted: boolean; deleted_file_path?: string; deleted_counts: Record<string, number>; error?: string }>; }
export interface AdminActionResponse { resource_id: string; job_id?: string; status: string; indexing_mode?: string; message: string; }
export interface GraphRagSettings { entity_batch_size: number; relationship_batch_size: number; updated_at?: string; message: string; }

export interface CatalogFacets { authors?: string[]; genres?: string[]; categories?: string[]; tags?: string[]; publishers?: string[]; languages?: string[]; subscription_tiers?: RegistrationTier[]; statuses?: string[]; }
export interface CatalogFacetsResponse { facets: CatalogFacets; }
export interface CatalogResource { resource_id: string; title: string; description?: string; authors: string[]; tags: string[]; genre?: string; category?: string; publisher?: string; language?: string; minimum_tier_code?: string; isbn?: string; page_count?: number; published_date?: string; status?: string; ingestion_status?: string; rag_enabled?: boolean; file_name?: string; file_size_bytes?: number; [key: string]: JsonValue | undefined; }
export interface CatalogResourceListResponse { total: number; count: number; limit: number; offset: number; resources: CatalogResource[]; }
export interface CatalogResourceDetailResponse { resource: CatalogResource; }
export interface CatalogQuery { q?: string; author?: string; category?: string; genre?: string; tag?: string; publisher?: string; language?: string; tier?: string; status?: string; published_from?: string; published_to?: string; sort?: string; limit: number; offset: number; }

export interface LibraryAskRequest { question: string; limit: number; offset: number; include_raw: boolean; }
export interface LibraryAskResponse { question: string; selected_tool?: string; tool_arguments: JsonObject; answer: string; debug: JsonObject; raw_tool_result?: JsonObject; }
export interface ToolDefinition { name: string; description?: string; inputSchema?: JsonObject; input_schema?: JsonObject; }
export interface ToolListResponse { tools: ToolDefinition[]; }
export interface ToolCallRequest { name: string; arguments: JsonObject; }

export interface ApiErrorBody { error?: { code?: string; message?: string; details?: JsonObject }; detail?: string | JsonObject; message?: string; }
