#!/usr/bin/env python3
"""Simple Bitwarden/Vaultwarden wrapper using the `bw` CLI.

Provides a small programmatic API to fetch secrets from a Bitwarden-compatible vault.

Usage (CLI):
  python tools/vault/secret_store.py get <item_name> [field]

Examples:
  python tools/vault/secret_store.py get eddie/github_token
  python tools/vault/secret_store.py get openwebui/api_key password

Notes:
- Requires `bw` CLI installed and an unlocked session (export `BW_SESSION`).
- Set `BW_SERVER` to your Vaultwarden URL if not using bitwarden.com.
"""
import json
import os
import subprocess
import sys
from typing import Optional


class VaultError(Exception):
    pass


def _check_bw_session():
    if os.environ.get("BW_SESSION"):
        return True
    # bw status can show unauthenticated if not logged in
    return False


def get_item_json(name: str) -> dict:
    """Return full item JSON for `name` using `bw get item <name>`.

    Raises VaultError on failure.
    """
    if not _check_bw_session():
        raise VaultError("BW_SESSION not set; login/unlock 'bw' first")
    try:
        p = subprocess.run(["bw", "get", "item", name], capture_output=True, text=True, check=True)
        return json.loads(p.stdout)
    except subprocess.CalledProcessError as e:
        raise VaultError(f"bw failed: {e.stderr.strip()}")


def get_password(name: str) -> Optional[str]:
    """Try to fetch only the password field for a named item."""
    if not _check_bw_session():
        raise VaultError("BW_SESSION not set; login/unlock 'bw' first")
    try:
        p = subprocess.run(["bw", "get", "password", name], capture_output=True, text=True, check=True)
        return p.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_field(name: str, field: str = "password") -> str:
    """Get `field` of item `name`. If `field` == 'password' tries shortcut, else parses item JSON."""
    if field == "password":
        pw = get_password(name)
        if pw:
            return pw
    data = get_item_json(name)
    if field == "notes":
        return data.get("notes", "")
    # look in fields
    for f in data.get("fields", []):
        if f.get("name") == field or f.get("type") == field:
            return f.get("value", "")
    # also try login.username/login.password
    login = data.get("login", {})
    if field in login:
        return login.get(field, "")
    # Fallback to a simple file-based vault (GPG-encrypted files) if BW_SESSION
    # is not available. This allows using `tools/simple_vault` scripts to store
    # secrets encrypted with GPG when a Bitwarden-compatible server is not used.
    try:
        fv = _try_simple_gpg_fallback(name, field)
        if fv is not None:
            return fv
    except Exception:
        pass

    raise VaultError(f"field '{field}' not found in item '{name}'")


def _try_simple_gpg_fallback(name: str, field: str = "password") -> Optional[str]:
    """Attempt to read a GPG-encrypted secret file from tools/simple_vault/secrets.

    The expected filename is `tools/simple_vault/secrets/{name_with_underscores}.gpg`.
    A passphrase file must be pointed to by `SIMPLE_VAULT_PASSPHRASE_FILE` env var.
    Returns the decrypted string on success, or None if no fallback file exists.
    """
    import tempfile

    # map item name to filename, e.g. openwebui/api_key -> openwebui_api_key.gpg
    fname = name.replace("/", "_") + ".gpg"
    base = os.path.join(os.path.dirname(__file__), "..", "simple_vault", "secrets")
    base = os.path.normpath(base)
    path = os.path.join(base, fname)
    passfile = os.environ.get("SIMPLE_VAULT_PASSPHRASE_FILE")
    # default to repo-local passphrase file if present
    if not passfile:
        default_pass = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "simple_vault", "passphrase"))
        if os.path.isfile(default_pass):
            passfile = default_pass
    # Prefer GPG-encrypted file if present
    if os.path.isfile(path) and passfile and os.path.isfile(passfile):
        with tempfile.NamedTemporaryFile(prefix="sv_decrypt_", delete=False) as tf:
            tmpout = tf.name
        try:
            p = subprocess.run([
                "gpg", "--quiet", "--batch", "--yes",
                "--passphrase-file", passfile,
                "-o", tmpout, "-d", path
            ], capture_output=True, text=True)
            if p.returncode == 0 and os.path.isfile(tmpout):
                with open(tmpout, "r") as f:
                    return f.read().strip()
        finally:
            try:
                os.unlink(tmpout)
            except Exception:
                pass

    # Fallback: allow plain-text files in the simple_vault (repo-local .txt)
    txt_path = os.path.splitext(path)[0] + ".txt"
    if os.path.isfile(txt_path):
        try:
            with open(txt_path, "r") as f:
                return f.read().strip()
        except Exception:
            return None

    return None


def cli_main():
    if len(sys.argv) < 3:
        print("usage: secret_store.py get <item_name> [field]", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd != "get":
        print("only 'get' supported", file=sys.stderr)
        sys.exit(2)
    item = sys.argv[2]
    field = sys.argv[3] if len(sys.argv) > 3 else "password"
    try:
        v = get_field(item, field)
    except VaultError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(v)


if __name__ == "__main__":
    cli_main()
