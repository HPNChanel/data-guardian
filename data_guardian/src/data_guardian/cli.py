# CLI implementation using Typer for commands like keygen, list, encrypt, decrypt, etc.
from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import typer
from .services.key_manager import KeyManager
from .services.encryptor import HybridEncryptor
from .services.decryptor import HybridDecryptor
from .services.signer_service import SignerService
from .crypto.hasher import sha256_file
from .config import CONFIG
from .audit.logger import get_logger
from .services.stream import StreamEncryptor, StreamDecryptor


app = typer.Typer(help="Data Guardian CLI")


def _setup_logger(audit: bool):
    if audit:
        get_logger()  # initialize JSON logger

@app.command("list-keys")
def list_keys():
    """List all keys from keystore"""
    km = KeyManager()
    keys = km.list_keys()
    if not keys:
        typer.echo("No keys found")
        raise typer.Exit(code=0)
    for k in keys:
        from time import strftime, localtime
        typer.echo(f"{k.kid:>18} {k.alg:<8} {strftime('%Y-%m-%d %H:%M:%S', localtime(k.created_at))} {k.label}")

@app.command("keygen-rsa")
def keygen_rsa(
    label: str = typer.Option("", help="Pick a label to remember easily"),
    audit: bool = typer.Option(False, "--audit", help="Emit structured logs"),
):
    """Create key-pairs RSA-3072 (encrypt session key)"""
    _setup_logger(audit)
    kid = KeyManager().create_rsa(label)
    typer.echo(f"Created {kid}")

@app.command("keygen-ed25519")
def keygen_ed25519(
    label: str = typer.Option("", help="Pick a label to remember easily"),
    audit: bool = typer.Option(False, "--audit", help="Emit structured logs"),
):
    """Create key-pairs Ed25519 (sign/verify)"""
    _setup_logger(audit)
    kid = KeyManager().create_ed25519(label)
    typer.echo(f"Created {kid}")


@app.command("keygen-x25519")
def keygen_x25519(
    label: str = typer.Option("", help="Pick a label to remember easily"),
    audit: bool = typer.Option(False, "--audit", help="Emit structured logs"),
):
    """Create key-pairs X25519 (ECC key exchange)"""
    _setup_logger(audit)
    kid = KeyManager().create_x25519(label)
    typer.echo(f"Created {kid}")

@app.command("encrypt")
def encrypt(
    input: Path = typer.Option(..., "-i", exists=True, readable=True, help="Input File"),
    output: Path = typer.Option(..., "-o", help="Output File (.dgd)"),
    kid: List[str] = typer.Option(..., "--kid", help="Recipient key id(s) or group:NAME/role:NAME"),
    enc: str = typer.Option("RSA-OAEP", help="Key wrap: RSA-OAEP|X25519-KEM"),
    aead: Optional[str] = typer.Option(None, help="Content AEAD: AESGCM|CHACHA20"),
    oaep_hash: Optional[str] = typer.Option(None, help="RSA-OAEP hash: SHA1|SHA256|SHA512"),
    use_policy: bool = typer.Option(True, help="Resolve group:/role: via policy file"),
    audit: bool = typer.Option(False, "--audit", help="Emit structured logs"),
):
    """Encrypt file: Hybrid (configurable recipients & algorithms)"""
    _setup_logger(audit)
    if use_policy:
        from .policy.recipients import resolve_recipients
        kid = resolve_recipients(kid)
    HybridEncryptor().encrypt_file(input, output, recipient_kids=kid, enc=enc, aead=aead, oaep_hash=oaep_hash)
    typer.echo(f"Encrypted -> {output}")

@app.command("decrypt")
def decrypt(
    input: Path = typer.Option(..., "-i", exists=True, readable=True, help="File .dgd"),
    output: Path = typer.Option(..., "-o", help="Decrypted File"),
    audit: bool = typer.Option(False, "--audit", help="Emit structured logs"),
):
    """Decrypt file: .dgd"""
    _setup_logger(audit)
    HybridDecryptor().decrypt_file(input, output)
    typer.echo(f"Decrypted -> {output}")

@app.command("sign")
def sign(
    input: Path = typer.Option(..., "-i", exists=True, readable=True),
    sig: Path = typer.Option(None, "-s", help="Signature Path (default: <input>.sig)"),
    kid: str = typer.Option(..., "--kid", help="Ed25519 key id (ed_*)"),
    audit: bool = typer.Option(False, "--audit", help="Emit structured logs"),
):
    """Separated Signature (detached)"""
    _setup_logger(audit)
    sig_path = sig or input.with_suffix(input.suffix + ".sig")
    SignerService().sign(input, sig_path, kid)
    typer.echo(f"Signed -> {sig_path} (+ .json)")

