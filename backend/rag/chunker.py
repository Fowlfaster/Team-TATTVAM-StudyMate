from typing import Any


def chunk_pieces(
    pieces: list[dict[str, Any]],
    source_type: str,
    topic: str = "Uncategorized",
    target_words: int = 500,
    overlap_words: int = 50,
) -> list[dict[str, Any]]:
    if target_words <= 0 or overlap_words < 0 or overlap_words >= target_words:
        raise ValueError("target_words must be positive and overlap_words smaller than target_words")

    located_words: list[tuple[str, dict[str, Any]]] = []
    for piece in pieces:
        text = str(piece.get("text", "")).strip()
        located_words.extend((word, piece) for word in text.split())

    chunks: list[dict[str, Any]] = []
    start_index = 0
    while start_index < len(located_words):
        end_index = min(start_index + target_words, len(located_words))
        if end_index < len(located_words) and len(located_words) - end_index <= overlap_words:
            end_index = len(located_words)

        words = located_words[start_index:end_index]
        first_piece = words[0][1]
        last_piece = words[-1][1]
        chunk: dict[str, Any] = {
            "text": " ".join(word for word, _ in words),
            "topic": topic,
        }

        if source_type == "pdf":
            page_start = int(first_piece["page"])
            page_end = int(last_piece["page"])
            chunk.update({
                "page_start": page_start,
                "page_end": page_end,
                "location": f"page {page_start}" if page_start == page_end else f"pages {page_start}-{page_end}",
            })
        elif source_type == "slides":
            slide_start = int(first_piece["slide"])
            slide_end = int(last_piece["slide"])
            chunk.update({
                "slide_start": slide_start,
                "slide_end": slide_end,
                "location": f"slide {slide_start}" if slide_start == slide_end else f"slides {slide_start}-{slide_end}",
            })
        elif source_type == "video":
            start_time = float(first_piece["start"])
            end_time = float(last_piece["end"])
            chunk.update({
                "start": start_time,
                "end": end_time,
                "location": f"{start_time:.2f}-{end_time:.2f} seconds",
            })
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

        chunks.append(chunk)
        if end_index == len(located_words):
            break
        start_index = end_index - overlap_words

    return chunks