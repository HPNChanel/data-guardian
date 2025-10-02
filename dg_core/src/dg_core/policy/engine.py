"""Policy evaluation engine."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

import regex

from ..models import Detection, RedactionAction, RedactionDecision
from .schema import PolicyDocument, PolicyRule

_ALLOWED_CALLS: Dict[str, Callable[..., Any]] = {
    "regex_match": lambda pattern, value: bool(regex.search(pattern, value or "")),
    "in_list": lambda value, values: value in values,
}

_ALLOWED_ATTR_METHODS = {"startswith", "endswith", "lower", "upper"}


class ExpressionError(Exception):
    """Raised when a policy expression is invalid."""


@dataclass(slots=True)
class CompiledRule:
    matcher: Callable[[Detection], bool]
    rule: PolicyRule


class SafeExpression:
    """Compile and evaluate limited boolean expressions."""

    def __init__(self, expression: str) -> None:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ExpressionError(str(exc)) from exc
        self._validate(tree)
        self._code = compile(tree, filename="<policy>", mode="eval")

    def _validate(self, node: ast.AST) -> None:
        allowed_nodes = (
            ast.Expression,
            ast.BoolOp,
            ast.UnaryOp,
            ast.BinOp,
            ast.Compare,
            ast.Eq,
            ast.NotEq,
            ast.In,
            ast.NotIn,
            ast.Gt,
            ast.GtE,
            ast.Lt,
            ast.LtE,
            ast.Call,
            ast.Name,
            ast.Attribute,
            ast.Load,
            ast.Constant,
            ast.List,
            ast.Tuple,
            ast.Dict,
            ast.Subscript,
            ast.Index,
            ast.Slice,
        )
        if not isinstance(node, allowed_nodes):
            raise ExpressionError(f"Unsupported expression node: {type(node).__name__}")
        if isinstance(node, ast.Call):
            self._validate_call(node)
        for child in ast.iter_child_nodes(node):
            self._validate(child)

    def _validate_call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name):
            if func.id not in _ALLOWED_CALLS:
                raise ExpressionError(f"Unsupported function call: {func.id}")
        elif isinstance(func, ast.Attribute):
            if not isinstance(func.value, ast.Name):
                raise ExpressionError("Only attribute calls on named objects are allowed")
            if func.attr not in _ALLOWED_ATTR_METHODS:
                raise ExpressionError(f"Method '{func.attr}' is not allowed in policies")
        else:
            raise ExpressionError("Unsupported callable in expression")

    def __call__(self, context: Dict[str, Any]) -> bool:
        namespace = SafeEvalNamespace(context)
        return bool(eval(self._code, {"__builtins__": {}}, namespace))


class SafeEvalNamespace(dict):
    """Namespace enforcing allowed access during evaluation."""

    def __init__(self, context: Dict[str, Any]) -> None:
        super().__init__(context)
        self.update(_ALLOWED_CALLS)


def _compile_rule(rule: PolicyRule) -> CompiledRule:
    expression = SafeExpression(rule.when)

    def matcher(detection: Detection) -> bool:
        context = {
            "detector": detection.detector,
            "value": detection.value,
            "categories": detection.categories,
            "context_before": detection.context_before,
            "context_after": detection.context_after,
        }
        return expression(context)

    return CompiledRule(matcher=matcher, rule=rule)


class PolicyEngine:
    """Deterministic evaluation of detections against policy rules."""

    def __init__(self, document: PolicyDocument) -> None:
        self.document = document
        self._compiled: List[CompiledRule] = [
            _compile_rule(rule) for rule in document.sorted_rules()
        ]
        self._allow_domains = {entry.lower() for entry in document.allowlist.email_domains}

    def decision_for(self, detection: Detection) -> RedactionDecision:
        allowlist_action = self._allowlist_override(detection)
        if allowlist_action:
            return allowlist_action
        for compiled in self._compiled:
            if compiled.matcher(detection):
                return RedactionDecision(
                    action=compiled.rule.action,
                    reason=compiled.rule.name,
                    preserve_length=(
                        compiled.rule.preserve_length
                        if compiled.rule.preserve_length is not None
                        else self.document.defaults.preserve_length
                    ),
                    salt=_salt_bytes(compiled.rule.salt or self.document.defaults.salt),
                )
        return RedactionDecision(
            action=self.document.defaults.action,
            reason="defaults",
            preserve_length=self.document.defaults.preserve_length,
            salt=_salt_bytes(self.document.defaults.salt),
        )

    def detector_enabled(self, detector_name: str) -> bool:
        selectors = self.document.detectors
        if selectors.include:
            if not any(_matches_selector(detector_name, selector) for selector in selectors.include):
                return False
        if selectors.exclude:
            if any(_matches_selector(detector_name, selector) for selector in selectors.exclude):
                return False
        return True

    def _allowlist_override(self, detection: Detection) -> RedactionDecision | None:
        if detection.detector.startswith("pii.email") and self._allow_domains:
            parts = detection.value.split("@")
            if len(parts) == 2 and parts[1].lower() in self._allow_domains:
                return RedactionDecision(
                    action=RedactionAction.ALLOW,
                    reason="allowlist.email_domain",
                    preserve_length=True,
                )
        return None


def _matches_selector(detector_name: str, selector: str) -> bool:
    if selector.endswith(".*"):
        return detector_name.startswith(selector[:-2])
    return detector_name == selector


def _salt_bytes(salt: str | None) -> bytes | None:
    if not salt:
        return None
    try:
        return bytes.fromhex(salt)
    except ValueError:
        return salt.encode("utf-8")


__all__ = ["PolicyEngine"]