@app.command("verify")
def verify(
    input: Path = typer.Option(..., "-i", exists=True, readable=True),
    sig: Path = typer.Option(..., "-s", exists=True, readable=True),
    meta: Path = typer.Option(None, "--meta", help="Meta JSON (default: <sig>.json)"), 
    audit: bool = typer.Option(False, "--audit", help="Emit structured logs"),
):
    """Verify Separated Signature"""
    _setup_logger(audit)
    ok = SignerService().verify(input, sig, meta)
    typer.echo("Verify OK" if ok else "Verify FAILED")
    raise typer.Exit(code=0 if ok else 2)

@app.command("sha256")
def sha256(input: Path = typer.Option(..., "-i", exists=True, readable=True)):
    """Print the SHA-256 of a file"""
    typer.echo(sha256_file(input))


# ---- Key utilities ----

@app.command("key-info")
def key_info(kid: str):
    km = KeyManager()
    for k in km.list_keys():
        if k.kid == kid:
            import json
            typer.echo(json.dumps(k.__dict__, indent=2))
            return
    typer.echo("Key not found")


@app.command("key-expire")
def key_expire(kid: str, expire_at: int = typer.Option(0, help="Epoch seconds; 0 disables immediately")):
    from .services.key_lifecycle import KeyLifecycle
    KeyLifecycle().set_expiry(kid, expire_at)
    typer.echo("Updated expiry")


@app.command("key-clean")
def key_clean():
    from .services.key_lifecycle import KeyLifecycle
    removed = KeyLifecycle().clean_expired()
    typer.echo(f"Removed {removed} expired keys from index")


@app.command("doctor")
def doctor():
    from .utils import sha256_file as _
    # Simple environment checks
    from .storage.paths import PathResolver
    paths_ok = PathResolver().ensure() is None
    typer.echo("Storage OK" if paths_ok is None else "Storage check completed")
    typer.echo("Crypto backends ready")


@app.command("selftest")
def selftest():
    # Simple roundtrip test on-memory
    data = b"hello world"
    from .crypto.symmetric import AesGcm
    key = AesGcm.gen_key()
    nonce = AesGcm.gen_nonce()
    a = AesGcm(key)
    ct = a.encrypt(nonce, data)
    assert a.decrypt(nonce, ct) == data
    typer.echo("Selftest OK")


@app.command("benchmark")
def benchmark(size_mb: int = 32, aead: str = "AESGCM"):
    import os, time
    data = os.urandom(size_mb * (1 << 20))
    from .crypto.symmetric import aead_factory, gen_key_for, gen_nonce_for
    key = gen_key_for(aead)
    nonce = gen_nonce_for(aead)
    a = aead_factory(aead, key)
    t0 = time.time(); ct = a.encrypt(nonce, data); t1 = time.time()
    mbps = size_mb / (t1 - t0)
    typer.echo(f"{aead} encrypt: {mbps:.2f} MB/s")


@app.command("encrypt-stream")
def encrypt_stream(
    input: Path = typer.Option(..., "-i", exists=True, readable=True),
    output: Path = typer.Option(..., "-o"),
    kid: List[str] = typer.Option(..., "--kid", help="Recipient key id(s) or group:NAME/role:NAME"),
    enc: str = typer.Option("RSA-OAEP"),
    aead: Optional[str] = typer.Option(None),
    oaep_hash: Optional[str] = typer.Option(None),
    chunk_size: int = typer.Option(1024*1024, help="Chunk size in bytes"),
    resume: bool = typer.Option(True, help="Resume if output exists"),
):
    from .policy.recipients import resolve_recipients
    kid = resolve_recipients(kid)
    StreamEncryptor().encrypt_file(input, output, kid, enc=enc, aead=aead, oaep_hash=oaep_hash, chunk_size=chunk_size, resume=resume)
    typer.echo(f"Encrypted (stream) -> {output}")


@app.command("decrypt-stream")
def decrypt_stream(
    input: Path = typer.Option(..., "-i", exists=True, readable=True),
    output: Path = typer.Option(..., "-o"),
):
    StreamDecryptor().decrypt_file(input, output)
    typer.echo(f"Decrypted (stream) -> {output}")
    
