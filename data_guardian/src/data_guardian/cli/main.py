import argparse, sys
from pathlib import Path
from data_guardian.crypto import asymmetric as asy, symmetric as sym
from data_guardian.storage.keystore import KeyStore
from data_guardian.services.envelope import EnvelopeHeader, RecipientEntry, FORMAT_VERSION
from data_guardian.services import key_lifecycle as kl
from data_guardian.audit.logger import log
from data_guardian.utils import sha256_file, b64e, b64d

def cmd_encrypt_multi(args):
    ks = KeyStore()
    key = sym.gen_key()
    recipients = []
    for name in args.recipients:
        pub_pem = ks.load_public(name, "rsa")
        priv = asy.rsa_load_private(ks.load_private(name, "rsa", args.passphrase.encode()), args.passphrase.encode())
        pub = priv.public_key()
        key_ct = asy.rsa_encrypt(pub, key)
        recipients.append(RecipientEntry(name=name, key_ct_b64=b64e(key_ct)))

    header = EnvelopeHeader(version=FORMAT_VERSION, alg="AES-256-GCM", keywrap="RSA-OAEP", recipients=recipients, chunk_bytes=args.chunk_bytes)
    with open(args.outfile, "wb") as fout:
        fout.write(header.to_bytes())
        # streaming frames
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aes = AESGCM(key)
        with open(args.infile, "rb") as fin:
            while True:
                chunk = fin.read(args.chunk_bytes)
                if not chunk:
                    break
                import os
                nonce = os.urandom(12)
                fout.write(nonce + aes.encrypt(nonce, chunk, None))
    log("encrypt_multi", infile=args.infile, outfile=args.outfile, recipients=args.recipients)

def cmd_decrypt(args):
    ks = KeyStore()
    with open(args.infile, "rb") as fin:
        header = EnvelopeHeader.from_bytes(fin.readline())
        # find a key we own
        key = None
        for r in header.recipients:
            try:
                priv_pem = ks.load_private(r.name, "rsa", args.passphrase.encode())
                priv = asy.rsa_load_private(priv_pem, args.passphrase.encode())
                key = asy.rsa_decrypt(priv, b64d(r.key_ct_b64))
                break
            except Exception:
                continue
        if key is None:
            raise SystemExit("No matching recipient key found or wrong passphrase.")
        # stream decrypt
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aes = AESGCM(key)
        with open(args.outfile, "wb") as fout:
            while True:
                nonce = fin.read(12)
                if not nonce:
                    break
                ct = fin.read(header.chunk_bytes + 16)
                pt = aes.decrypt(nonce, ct, None)
                fout.write(pt)
    log("decrypt", infile=args.infile, outfile=args.outfile)

def cmd_export(args):
    data = kl.export_key(args.name, args.kind, args.passphrase.encode())
    Path(args.outfile).write_bytes(data)
    print(f"Exported -> {args.outfile}")

def cmd_import(args):
    data = Path(args.infile).read_bytes()
    kl.import_key(args.name, args.kind, data, args.passphrase.encode())
    print(f"Imported {args.name} ({args.kind})")

def cmd_rotate(args):
    kl.rotate_key(args.name, args.kind, args.passphrase.encode())
    print(f"Rotated {args.name} ({args.kind})")

def cmd_revoke(args):
    kl.revoke_key(args.name, args.kind)
    print(f"Revoked {args.name} ({args.kind})")

def main(argv=None):
    p = argparse.ArgumentParser(prog="data-guardian")
    sub = p.add_subparsers(dest="cmd", required=True)

    em = sub.add_parser("encrypt-multi")
    em.add_argument("--in", dest="infile", required=True)
    em.add_argument("--out", dest="outfile", required=True)
    em.add_argument("--recipients", nargs="+", required=True)
    em.add_argument("--passphrase", required=True)
    em.add_argument("--chunk-bytes", type=int, default=1024*1024)
    em.set_defaults(func=cmd_encrypt_multi)

    dd = sub.add_parser("decrypt")
    dd.add_argument("--in", dest="infile", required=True)
    dd.add_argument("--out", dest="outfile", required=True)
    dd.add_argument("--passphrase", required=True)
    dd.set_defaults(func=cmd_decrypt)

    ex = sub.add_parser("export-key")
    ex.add_argument("--name", required=True)
    ex.add_argument("--kind", choices=["rsa","ed25519"], required=True)
    ex.add_argument("--passphrase", required=True)
    ex.add_argument("--out", dest="outfile", required=True)
    ex.set_defaults(func=cmd_export)

    im = sub.add_parser("import-key")
    im.add_argument("--name", required=True)
    im.add_argument("--kind", choices=["rsa","ed25519"], required=True)
    im.add_argument("--passphrase", required=True)
    im.add_argument("--in", dest="infile", required=True)
    im.set_defaults(func=cmd_import)

    ro = sub.add_parser("rotate-key")
    ro.add_argument("--name", required=True)
    ro.add_argument("--kind", choices=["rsa","ed25519"], required=True)
    ro.add_argument("--passphrase", required=True)
    ro.set_defaults(func=cmd_rotate)

    rv = sub.add_parser("revoke-key")
    rv.add_argument("--name", required=True)
    rv.add_argument("--kind", choices=["rsa","ed25519"], required=True)
    rv.set_defaults(func=cmd_revoke)

    args = p.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    main()
