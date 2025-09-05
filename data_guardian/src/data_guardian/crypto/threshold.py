from __future__ import annotations

"""Simple Shamir Secret Sharing (SSS) over secp256k1 prime field for 32-byte secrets.

This is intended for threshold-wrapping the CEK (content encryption key).
Do not use for arbitrary large secrets beyond 32 bytes.
"""

import os
from typing import List, Tuple

# Prime for secp256k1 field
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F


def _modinv(a: int, p: int) -> int:
    return pow(a, p - 2, p)


def _eval_poly(coeffs: List[int], x: int) -> int:
    y = 0
    xp = 1
    for c in coeffs:
        y = (y + c * xp) % P
        xp = (xp * x) % P
    return y


def split_secret(secret: bytes, n: int, k: int) -> List[Tuple[int, int]]:
    if len(secret) != 32:
        raise ValueError("Secret must be 32 bytes")
    if not (1 < k <= n <= 255):
        raise ValueError("Invalid (k, n)")
    s = int.from_bytes(secret, "big") % P
    # random coeffs: degree k-1 with a0 = s
    coeffs = [s] + [int.from_bytes(os.urandom(32), "big") % P for _ in range(k - 1)]
    shares: List[Tuple[int, int]] = []
    for x in range(1, n + 1):
        y = _eval_poly(coeffs, x)
        shares.append((x, y))
    return shares


def combine_shares(shares: List[Tuple[int, int]], k: int) -> bytes:
    if len(shares) < k:
        raise ValueError("Not enough shares")
    # Lagrange interpolation at x=0
    x_s = [x for x, _ in shares[:k]]
    y_s = [y for _, y in shares[:k]]
    s = 0
    for j in range(k):
        num = 1
        den = 1
        xj = x_s[j]
        for m in range(k):
            if m == j:
                continue
            xm = x_s[m]
            num = (num * (-xm % P)) % P
            den = (den * (xj - xm) % P) % P
        lj = (num * _modinv(den, P)) % P
        s = (s + y_s[j] * lj) % P
    return int(s).to_bytes(32, "big")

