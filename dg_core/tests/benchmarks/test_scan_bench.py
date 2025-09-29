import pytest

from dg_core.scanner import scan_text


@pytest.mark.bench
def test_scan_throughput(benchmark):
    text = "\n".join(["alice@example.com AKIA1234567890ABCD12 4111111111111111"] * 100)
    benchmark(lambda: scan_text(text))