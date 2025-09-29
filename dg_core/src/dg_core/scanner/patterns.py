"""Built-in detector patterns for DG Core."""
from __future__ import annotations

import regex

from ..utils.checks import luhn_valid
from .registry import DetectorRegistry

EMAIL_PATTERN = r"(?<![\w+.-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])"
PHONE_PATTERN = r"(?<!\d)(?:\+\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4})(?!\d)"
CREDIT_CARD_PATTERN = r"\b(?:\d[ -]*?){13,19}\b"
SSN_PATTERN = r"\b\d{3}-\d{2}-\d{4}\b"
IBAN_PATTERN = r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}\b"
IPV4_PATTERN = r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
IPV6_PATTERN = r"\b(?:[A-F0-9]{1,4}:){7}[A-F0-9]{1,4}\b"
AWS_ACCESS_KEY_PATTERN = r"\bAKIA[0-9A-Z]{16}\b"
GOOGLE_API_KEY_PATTERN = r"\bAIza[0-9A-Za-z\-_]{35}\b"
JWT_PATTERN = r"eyJ[A-Za-z0-9_\-]+?\.[A-Za-z0-9_\-]+?\.[A-Za-z0-9_\-]+"
PRIVATE_KEY_PATTERN = r"-----BEGIN (?:RSA |DSA |EC )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |DSA |EC )?PRIVATE KEY-----"
DOTENV_PATTERN = r"(?m)^[A-Z][A-Z0-9_]{2,}=(.+)$"
URL_WITH_CREDS_PATTERN = r"https?://[\w.-]+:[^@\s]+@[\w.-]+(?:[:/][^\s]*)?"
BEARER_TOKEN_PATTERN = r"\b(?:ya29\.|xoxp-|xoxb-)[0-9A-Za-z\-]{20,}\b"
IBAN_STRICT_PATTERN = r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"


def load_builtin_detectors(registry: DetectorRegistry) -> DetectorRegistry:
    registry.register_regex("pii.email", EMAIL_PATTERN, categories=("pii", "email"))
    registry.register_regex("pii.phone", PHONE_PATTERN, categories=("pii", "phone"))
    registry.register_regex(
        "pii.credit_card",
        CREDIT_CARD_PATTERN,
        categories=("pii", "payment"),
        validator=luhn_valid,
        normalizer=lambda value: regex.sub(r"[ -]", "", value),
    )
    registry.register_regex("pii.ssn", SSN_PATTERN, categories=("pii", "government"))
    registry.register_regex(
        "pii.iban",
        IBAN_PATTERN,
        categories=("pii", "bank"),
        flags=regex.IGNORECASE,
    )
    registry.register_regex("pii.ipv4", IPV4_PATTERN, categories=("pii", "network"))
    registry.register_regex("pii.ipv6", IPV6_PATTERN, categories=("pii", "network"), flags=regex.IGNORECASE)
    registry.register_regex("secrets.aws_access_key", AWS_ACCESS_KEY_PATTERN, categories=("secret",))
    registry.register_regex("secrets.google_api_key", GOOGLE_API_KEY_PATTERN, categories=("secret",))
    registry.register_regex("secrets.jwt", JWT_PATTERN, categories=("secret", "token"))
    registry.register_regex(
        "secrets.private_key",
        PRIVATE_KEY_PATTERN,
        categories=("secret", "key"),
        flags=regex.DOTALL,
    )
    registry.register_regex(
        "config.dotenv",
        DOTENV_PATTERN,
        categories=("config",),
        flags=regex.MULTILINE,
    )
    registry.register_regex("config.url_creds", URL_WITH_CREDS_PATTERN, categories=("config", "secret"))
    registry.register_regex("secrets.bearer", BEARER_TOKEN_PATTERN, categories=("secret", "token"))
    registry.register_regex("pii.iban_strict", IBAN_STRICT_PATTERN, categories=("pii", "bank"))
    return registry


__all__ = ["load_builtin_detectors"]