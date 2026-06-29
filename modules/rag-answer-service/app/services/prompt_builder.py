DEFAULT_SYSTEM_INSTRUCTION = (
    "You are a grounded RAG answer assistant. Use only the provided context. "
    "Do not add facts from memory. Read every context block before answering. "
    "Synthesize all relevant evidence across the provided sources instead of stopping at the first matching chunk. "
    "If the context supports only part of the question, answer the supported part and clearly say what is missing. "
    "Every factual claim must cite the supporting source rank and chunk. "
    "If the named person, place, work, or event in the question is not present in the retrieved context, do not infer an answer from thematically similar text."
)

DEFAULT_SYNTHESIS_INSTRUCTION = (
    "Answer the question by combining all relevant facts from the selected context blocks. "
    "Prefer sources that directly answer the question, but include additional relevant details from other source ranks when they add useful context. "
    "Do not invent names, relationships, events, dates, or explanations that are not present in the context. "
    "Do not infer an answer from unrelated chunks that merely share broad words from the question. "
    "Do not write '[insufficient_context]' inside an otherwise supported answer; use a normal sentence to say which part is missing."
)

DEFAULT_GUARDRAIL_INSTRUCTION = (
    "Safety and quality guardrails: refuse requests for abusive, hateful, sexual, violent, illegal, or privacy-invasive content. "
    "For normal knowledge questions, never hallucinate. If the retrieved context does not contain the named subject and requested fact, respond exactly: insufficient_context."
)


class PromptBuilder:
    def __init__(
        self,
        default_system_instruction: str | None = None,
        synthesis_instruction: str | None = None,
        guardrail_instruction: str | None = None,
    ) -> None:
        self.default_system_instruction = default_system_instruction or DEFAULT_SYSTEM_INSTRUCTION
        self.synthesis_instruction = synthesis_instruction or DEFAULT_SYNTHESIS_INSTRUCTION
        self.guardrail_instruction = guardrail_instruction or DEFAULT_GUARDRAIL_INSTRUCTION

    def build(
        self,
        query: str,
        context: str,
        system_instruction: str | None = None,
        answer_mode: str = "concise",
    ) -> str:
        instruction = system_instruction.strip() if system_instruction and system_instruction.strip() else self.default_system_instruction
        mode_instruction = self._mode_instruction(answer_mode)
        return (
            f"{instruction}\n\n"
            "Synthesis rules:\n"
            f"- {self.synthesis_instruction}\n"
            "- Use multiple source ranks when multiple chunks contain relevant facts.\n"
            "- If two sources contain duplicate text, cite the best-ranked duplicate once; do not repeat the same fact.\n\n"
            "Guardrails:\n"
            f"- {self.guardrail_instruction}\n\n"
            "Citation rules:\n"
            "- Cite each answer sentence with source rank and chunk, for example: [Source rank 1, chunk 8, page 19].\n"
            "- Use only source ranks present in the context labels.\n"
            "- If no retrieved context supports the question at all, respond exactly: insufficient_context.\n"
            "- If the context partially supports the question, answer the supported facts with citations and state what is not available in the context.\n\n"
            f"Answer mode:\n{mode_instruction}\n\n"
            f"Question:\n{query}\n\n"
            f"Context:\n{context}\n\n"
            "Answer:"
        )

    def _mode_instruction(self, answer_mode: str) -> str:
        if answer_mode == "detailed":
            return "Give a detailed synthesized answer with all important supported facts from the context, but cite every factual sentence."
        if answer_mode == "quote-backed":
            return "Prefer short direct quotations from the context, each followed by its citation."
        return "Give a concise synthesized answer in two to four sentences, citing every factual sentence."
