# Define dataclasses or typed models (e.g., KeyInfo, DgdHeader).
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class KeyInfo:
  kid: str
  alg: str     #* RSA | ED25519
  label: str
  created_at: int  #* Epochs second

@dataclass
class Recipient:
  kid: str
  ek_b64: str
  
@dataclass
class DgdHeader:
  v: int
  alg: str   #* AES-256-GCM
  enc: str   #* RSA-OAEP
  nonce_b64: str
  recipients: List[Recipient]
  chunk: bool = False
  
  def to_json(self) -> str:
    import json
    return json.dumps({
      "v": self.v, "alg": self.alg, "enc": self.enc,
      "nonce": self.nonce_b64,
      "recipients": [ {"kid": r.kid, "ek": r.ek_b64} for r in self.recipients ],
      "chunk": self.chunk
    }, ensure_ascii=False)
  