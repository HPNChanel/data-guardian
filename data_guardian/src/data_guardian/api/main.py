from fastapi import FastAPI, UploadFile, HTTPException, Depends, Header, Response

from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import io
import json
import os
import time
import jwt

from data_guardian.crypto.asymmetric import RsaKeyPair, sign as ed_sign
from data_guardian.crypto.symmetric import aead_factory, gen_key_for, gen_nonce_for
from data_guardian.crypto.ecc import X25519KeyPair, X25519EphemeralWrap
from data_guardian.storage.keystore import KeyStore
from data_guardian.models import Recipient, DgdHeader
from data_guardian.utils import b64e, b64d, sha256_file
from data_guardian.policy.policy import enforce, OperationContext
from data_guardian.config import CONFIG
from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest

app = FastAPI(title="Data Guardian API", version="4.1.0")


# ---- Metrics ----
REQS = Counter("dg_requests_total", "Total API requests", ["path", "method"])
LAT = Histogram("dg_request_seconds", "Request latency", ["path", "method"])


def _jwt_secret() -> str:
    return os.getenv("DG_JWT_SECRET", "dev-secret-change-me")


def auth_dependency(authorization: Optional[str] = Header(default=None)):
    if not authorization:
        raise HTTPException(401, "Missing Authorization header")
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise ValueError("bad scheme")
        payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


class EncryptRequest(BaseModel):
    recipients: List[str]  # list of key ids (kid)
    enc: str = "RSA-OAEP"  # or X25519-KEM
    aead: str | None = None  # AESGCM | CHACHA20
    oaep_hash: str | None = None


@app.post("/encrypt")
async def encrypt_api(file: UploadFile, req: EncryptRequest, _user=Depends(auth_dependency)):
    with LAT.labels("/encrypt", "POST").time():
        REQS.labels("/encrypt", "POST").inc()
        enforce(OperationContext(op="encrypt", actor=None, details={"recipients": req.recipients}))
        ks = KeyStore()

        data = await file.read()
        aead = (req.aead or CONFIG.crypto.aead).upper()
        enc = req.enc
        oaep = (req.oaep_hash or CONFIG.crypto.rsa_oaep_hash).upper()

        cek = gen_key_for(aead)
        nonce = gen_nonce_for(aead)
        a = aead_factory(aead, cek)
        ct = a.encrypt(nonce, data, None)

        recips: List[Recipient] = []
        from cryptography.hazmat.primitives import serialization
        if enc == "RSA-OAEP":
            for kid in req.recipients:
                pub_pem = ks.load_public_key(kid)
                wrapped = RsaKeyPair(public=serialization.load_pem_public_key(pub_pem)).wrap_key(cek, oaep_hash=oaep)  # type: ignore[arg-type]
                recips.append(Recipient(kid=kid, ek_b64=b64e(wrapped), scheme="RSA-OAEP"))
        elif enc == "X25519-KEM":
            for kid in req.recipients:
                pub_pem = ks.load_public_key(kid)
                wrap = X25519KeyPair.wrap_cek_for_recipient(
                    serialization.load_pem_public_key(pub_pem), cek, aead=aead  # type: ignore[arg-type]
                )
                recips.append(
                    Recipient(kid=kid, ek_b64=b64e(wrap.ct), epk_pem_b64=b64e(wrap.epk_pem), nonce_b64=b64e(wrap.nonce), scheme="X25519-KEM")
                )
        else:
            raise HTTPException(400, f"Unsupported enc: {enc}")

        header = DgdHeader(
            v=1,
            aead=aead,
            enc=enc,
            content_nonce_b64=b64e(nonce),
            recipients=recips,
            chunk=False,
        )
        buf = io.BytesIO()
        buf.write((header.to_json() + "\n\n").encode("utf-8"))
        buf.write(ct)
        buf.seek(0)
        return {"filename": file.filename + ".dgd", "content_b64": b64e(buf.read())}


class DecryptRequest(BaseModel):
    passphrase: str


