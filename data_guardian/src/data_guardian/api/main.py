from fastapi import FastAPI, UploadFile, HTTPException

from pydantic import BaseModel
from typing import List
import io
import json

from data_guardian.crypto.asymmetric import RsaKeyPair, sign as ed_sign
from data_guardian.crypto.symmetric import AesGcm
from data_guardian.storage.keystore import KeyStore
from data_guardian.models import Recipient, DgdHeader
from data_guardian.utils import b64e, b64d, sha256_file
from data_guardian.policy.policy import enforce, OperationContext

app = FastAPI(title="Data Guardian API", version="4.0.0")


class EncryptRequest(BaseModel):
    recipients: List[str]  # list of RSA key ids (kid)
    # Optional legacy parameter; not required to fetch public keys
    passphrase: str | None = None


@app.post("/encrypt")
async def encrypt_api(file: UploadFile, req: EncryptRequest):
    enforce(
        OperationContext(op="encrypt", actor=None, details={"recipients": req.recipients})
    )
    ks = KeyStore()

    data = await file.read()
    session_key = AesGcm.gen_key()
    nonce = AesGcm.gen_nonce()
    aes = AesGcm(session_key)
    ct = aes.encrypt(nonce, data, None)

    recips: List[Recipient] = []
    from cryptography.hazmat.primitives import serialization
    for kid in req.recipients:
        pub_pem = ks.load_public_key(kid)
        wrapped = RsaKeyPair(public=serialization.load_pem_public_key(pub_pem)).wrap_key(
            session_key
        )
        recips.append(Recipient(kid=kid, ek_b64=b64e(wrapped)))

    header = DgdHeader(
        v=1,
        alg="AES-256-GCM",
        enc="RSA-OAEP",
        nonce_b64=b64e(nonce),
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
async def decrypt_api(file: UploadFile, req: DecryptRequest):
    enforce(OperationContext(op="decrypt", actor=None, details={}))
    ks = KeyStore()
    raw = await file.read()
    sep = raw.find(b"\n\n")
    if sep < 0:
        raise HTTPException(400, "Malformed payload: header separator not found")
    header = json.loads(raw[:sep].decode("utf-8"))
    body = raw[sep + 2 :]

    # Try each recipient with provided passphrase
    session_key = None
    from cryptography.hazmat.primitives import serialization

    for r in header.get("recipients", []):
        kid = r["kid"]
        try:
            priv = ks.load_private_key_with_passphrase(kid, req.passphrase.encode())
            wrapped = b64d(r["ek"])
            session_key = RsaKeyPair(private=priv).unwrap_key(wrapped)
            break
        except Exception:
            continue
    if session_key is None:
        raise HTTPException(403, "No matching key or bad passphrase")

    aes = AesGcm(session_key)
    nonce = b64d(header["nonce"]) if "nonce" in header else b64d(header["nonce_b64"])
    pt = aes.decrypt(nonce, body, None)
    return {"filename": file.filename.replace(".dgd", ""), "content_b64": b64e(pt)}


class SignRequest(BaseModel):
    signer: str  # ed25519 key id
    passphrase: str


@app.post("/sign")
async def sign_api(file: UploadFile, req: SignRequest):
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
async def verify_api(file: UploadFile, req: VerifyRequest):
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
def sha256_api(path: str):
    enforce(OperationContext(op="sha256", actor=None, details={"path": path}))
    return {"path": path, "sha256": sha256_file(path)}


@app.get("/keys/list")
def list_keys():
    ks = KeyStore()
    return {"keys": [k.__dict__ for k in ks.list_keys()]}
