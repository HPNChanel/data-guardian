
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

class DecryptRequest(BaseModel):
    passphrase: str

@app.post("/decrypt")
async def decrypt_api(file: UploadFile, req: DecryptRequest):
    enforce(OperationContext(op="decrypt", actor=None, details={}))
    ks = KeyStore()
    raw = await file.read()
    header_line, ct_payload = raw.split(b"\n", 1)
    header = EnvelopeHeader.from_bytes(header_line)
    key = None
    for r in header.recipients:
        try:
            priv_pem = ks.load_private(r.name, "rsa", req.passphrase.encode())
            priv = asy.rsa_load_private(priv_pem, req.passphrase.encode())
            key = asy.rsa_decrypt(priv, b64d(r.key_ct_b64))
            break
        except Exception:
            continue
    
    if key is None:
        raise HTTPException(403, "No matching key or bad passphrase")
    
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aes = AESGCM(key)
    nonce, ct = ct_payload[:12], ct_payload[12:]
    data = aes.decrypt(nonce, ct, None)
    return {"filename": file.filename.replace(".dgc",""), "content_b64": b64e(data)}

class SignRequest(BaseModel):
    signer: str
    passphrase: str

@app.post("/sign")
async def sign_api(file: UploadFile, req: SignRequest):
    enforce(OperationContext(op="sign", actor=req.signer, details={}))
    ks = KeyStore()
    priv_pem = ks.load_private(req.signer, "ed25519", req.passphrase.encode())
    priv = asy.ed25519_load_private(priv_pem, req.passphrase.encode())
    data = await file.read()
    sig = asy.sign(priv, data)
    return {"sig_b64": b64e(sig)}

class VerifyRequest(BaseModel):
    signer: str
    sig_b64: str
    
@app.post("/verify")
async def verify_api(file: UploadFile, req: VerifyRequest):
    enforce(OperationContext(op="verify", actor=req.signer, details={}))
    from cryptography.hazmat.primitives.asymmetric import ed25519
    ks = KeyStore()
    pub = ks.load_public(req.signer, "ed25519")
    data = await file.read()
    sig = b64d(req.sig_b64)
    try:
        ed25519.Ed25519PublicKey.from_public_bytes(pub).verify(sig, data)
        return {"valid": True}
    except Exception:
        return {"valid": False}

@app.get("/sha256")
def sha256_api(path: str):
    enforce(OperationContext(op="sha256", actor=None, details={"path": path}))
    return {"path": path, "sha256": sha256_file(path)}

@app.get("/keys/list")
def list_keys():
    ks = KeyStore()
    return {"keys": [k.__dict__ for k in ks.list()]}
