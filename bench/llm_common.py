"""Prompt, output schema and span mapping shared by the LLM baselines (local vLLM and hosted APIs)."""

from __future__ import annotations

PROMPT = """Extract all named entities of the following types from the text. Copy each entity exactly as it appears in the text (same characters, no rewording).

Entity types:
{types}

Text:
{text}

Return JSON: {{"entities": [{{"text": "...", "type": "<type key>"}}]}}. Return an empty list if there are none."""


def json_schema(keys: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}, "type": {"type": "string", "enum": keys}},
                    "required": ["text", "type"],
                },
            }
        },
        "required": ["entities"],
    }


def to_spans(text: str, ents: list[dict], keys: set[str] | None = None) -> list[tuple]:
    """Map generated surfaces back to character offsets (first unused occurrence); drop anything not in the text."""
    spans, taken = [], []
    for e in ents:
        if not isinstance(e, dict):
            continue
        surface = str(e.get("text", "")).strip()
        label = str(e.get("type", ""))
        if not surface or (keys is not None and label not in keys):
            continue
        start = text.find(surface)
        while start >= 0 and any(start < t1 and t0 < start + len(surface) for t0, t1 in taken):
            start = text.find(surface, start + 1)
        if start < 0:
            continue
        end = start + len(surface)
        taken.append((start, end))
        spans.append((start, end, label, surface))
    return spans
