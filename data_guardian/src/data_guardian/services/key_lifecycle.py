from __future__ import annotations

from ..storage.keystore import KeyStore


class KeyLifecycle:
    def __init__(self, store: KeyStore | None = None) -> None:
        self.store = store or KeyStore()

    def set_expiry(self, kid: str, expiry: int | None) -> None:
        self.store.set_expiry(kid, expiry)

    def clean_expired(self) -> int:
        return self.store.clean_expired()

