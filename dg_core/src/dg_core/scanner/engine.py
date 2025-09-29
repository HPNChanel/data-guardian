"""Scanner orchestration logic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from ..models import Detection
from ..utils.text import normalize
from .patterns import load_builtin_detectors
from .registry import Detector, DetectorRegistry, SpanMapper


@dataclass(slots=True)
class ScannerConfig:
    enabled: Sequence[str] | None = None
    disabled: Sequence[str] | None = None
    context_window: int = 32
    max_detections: int | None = None


class Scanner:
    """Run registered detectors against input data."""

    def __init__(self, registry: DetectorRegistry | None = None, config: ScannerConfig | None = None) -> None:
        self.registry = registry or DetectorRegistry()
        if not self.registry.all():
            load_builtin_detectors(self.registry)
        self.config = config or ScannerConfig()

    def scan(self, data: str | bytes) -> List[Detection]:
        text, offsets = normalize(data)
        mapper = SpanMapper(text, offsets, context_window=self.config.context_window)
        detectors = list(self._resolve_detectors())
        detections: List[Detection] = []
        for detector in detectors:
            for detection in detector.detect(text, mapper):
                detections.append(detection)
                if self.config.max_detections and len(detections) >= self.config.max_detections:
                    return _dedupe_sorted(detections)
        return _dedupe_sorted(detections)

    def _resolve_detectors(self) -> Iterable[Detector]:
        enabled = list(self.config.enabled or self.registry.all().keys())
        disabled = set(self.config.disabled or [])
        for selector in enabled:
            for detector in self.registry.iter_matching(selector):
                if detector.name in disabled:
                    continue
                yield detector


def scan_text(
    data: str | bytes,
    *,
    scanner: Scanner | None = None,
    config: ScannerConfig | None = None,
) -> List[Detection]:
    runner = scanner or Scanner(config=config)
    if config is not None:
        runner.config = config
    return runner.scan(data)


def _dedupe_sorted(detections: List[Detection]) -> List[Detection]:
    seen: Dict[Tuple[str, int, int], Detection] = {}
    for detection in detections:
        key = (detection.detector, detection.span.start, detection.span.end)
        if key not in seen:
            seen[key] = detection
    ordered_keys = sorted(seen.keys(), key=lambda key: key[1])
    return [seen[key] for key in ordered_keys]


__all__ = ["Scanner", "ScannerConfig", "scan_text"]