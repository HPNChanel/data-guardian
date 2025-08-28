
from fastapi import FastAPI, UploadFile, HTTPException, Form

from pydantic import BaseModel
from pathlib import Path
from typing import List
from data_guardian.crypto import asymmetric as asy, symmetric as sym
from data_guardian.storage.keystore import KeyStore
from data_guardian.services.envelope import EnvelopeHeader, RecipientEntry, FORMAT_VERSION
from data_guardian.utils import b64e, b64d, sha256_file
from data_guardian.policy.policy import enforce, OperationContext, check_passphrase_strength

app = FastAPI(title="Data Guardian API", version="4.0.0")

class EncryptRequest(BaseModel):
    recipients: List[str]
    passphrase: str
    chunk_bytes: int = 1024*1024

@app.post("/encrypt")
async def encrypt_api(file: UploadFile, req: EncryptRequest):
    enforce(OperationContext(op="encrypt", actor=None, details={"recipients": req.recipients}))
    check_passphrase_strength(req.passphrase)
    ks = KeyStore()
    key = sym.gen_key()
    recipients = []
    for name in req.recipients:
        pub_pem = ks.load_public(name, "rsa")
        priv = asy.rsa_load_private(ks.load_private(name, "rsa", req.passphrase.encode()), req.passphrase.encode())
        pub = priv.public_key()
        key_ct = asy.rsa_encrypt(pub, key)
        recipients.append(RecipientEntry(name=name, key_ct_b64=b64e(key_ct)))
    header = EnvelopeHeader(version=FORMAT_VERSION, alg="AES-256-GCM", keywrap="RSA-OAEP", recipients=recipients, chunk_bytes=req.chunk_bytes)
    data = await file.read()
    
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import os, io
    aes = AESGCM(key)
    buf = io.BytesIO()
    buf.write(header.to_bytes())
    #* naive one-chunk for demo, clients should stream for big files
    nonce = os.urandom(12)
    buf.write(nonce + aes.encrypt(nonce, data, None))
    buf.seek(0)
    return {"filename": file.filename + ".dgc", "content_b64": b64e(buf.read())}
