from __future__ import annotations

import tiktoken

_ENCODING: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    global _ENCODING
    if _ENCODING is None:
        _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping token-aware chunks using tiktoken cl100k_base encoding.

    Args:
        text: The input text to split.
        size: Target chunk size in tokens.
        overlap: Number of tokens to overlap between consecutive chunks.

    Returns:
        List of text chunk strings.
    """
    enc = _get_encoding()
    tokens = enc.encode(text)

    if not tokens:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(tokens):
        end = min(start + size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text_str = enc.decode(chunk_tokens)
        chunks.append(chunk_text_str)

        if end == len(tokens):
            break

        start = end - overlap

    return chunks
