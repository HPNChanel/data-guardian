from pathlib import Path

from dg_core.policy import policy_from_path, PolicyEngine
from dg_core.redactor.engines import RedactionEngine
from dg_core.scanner import scan_text


def _default_policy():
    return policy_from_path(Path(__file__).resolve().parents[2] / "policies" / "default.yaml")


def test_secret_redacted():
    text = "AWS key AKIA1234567890ABCD12 present"
    detections = scan_text(text)
    engine = PolicyEngine(_default_policy())
    redactor = RedactionEngine(engine)
    redacted, _ = redactor.redact(text, detections)
    assert "AKIA1234567890ABCD12" not in redacted
    assert "[REDACTED]" in redacted


def test_preserve_length_mask():
    text = "Email alice@example.com"
    detections = scan_text(text)
    engine = PolicyEngine(_default_policy())
    redactor = RedactionEngine(engine)
    redacted, _ = redactor.redact(text, detections)
    assert len(redacted) == len(text)