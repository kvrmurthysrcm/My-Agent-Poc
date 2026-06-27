DEFAULT_SYSTEM_INSTRUCTION = (
    "You are a grounded RAG answer assistant. Use only the provided context. "
    "Do not add facts from memory. If the context is insufficient, say what is missing. "
    "Prefer direct passages that answer the user's wording over background setup. "
    "Do not confuse guides, devotees, or other yogis with the named subject. "
    "Every factual claim must cite the supporting source rank, chunk, and page when available."
)


class PromptBuilder:
    def build(
        self,
        query: str,
        context: str,
        system_instruction: str | None = None,
        answer_mode: str = "concise",
    ) -> str:
        instruction = system_instruction.strip() if system_instruction and system_instruction.strip() else DEFAULT_SYSTEM_INSTRUCTION
        mode_instruction = self._mode_instruction(answer_mode)
        return (
            f"{instruction}\n\n"
            "Citation rules:\n"
            "- Cite each answer sentence with source rank and chunk, for example: [Source rank 1, chunk 8, page 19].\n"
            "- Use only source ranks present in the context labels.\n"
            "- If the retrieved context does not support the answer, respond exactly: insufficient_context.\n\n"
            f"Answer mode:\n{mode_instruction}\n\n"
            f"Question:\n{query}\n\n"
            f"Context:\n{context}\n\n"
            "Answer:"
        )

    def _mode_instruction(self, answer_mode: str) -> str:
        if answer_mode == "detailed":
            return "Give a detailed answer with all important supported facts, but cite every factual sentence."
        if answer_mode == "quote-backed":
            return "Prefer short direct quotations from the context, each followed by its citation."
        return "Give a concise answer in one or two sentences, citing every factual sentence."
