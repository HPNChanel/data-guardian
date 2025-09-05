from data_guardian.crypto.threshold import split_secret, combine_shares
import os


def test_threshold_combine():
    secret = os.urandom(32)
    shares = split_secret(secret, n=5, k=3)
    # pick any 3
    part = shares[0:3]
    recovered = combine_shares(part, 3)
    assert recovered == secret

