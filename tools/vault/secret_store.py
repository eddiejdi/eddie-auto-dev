#!/usr/bin/env python3
"""Secrets helper with Bitwarden (`bw` CLI) as primary source.

Resolution order:
    1. Bitwarden via `bw` CLI (requires `BW_SESSION` or unlocked vault)
    2. Environment variable (uppercased, slashes -> underscores)
    3. `tools/simple_vault/secrets/{name}.gpg` decrypted with
         `SIMPLE_VAULT_PASSPHRASE_FILE` or plain-text `.txt` sibling file

CLI usage: `python tools/vault/secret_store.py get <item> [field]`
"""
import json
import os
import subprocess
import sys
from typing import Optional


class VaultError(Exception):
    pass


def _try_bw_unlock() -> bool:
    """Attempt to unlock the Bitwarden vault using BW_MASTER_PASSWORD.

    On success, sets BW_SESSION in the current process environment and
    returns True.  Returns False when the password env var is missing or
    the unlock command fails.
    """
    master = os.environ.get("BW_MASTER_PASSWORD")
    if not master:
        return False
    try:
        p = subprocess.run(
            ["bw", "unlock", "--raw"],
            input=master,
            capture_output=True,
            text=True,
            timeout=30,
        )
        session = (p.stdout or "").strip()
        if p.returncode == 0 and session:
            os.environ["BW_SESSION"] = session
            return True
    except Exception:
        pass
    return False


def _check_bw_session():
    # Prefer Bitwarden if available and unlocked. Return True when a usable
    # BW_SESSION is present or the `bw` CLI reports unlocked status.
    if os.environ.get("BW_SESSION"):
        return True
    try:
        p = subprocess.run(["bw", "status"], capture_output=True, text=True)
        out = (p.stdout or "") + (p.stderr or "")
        if "unlocked" in out.lower():
            return True
    except Exception:
        pass
    # Vault is locked — try auto-unlock via BW_MASTER_PASSWORD
    return _try_bw_unlock()


def get_item_json(name: str) -> dict:
    """Return full item JSON for `name` using `bw get item <name>`.

    Raises VaultError on failure.
    """
    # Try to fetch via bw if available
    if _check_bw_session():
        cmd = ["bw", "get", "item", name]
        # include session if present
        sess = os.environ.get("BW_SESSION")
        if sess:
            cmd += ["--session", sess]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(p.stdout)
        except subprocess.CalledProcessError as e:
            # fall through to other fallbacks
            raise VaultError(f"bw failed: {e.stderr.strip()}")
        except Exception as e:
            raise VaultError(f"bw returned invalid JSON: {e}")
    raise VaultError("BW_SESSION not set and bw CLI unavailable/unlocked")


def get_password(name: str) -> Optional[str]:
    """Fetch password field for item `name`.

    Tries Bitwarden first, then env vars, then simple_vault.
    Returns None only if the secret is not found anywhere.
    """
    try:
        return get_field(name, "password")
    except VaultError:
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
    # 1) Try Bitwarden item if available
    if _check_bw_session():
        try:
            item = get_item_json(name)
            # login.password for login items
            if field == 'password':
                pw = item.get('login', {}).get('password')
                if pw:
                    return pw
            # custom fields array
            for f in item.get('fields', []) or []:
                # Bitwarden fields may have 'name' and 'value'
                if f.get('name', '').lower() == field.lower():
                    return f.get('value')
            # try notes
            if field in (None, 'notes'):
                notes = item.get('notes')
                if notes:
                    return notes
            # if requesting a named field different from 'password', also try login.<field>
            lf = item.get('login', {}).get(field)
            if lf:
                return lf
        except VaultError:
            # fall back to env/simple_vault
            pass

    # 2) environment variable fallback
    env_name = name.replace('/', '_').upper()
    if field and field != 'password':
        env_name = f"{env_name}_{field.upper()}"
    v = os.environ.get(env_name)
    if v:
        return v

    # 3) simple_vault GPG/plaintext files
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
