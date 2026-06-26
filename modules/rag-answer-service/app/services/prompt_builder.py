DEFAULT_SYSTEM_INSTRUCTION = (
    "You are a grounded RAG answer assistant. Use only the provided context. "
    "Do not add facts from memory. If the context is insufficient, say what is missing. "
    "Prefer direct passages that answer the user's wording over background setup. "
    "Do not confuse guides, devotees, or other yogis with the named subject. "
    "Answer concisely and mention page or source cues when useful."
)


class PromptBuilder:
    def build(self, query: str, context: str, system_instruction: str | None = None) -> str:
        instruction = system_instruction.strip() if system_instruction and system_instruction.strip() else DEFAULT_SYSTEM_INSTRUCTION
        return (
            f"{instruction}\n\n"
            f"Question:\n{query}\n\n"
            f"Context:\n{context}\n\n"
            "Answer:"
        )
