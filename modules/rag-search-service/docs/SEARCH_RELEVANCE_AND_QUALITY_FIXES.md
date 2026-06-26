# Search Relevance and Result Quality Fixes

## Problem

Hybrid search was ranking unrelated chunks above exact matches for some queries. The clearest failure was an exact `A Christmas Carol` quote ranking below Ramayan, Gita, and Upanishads chunks.

The SQLite keyword fallback counted raw query substrings. Common words such as `the`, `a`, `and`, `of`, `in`, and `that` gave long unrelated chunks very high keyword scores. Hybrid ranking then forced any keyword score over a small threshold to `0.95`, which let bad keyword hits overpower semantic and title matches.

Search responses also exposed stored page markers and already-ingested low-value chunks, such as publisher/footer text.

## Fixes

- Keyword scoring now uses meaningful lexical tokens instead of raw substring counts.
- Stopwords and very short tokens are ignored.
- Common aliases normalize into comparable terms, for example `Githa`, `Geetha`, and `Gita`.
- `Ramayana` normalizes toward `Ramayan`.
- Exact phrase matches receive a strong signal and rank above vector-only candidates.
- Title and resource metadata token overlap are explicitly boosted.
- Long queries require minimum meaningful-term coverage before a keyword result qualifies.
- Conversational prefixes such as `tell me about` and subject prefixes such as `the novel:` are stripped before retrieval.
- The old hard hybrid score clamp for `keyword_score >= 5` was removed.
- Low-value result chunks are filtered at search time to reduce the impact of old indexed data.
- `[Page N]` markers are stripped from snippets and returned `chunk_text`; page references remain in `page_start` and `page_end`.

## Verified Behavior

The query:

```text
The very gold and silver fish, set forth among these choice fruits in a bowl, though members of a dull and stagnant-blooded race, appeared to know that there was something going on
```

now ranks the matching `A Christmas Carol` chunk first.

## Remaining Work

Search still returns chunks. For prompts such as `Tell me about Ramayan`, a better product behavior would be a document-level answer path that identifies the resource, selects representative content chunks, and composes a concise answer with citations.
