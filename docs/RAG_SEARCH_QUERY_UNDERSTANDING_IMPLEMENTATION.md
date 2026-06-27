# RAG Search Query Understanding Implementation
This feature improves how the RAG search service understands user questions before retrieval starts. 
It cleans up conversational phrasing, fixes known spelling and entity typos, classifies the query intent, and passes that intent into retrieval, reranking, and answer context packing. 
The goal is to make natural-language queries such as "tell me about A Christams Carol", exact quote lookups, broad summaries, and factual questions retrieve 
the right chunks with less manual query tuning.



Implementation date: 2026-06-27

## Scope

This implements Task 6 from `TODO/RAG_TIGHTENING_PLAN.md` for the RAG search path, with a small answer-service integration so normalized query intent can influence context packing.

## Search Changes

- Added structured query understanding in `modules/rag-search-service/app/search/query_preprocessor.py`.
- The preprocessor now returns:
  - `original_query`
  - `normalized_query`
  - `query_intent`
  - `normalized_terms`
  - `spelling_normalized`
- Supported intents:
  - `exact_quote`
  - `title_lookup`
  - `summary_request`
  - `factual_question`
  - `broad_document_query`
- Conversational prefixes are stripped before retrieval, including `tell me about`, `summarize`, `summary of`, `find`, and `search for`.
- Subject prefixes such as `the novel:` and `book:` are stripped before retrieval.
- Common typo/entity normalization is now configurable through:
  - `QUERY_ALIASES`
  - `QUERY_ALIASES_FILE`

## Configurable Aliases

Default aliases live in `modules/rag-search-service/app/search/default_query_aliases.json` and cover the known bad cases:

```json
{
  "christams": "christmas",
  "githa": "gita",
  "brenton": "brunton"
}
```

The same alias map also keeps existing title/entity normalizations such as `bhagawat -> bhagavad`, `geetha -> gita`, and `ramayana -> ramayan`.

Aliases can be overridden or extended without editing Python code:

```powershell
$env:QUERY_ALIASES='{"custmr":"customer","polcy":"policy"}'
```

For larger glossary-style maps, set `QUERY_ALIASES_FILE` to a JSON object path.

## Ranking And Retrieval

- Search responses now include `original_query`, `query_intent`, and `spelling_normalized`.
- Keyword search receives `query_intent`.
- PostgreSQL keyword search uses `websearch_to_tsquery` by default and switches to `phraseto_tsquery` for `exact_quote`.
- Reranking now uses the explicit query intent:
  - exact quotes receive phrase-match boosts and non-matching candidates are slightly penalized.
  - summary and broad document queries downrank front matter and boilerplate more strongly.
  - title lookup behavior still promotes early chunks from title-matched resources.
- Lexical token normalization now accepts the configured alias map instead of relying only on fixed module-level aliases.

## Answer Context Packing

`rag-answer-service` now passes the normalized search query into context packing. The context builder reads `query_intent` from the search response and downranks front-matter/boilerplate chunks for summary and broad-document requests before packing context.

## Tests And Verification

Added focused tests in `modules/rag-search-service/tests/test_rag_search.py` for:

- typo normalization: `A Christams Carol -> A Christmas Carol`
- runtime alias configuration
- exact quote intent propagation to keyword search
- query intent being returned by the search response

Verification performed:

```powershell
.\.venv\Scripts\python.exe -m compileall app tests
.\.venv\Scripts\python.exe -m compileall ..\rag-answer-service\app ..\rag-answer-service\tests
```

Both compile checks passed.

The full search pytest run was attempted with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rag_search.py
```

It did not reach test bodies because local PostgreSQL database `online_library_test` does not exist.
