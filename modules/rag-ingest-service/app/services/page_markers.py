import re


PAGE_MARKER_PATTERN = re.compile(r"\[Page\s+(\d+)\]", re.IGNORECASE)


def page_range_for_text(text: str) -> tuple[int | None, int | None]:
    pages = [int(match.group(1)) for match in PAGE_MARKER_PATTERN.finditer(text)]
    if not pages:
        return None, None
    return min(pages), max(pages)
