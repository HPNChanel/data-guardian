from pathlib import Path

from dg_core.models import Detection, RedactionAction, Span
from dg_core.policy import policy_from_path, PolicyEngine


def test_policy_allowlist_allows_trusted_email():
    policy = policy_from_path(Path(__file__).resolve().parents[2] / "policies" / "default.yaml")
    engine = PolicyEngine(policy)
    detection = Detection(
        detector="pii.email",
        value="user@trusted.example",
        span=Span(start=0, end=0),
        context_before="",
        context_after="",
    )
    decision = engine.decision_for(detection)
    assert decision.action == RedactionAction.ALLOW


def test_policy_default_action_mask():
    policy = policy_from_path(Path(__file__).resolve().parents[2] / "policies" / "default.yaml")
    engine = PolicyEngine(policy)
    detection = Detection(
        detector="pii.phone",
        value="555-123-9876",
        span=Span(start=0, end=0),
        context_before="",
        context_after="",
    )
    decision = engine.decision_for(detection)
    assert decision.action == RedactionAction.MASK