from pathlib import Path

from hypothesis import given, strategies as st

from dg_core.policy import policy_from_path, PolicyEngine
from dg_core.redactor.engines import RedactionEngine
from dg_core.scanner import scan_text

_policy = policy_from_path(Path(__file__).resolve().parents[2] / "policies" / "default.yaml")
_redactor_engine = RedactionEngine(PolicyEngine(_policy))


@given(
    st.text(min_size=0, max_size=24),
    st.sampled_from([
        "alice@example.com",
        "AKIA1234567890ABCD12",
        "4111 1111 1111 1111",
        "555-12-3456",
    ]),
    st.text(min_size=0, max_size=24),
)
def test_redaction_idempotent(prefix: str, secret: str, suffix: str) -> None:
    text = prefix + secret + suffix
    detections = scan_text(text)
    redacted_one, _ = _redactor_engine.redact(text, detections)
    detections_two = scan_text(redacted_one)
    redacted_two, _ = _redactor_engine.redact(redacted_one, detections_two)
    assert redacted_one == redacted_two