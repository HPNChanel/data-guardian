"""Redaction engine that applies policy decisions to text."""
from __future__ import annotations

from bisect import bisect_left
from typing import List, Sequence, Tuple

from ..models import Detection, RedactionDecision, RedactedSegment
from ..policy import PolicyEngine
from ..utils.text import byte_offsets, to_text
from .strategies import apply_strategy


class RedactionEngine:
    def __init__(self, policy_engine: PolicyEngine) -> None:
        self.policy_engine = policy_engine

    def redact(self, text: str | bytes, detections: Sequence[Detection]) -> Tuple[str | bytes, List[RedactedSegment]]:
        decoded = to_text(text)
        output, segments = self._redact_string(decoded, detections)
        if isinstance(text, bytes):
            return output.encode("utf-8", errors="surrogatepass"), segments
        return output, segments

    def _redact_string(self, text: str, detections: Sequence[Detection]) -> Tuple[str, List[RedactedSegment]]:
        if not detections:
            return text, []
        byte_index_map = byte_offsets(text)
        replacements: List[Tuple[int, int, str, RedactionDecision, Detection]] = []
        for detection in detections:
            decision = self.policy_engine.decision_for(detection)
            start_index = _byte_to_char_index(byte_index_map, detection.span.start)
            end_index = _byte_to_char_index(byte_index_map, detection.span.end)
            replacement = apply_strategy(detection, decision)
            replacements.append((start_index, end_index, replacement, decision, detection))
        replacements.sort(key=lambda item: item[0], reverse=True)
        mutated = text
        segments: List[RedactedSegment] = []
        for start, end, replacement, decision, detection in replacements:
            mutated = mutated[:start] + replacement + mutated[end:]
            segments.append(
                RedactedSegment(
                    span=detection.span,
                    replacement=replacement,
                    action=decision.action,
                )
            )
        segments.reverse()
        return mutated, segments


def _byte_to_char_index(mapping: Sequence[int], byte_pos: int) -> int:
    index = bisect_left(mapping, byte_pos)
    if index >= len(mapping) or mapping[index] != byte_pos:
        raise ValueError(f"Byte offset {byte_pos} does not align to UTF-8 boundary")
    return index


__all__ = ["RedactionEngine"]