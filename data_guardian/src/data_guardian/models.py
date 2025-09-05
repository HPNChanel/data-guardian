# Define dataclasses or typed models (e.g., KeyInfo, DgdHeader).
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Literal, Optional

@dataclass
class KeyInfo:
  kid: str
  alg: str     #* RSA | ED25519
  label: str
  created_at: int  #* Epochs second

@dataclass
class Recipient:
  kid: str
  # For RSA: ek_b64 contains wrapped CEK. For X25519: ek_b64 is 'ct' and epk/nonce present.
  ek_b64: str
  scheme: Literal["RSA-OAEP", "X25519-KEM"] = "RSA-OAEP"
  epk_pem_b64: Optional[str] = None  # For X25519 only
  nonce_b64: Optional[str] = None    # For X25519 only (wrapping CEK)
  
@dataclass
class DgdHeader:
  v: int
  aead: Literal["AESGCM", "CHACHA20"]
  enc: Literal["RSA-OAEP", "X25519-KEM"]
  content_nonce_b64: str
  recipients: List[Recipient]
  chunk: bool = False
  # optional threshold
  threshold_k: Optional[int] = None
  # streaming options
  chunk_size: Optional[int] = None
  total_size: Optional[int] = None
  
  def to_json(self) -> str:
    import json
    def enc_recipient(r: Recipient) -> dict:
      d = {"kid": r.kid, "ek": r.ek_b64, "scheme": r.scheme}
      if r.scheme == "X25519-KEM":
        d["epk_pem_b64"] = r.epk_pem_b64
        d["nonce"] = r.nonce_b64
      return d
    return json.dumps({
      "v": self.v, "aead": self.aead, "enc": self.enc,
      "nonce": self.content_nonce_b64,
      "recipients": [ enc_recipient(r) for r in self.recipients ],
      "chunk": self.chunk,
      "threshold_k": self.threshold_k,
      "chunk_size": self.chunk_size,
      "total_size": self.total_size,
    }, ensure_ascii=False)
  
