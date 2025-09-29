import json
from pathlib import Path

from dg_core.scanner import scan_text


def test_scanner_matches_golden():
    root = Path(__file__).resolve().parents[1]
    text = (root / "golden" / "sample_scan.txt").read_text(encoding="utf-8")
    expected = json.loads((root / "golden" / "sample_scan.json").read_text(encoding="utf-8"))
    detections = scan_text(text)
    simplified = [{"detector": det.detector, "value": det.value} for det in detections]
    for entry in expected:
        assert entry in simplified