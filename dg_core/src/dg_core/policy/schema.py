"""Policy document schemas."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from ..models import RedactionAction


class DetectorSelectors(BaseModel):
    include: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)


class AllowList(BaseModel):
    email_domains: List[str] = Field(default_factory=list)


class PolicyDefaults(BaseModel):
    action: RedactionAction = RedactionAction.MASK
    preserve_length: bool = False
    salt: Optional[str] = None


class PolicyRule(BaseModel):
    name: str
    when: str
    action: RedactionAction
    priority: int = Field(default=100, ge=0, le=1000)
    preserve_length: Optional[bool] = None
    salt: Optional[str] = None


class PolicyDocument(BaseModel):
    version: int = Field(default=1, ge=1)
    name: str = Field(default="default")
    description: str = Field(default="")
    defaults: PolicyDefaults = Field(default_factory=PolicyDefaults)
    rules: List[PolicyRule] = Field(default_factory=list)
    detectors: DetectorSelectors = Field(default_factory=DetectorSelectors)
    allowlist: AllowList = Field(default_factory=AllowList)

    def sorted_rules(self) -> List[PolicyRule]:
        return sorted(self.rules, key=lambda rule: rule.priority)


def policy_from_path(path: Path) -> PolicyDocument:
    import json

    import yaml

    with path.open("r", encoding="utf-8") as handle:
        if path.suffix.lower() in {".yaml", ".yml"}:
            raw = yaml.safe_load(handle)
        else:
            raw = json.load(handle)
    return PolicyDocument.model_validate(raw)


__all__ = [
    "PolicyDocument",
    "PolicyRule",
    "PolicyDefaults",
    "DetectorSelectors",
    "AllowList",
    "policy_from_path",
]