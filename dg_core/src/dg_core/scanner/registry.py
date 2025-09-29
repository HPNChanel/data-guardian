"""Detector registry and helpers for scanners."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, Iterator, Mapping, Sequence, Tuple

import regex

from ..models import Detection


class Detector:
    """Protocol-like base class for detectors."""

    name: str
    categories: Sequence[str]

    def detect(self, text: str, mapper: "SpanMapper") -> Iterable[Detection]:  # pragma: no cover - protocol
        raise NotImplementedError


@dataclass(slots=True)
class RegexDetector(Detector):
    """Detector backed by a compiled regular expression."""

    name: str
    pattern: regex.Pattern[str]
    categories: Sequence[str] = field(default_factory=tuple)
    max_matches: int | None = None
    validator: Callable[[str], bool] | None = None
    normalizer: Callable[[str], str] | None = None

    def detect(self, text: str, mapper: "SpanMapper") -> Iterable[Detection]:
        count = 0
        for match in self.pattern.finditer(text, overlapped=True):
            value = match.group()
            if self.validator and not self.validator(value):
                continue
            detection = mapper.to_detection(self.name, match, tuple(self.categories))
            if self.normalizer:
                detection.value = self.normalizer(value)
            yield detection
            count += 1
            if self.max_matches is not None and count >= self.max_matches:
                break


class SpanMapper:
    """Utility to convert regex matches into Detection objects."""

    __slots__ = ("_text", "_byte_offsets", "_context_window")

    def __init__(self, text: str, byte_offsets: Sequence[int], context_window: int = 32) -> None:
        self._text = text
        self._byte_offsets = byte_offsets
        self._context_window = context_window

    def to_detection(self, detector: str, match: regex.Match[str], categories: Tuple[str, ...]) -> Detection:
        start, end = match.span()
        span = (self._byte_offsets[start], self._byte_offsets[end])
        before_start = max(0, start - self._context_window)
        after_end = min(len(self._text), end + self._context_window)
        return Detection(
            detector=detector,
            span=self._to_span(span),
            value=match.group(),
            context_before=self._text[before_start:start],
            context_after=self._text[end:after_end],
            categories=categories,
        )

    @staticmethod
    def _to_span(byte_span: tuple[int, int]):
        from ..models import Span

        return Span(start=byte_span[0], end=byte_span[1])


class DetectorRegistry:
    """Runtime registry for built-in and user provided detectors."""

    def __init__(self) -> None:
        self._detectors: Dict[str, Detector] = {}

    def register(self, detector: Detector, override: bool = False) -> None:
        if not override and detector.name in self._detectors:
            raise ValueError(f"Detector already registered: {detector.name}")
        self._detectors[detector.name] = detector

    def register_regex(
        self,
        name: str,
        pattern: str,
        *,
        flags: regex.RegexFlag | int = regex.UNICODE,
        categories: Sequence[str] | None = None,
        override: bool = False,
        validator: Callable[[str], bool] | None = None,
        normalizer: Callable[[str], str] | None = None,
    ) -> None:
        compiled = regex.compile(pattern, flags)
        self.register(
            RegexDetector(
                name=name,
                pattern=compiled,
                categories=tuple(categories or ()),
                validator=validator,
                normalizer=normalizer,
            ),
            override=override,
        )

    def unregister(self, name: str) -> None:
        self._detectors.pop(name, None)

    def get(self, name: str) -> Detector:
        try:
            return self._detectors[name]
        except KeyError as exc:
            raise KeyError(f"Unknown detector: {name}") from exc

    def all(self) -> Mapping[str, Detector]:
        return dict(self._detectors)

    def iter_matching(self, selector: str) -> Iterator[Detector]:
        if selector.endswith(".*"):
            prefix = selector[:-2]
            for name, detector in self._detectors.items():
                if name.startswith(prefix):
                    yield detector
        else:
            yield self.get(selector)

    def clear(self) -> None:
        self._detectors.clear()


__all__ = ["Detector", "RegexDetector", "DetectorRegistry", "SpanMapper"]