# CLI implementation using Typer for commands like keygen, list, encrypt, decrypt, etc.
from __future__ import annotations
from pathlib import Path
import typer
from .services.key_manager import KeyManager
from .services.encryptor import HybridEncryptor
from .services.decryptor import HybridDecryptor
from .services.signer_service import SignerService
from .crypto.hasher import sha256_file


app = typer.Typer(help="Data Guardian CLI")

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
def keygen_rsa(label: str = typer.Option("", help="Pick a label to remember easily")):
    """Create key-pairs RSA-3072 (encrypt session key)"""
    kid = KeyManager().create_rsa(label)
    typer.echo(f"Created {kid}")

@app.command("keygen-ed25519")
def keygen_ed25519(label: str = typer.Option("", help="Pick a label to remember easily")):
    """Create key-pairs Ed25519 (sign/verify)"""
    kid = KeyManager().create_ed25519(label)
    typer.echo(f"Created {kid}")

@app.command("encrypt")
def encrypt(
    input: Path = typer.Option(..., "-i", exists=True, readable=True, help="Input File"),
    output: Path = typer.Option(..., "-o", help="Output File (.dgd)"),
    kid: str = typer.Option(..., "--kid", help="RSA key id (rsa_*)"),
):
    """Encrypt file: AES-256-GCM + wrap session key using RSA-OAEP"""
    HybridEncryptor().encrypt_file(input, output, kid)
    typer.echo(f"Encrypted -> {output}")

@app.command("decrypt")
def decrypt(
    input: Path = typer.Option(..., "-i", exists=True, readable=True, help="File .dgd"),
    output: Path = typer.Option(..., "-o", help="Decrypted File"),
):
    """Decrypt file: .dgd"""
    HybridDecryptor().decrypt_file(input, output)
    typer.echo(f"Decrypted -> {output}")

@app.command("sign")
def sign(
    input: Path = typer.Option(..., "-i", exists=True, readable=True),
    sig: Path = typer.Option(None, "-s", help="Signature Path (default: <input>.sig)"),
    kid: str = typer.Option(..., "--kid", help="Ed25519 key id (ed_*)"),
):
    """Separated Signature (detached)"""
    sig_path = sig or input.with_suffix(input.suffix + ".sig")
    SignerService().sign(input, sig_path, kid)
    typer.echo(f"Signed -> {sig_path} (+ .json)")

@app.command("verify")
def verify(
    input: Path = typer.Option(..., "-i", exists=True, readable=True),
    sig: Path = typer.Option(..., "-s", exists=True, readable=True),
    meta: Path = typer.Option(None, "--meta", help="Meta JSON (default: <sig>.json)"), 
):
    """Verify Separated Signature"""
    ok = SignerService().verify(input, sig, meta)
    typer.echo("Verify OK" if ok else "Verify FAILED")
    raise typer.Exit(code=0 if ok else 2)

@app.command("sha256")
def sha256(input: Path = typer.Option(..., "-i", exists=True, readable=True)):
    """Print the SHA-256 of a file"""
    typer.echo(sha256_file(input))
    