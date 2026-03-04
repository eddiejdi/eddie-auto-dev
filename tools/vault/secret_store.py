#!/usr/bin/env python3
"""Secrets helper with Bitwarden (`bw` CLI) as primary source.

Resolution order:
    1. Bitwarden via `bw` CLI (com auto-unlock via BW_MASTER_PASSWORD ou cache)
    2. Environment variable (uppercased, slashes -> underscores)
    3. `tools/simple_vault/secrets/{name}.gpg` decrypted with
         `SIMPLE_VAULT_PASSPHRASE_FILE` or plain-text `.txt` sibling file

CLI usage: `python tools/vault/secret_store.py get <item> [field]`
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("secret_store")

# Caminho do cache de sessão (mesmo usado pelo Secrets Agent)
BW_SESSION_CACHE = Path(
    os.environ.get("SECRETS_AGENT_DATA", "/var/lib/eddie/secrets_agent")
) / "bw_session.cache"

BW_PASSWORD_FILE = Path(
    os.environ.get("BW_PASSWORD_FILE", str(BW_SESSION_CACHE.parent / ".bw_master_password"))
)


class VaultError(Exception):
    pass


def _try_bw_unlock() -> bool:
    """Tenta unlock do Bitwarden usando BW_MASTER_PASSWORD ou BW_PASSWORD_FILE.

    Em caso de sucesso, seta BW_SESSION no env e salva no cache em disco.
    Retorna False se credenciais não estão disponíveis ou unlock falhou.
    """
    master = os.environ.get("BW_MASTER_PASSWORD")
    if not master and BW_PASSWORD_FILE.exists():
        try:
            master = BW_PASSWORD_FILE.read_text().strip()
        except OSError:
            pass
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
            # Salvar no cache compartilhado
            try:
                BW_SESSION_CACHE.parent.mkdir(parents=True, exist_ok=True)
                BW_SESSION_CACHE.write_text(session)
                BW_SESSION_CACHE.chmod(0o600)
            except OSError:
                pass
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return False


def _check_bw_session():
    """Verifica se há sessão BW válida. Tenta cache, env, status e auto-unlock.

    Retorna True quando BW_SESSION está pronta para uso.
    """
    # 1) env var já setada
    if os.environ.get("BW_SESSION"):
        return True
    # 2) cache em disco (compartilhado com Secrets Agent)
    if BW_SESSION_CACHE.exists():
        try:
            cached = BW_SESSION_CACHE.read_text().strip()
            if cached and cached != "notset":
                os.environ["BW_SESSION"] = cached
                return True
        except OSError:
            pass
    # 3) bw status reporta unlocked?
    try:
        p = subprocess.run(["bw", "status"], capture_output=True, text=True, timeout=15)
        out = (p.stdout or "") + (p.stderr or "")
        if "unlocked" in out.lower():
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    # 4) auto-unlock via master password
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
