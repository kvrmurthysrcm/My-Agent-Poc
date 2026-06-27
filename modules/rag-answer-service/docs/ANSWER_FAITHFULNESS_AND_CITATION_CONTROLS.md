# Answer Faithfulness And Citation Controls

The answer service now treats retrieved chunks as the only allowed evidence for generated answers. It asks the LLM to cite every factual answer sentence with source rank, chunk, and page when available, then verifies the generated answer before returning it. If the answer cannot be tied back to selected context, the service returns an `insufficient_context` response instead of exposing unsupported claims.

Implementation date: 2026-06-27

## Feature Summary

- Answers are generated only after `rag-search-service` returns selected context.
- Prompt instructions require citations in this form:

```text
[Source rank 1, chunk 8, page 19]
```

- The post-generation verifier checks:
  - the answer includes source-rank citations
  - cited source ranks exist in the selected context
  - cited chunks match the selected source rank
  - answer terms overlap enough with selected source text
- Unsupported or uncited answers are replaced with an `insufficient_context` answer.
- Raw prompts are returned only when `include_raw_prompt=true`.

## API Additions

`POST /rag/answer` request fields:

- `answer_mode`: one of `concise`, `detailed`, or `quote-backed`
- `include_raw_prompt`: defaults to `false`

Response fields:

- `answer_status`: `answered` or `insufficient_context`
- `answer_mode`: selected answer mode
- `cited_source_ranks`: source ranks cited by the answer
- `citation_verification`: verifier details and failure reason when rejected
- `raw_prompt`: present only when explicitly requested

## Answer Modes

- `concise`: one or two supported sentences with citations.
- `detailed`: fuller answer, still requiring citations for each factual sentence.
- `quote-backed`: prefers short direct quotations from retrieved context.

## Insufficient Context Behavior

The service returns `answer_status=insufficient_context` when:

- search returns no selected context
- the LLM answers without source-rank citations
- the LLM cites a source rank that was not selected
- the LLM cites the wrong chunk for a selected source
- the generated answer has weak evidence overlap with selected context

This protects cases where the LLM attempts to answer from memory or from a nearby but unsupported passage.

## Ramana Maharshi Case

The context packer and verifier favor the passage about peace and inner stillness when answering the question about Paul Brunton's impression of Ramana Maharshi. A generated answer must cite the selected source rank and chunk for that passage; an answer citing unrelated guide/Yogi material is rejected if that cited rank/chunk was not selected or does not support the answer.

## Verification

Focused tests cover:

- supported cited answers
- no-context insufficient responses
- unsupported uncited answers
- wrong chunk citations
- answer modes and raw prompt gating

Run from the module directory:

```powershell
pytest
```
