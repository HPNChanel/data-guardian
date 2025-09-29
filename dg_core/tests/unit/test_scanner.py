import pytest

from dg_core.scanner import Scanner, scan_text


def test_scan_detects_email():
    text = "Contact me at alice@example.com for details."
    detections = scan_text(text)
    emails = [det for det in detections if det.detector == "pii.email"]
    assert emails
    assert emails[0].value == "alice@example.com"


def test_credit_card_luhn_filter():
    text = "Fake 4111 1111 1111 1111 card and junk 1234 5678 9012 3456"
    detections = scan_text(text)
    cards = [det.value for det in detections if det.detector == "pii.credit_card"]
    assert "4111111111111111" in cards
    assert "1234567890123456" not in cards


def test_register_custom_detector():
    scanner = Scanner()
    scanner.registry.register_regex("custom.hex", r"0x[0-9a-fA-F]+", categories=("custom",))
    detections = scanner.scan("value 0xDEADBEEF inside")
    assert any(det.detector == "custom.hex" for det in detections)