@app.post("/decrypt")
async def decrypt_api(file: UploadFile, req: DecryptRequest, _user=Depends(auth_dependency)):
    with LAT.labels("/decrypt", "POST").time():
        REQS.labels("/decrypt", "POST").inc()
        enforce(OperationContext(op="decrypt", actor=None, details={}))
        ks = KeyStore()
        raw = await file.read()
        sep = raw.find(b"\n\n")
        if sep < 0:
            raise HTTPException(400, "Malformed payload: header separator not found")
        header = json.loads(raw[:sep].decode("utf-8"))
        body = raw[sep + 2 :]

        cek = None
        from cryptography.hazmat.primitives import serialization
        aead = header.get("aead", CONFIG.crypto.aead)
        enc = header.get("enc", "RSA-OAEP")
        content_nonce = b64d(header.get("nonce") or header.get("content_nonce_b64"))
        if enc == "RSA-OAEP":
            for r in header.get("recipients", []):
                kid = r["kid"]
                try:
                    priv = ks.load_private_key_with_passphrase(kid, req.passphrase.encode())
                    wrapped = b64d(r["ek"]) if "ek" in r else b64d(r["ek_b64"])
                    cek = RsaKeyPair(private=priv).unwrap_key(wrapped)
                    break
                except Exception:
                    continue
        elif enc == "X25519-KEM":
            for r in header.get("recipients", []):
                kid = r["kid"]
                try:
                    priv = ks.load_private_key_with_passphrase(kid, req.passphrase.encode())
                    wrap = X25519EphemeralWrap(
                        epk_pem=b64d(r["epk_pem_b64"]),
                        ct=b64d(r["ek"]) if "ek" in r else b64d(r["ek_b64"]),
                        nonce=b64d(r.get("nonce") or r.get("nonce_b64")),
                        aead=aead,
                    )
                    cek = X25519KeyPair.unwrap_cek(priv, wrap)
                    break
                except Exception:
                    continue
        else:
            raise HTTPException(400, f"Unsupported enc: {enc}")

        if cek is None:
            raise HTTPException(403, "No matching key or bad passphrase")

        a = aead_factory(aead, cek)
        pt = a.decrypt(content_nonce, body, None)
        return {"filename": file.filename.replace(".dgd", ""), "content_b64": b64e(pt)}


class SignRequest(BaseModel):
    signer: str  # ed25519 key id
    passphrase: str


@app.post("/sign")
async def sign_api(file: UploadFile, req: SignRequest, _user=Depends(auth_dependency)):
    enforce(OperationContext(op="sign", actor=req.signer, details={}))
    ks = KeyStore()
    priv = ks.load_private_key_with_passphrase(req.signer, req.passphrase.encode())
    data = await file.read()
    sig = ed_sign(priv, data)
    return {"sig_b64": b64e(sig)}


class VerifyRequest(BaseModel):
    signer: str
    sig_b64: str


@app.post("/verify")
async def verify_api(file: UploadFile, req: VerifyRequest, _user=Depends(auth_dependency)):
    enforce(OperationContext(op="verify", actor=req.signer, details={}))
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization

    ks = KeyStore()
    pub_pem = ks.load_public_key(req.signer)
    pub = serialization.load_pem_public_key(pub_pem)
    data = await file.read()
    sig = b64d(req.sig_b64)
    try:
        assert isinstance(pub, ed25519.Ed25519PublicKey)
        pub.verify(sig, data)
        return {"valid": True}
    except Exception:
        return {"valid": False}


@app.get("/sha256")
def sha256_api(path: str, _user=Depends(auth_dependency)):
    enforce(OperationContext(op="sha256", actor=None, details={"path": path}))
    return {"path": path, "sha256": sha256_file(path)}


@app.get("/keys/list")
def list_keys(_user=Depends(auth_dependency)):
    ks = KeyStore()
    return {"keys": [k.__dict__ for k in ks.list_keys()]}


@app.get("/healthz")
def healthz():
    return {"status": "ok", "ts": int(time.time())}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class StreamEncryptRequest(BaseModel):
    recipients: List[str]
    enc: str = "RSA-OAEP"
    aead: Optional[str] = None
    oaep_hash: Optional[str] = None
    chunk_size: int = 1024 * 1024


@app.post("/encrypt/stream")
async def encrypt_stream_api(file: UploadFile, req: StreamEncryptRequest, _user=Depends(auth_dependency)):
    # For demo, buffer in-memory then stream format
    from data_guardian.services.stream import StreamEncryptor
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "in.bin")
        outp = os.path.join(td, "out.dgd")
        with open(inp, "wb") as f:
            f.write(await file.read())
        StreamEncryptor().encrypt_file(Path(inp), Path(outp), req.recipients, enc=req.enc, aead=req.aead, oaep_hash=req.oaep_hash, chunk_size=req.chunk_size)
        return {"filename": file.filename + ".dgd", "content_b64": b64e(open(outp, 'rb').read())}


@app.post("/decrypt/stream")
async def decrypt_stream_api(file: UploadFile, _user=Depends(auth_dependency)):
    from data_guardian.services.stream import StreamDecryptor
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "in.dgd")
        outp = os.path.join(td, "out.bin")
        with open(inp, "wb") as f:
            f.write(await file.read())
        StreamDecryptor().decrypt_file(Path(inp), Path(outp))
        return {"filename": file.filename.replace('.dgd',''), "content_b64": b64e(open(outp, 'rb').read())}
