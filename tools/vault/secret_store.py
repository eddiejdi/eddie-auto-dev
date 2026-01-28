#!/usr/bin/env python3
"""Simple secrets helper that uses repo-local `simple_vault` as the
primary secret store and environment variables as a convenience fallback.

This project removed Vaultwarden/Bitwarden dependence; the module no
longer requires `bw` or `BW_SESSION`. It will try the following, in
order:
    1. Environment variable (uppercased, slashes -> underscores)
    2. `tools/simple_vault/secrets/{name}.gpg` decrypted with
         `SIMPLE_VAULT_PASSPHRASE_FILE` or plain-text `.txt` sibling file

The CLI remains for compatibility: `python tools/vault/secret_store.py get <item>`.
"""
import json
import os
import subprocess
import sys
from typing import Optional


class VaultError(Exception):
    pass


def _check_bw_session():
    # Bitwarden removed from project; do not attempt bw session.
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
    """Fetch password field.

    Deprecated for this repo; kept for CLI compatibility. This will
    always defer to simple_vault or environment variables.
    """
    return None


def get_field(name: str, field: str = "password") -> str:
    """Get `field` of item `name`.

    Behavior:
      - If an environment variable exists for the secret, return it. The
        env var name is the item name uppercased with `/` -> `_`.
      - Otherwise attempt to read from `tools/simple_vault/secrets` via
        `_try_simple_gpg_fallback`.
      - Raises `VaultError` if not found.
    """
    # 1) environment variable fallback
    env_name = name.replace('/', '_').upper()
    if field and field != 'password':
        env_name = f"{env_name}_{field.upper()}"
    v = os.environ.get(env_name)
    if v:
        return v

    # 2) simple_vault GPG/plaintext files
    fv = _try_simple_gpg_fallback(name, field)
    if fv is not None:
        return fv

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
