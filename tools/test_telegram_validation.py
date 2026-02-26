#!/usr/bin/env python3
"""Test runner isolado para validação do token em `telegram_bot.py`.

Este script executa três testes em subprocessos distintos para evitar
interferência de stubs no processo atual:

- token vazio (falso) -> espera SystemExit
- token mal formatado (falso) -> espera SystemExit
- token real via `tools.secrets_loader` (end-to-end) -> observa resultado

Observação: não imprime o token real; mostra apenas status/saídas.
"""
import sys
import os
import tempfile
import textwrap
import subprocess
from pathlib import Path

VENV_PY = str(Path(__file__).resolve().parents[1] / ".venv" / "bin" / "python3")
if not Path(VENV_PY).exists():
    VENV_PY = sys.executable


def run_subprocess(code: str, extra_env: dict | None = None):
    """Executa um código Python em subprocesso e retorna saída (stdout+stderr) e returncode."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        fname = f.name
    try:
        # Garantir que o repo root esteja em PYTHONPATH no subprocesso
        repo_root = str(Path(__file__).resolve().parents[1])
        env = dict(**os.environ)
        env_pythonpath = env.get('PYTHONPATH', '')
        if repo_root not in env_pythonpath.split(os.pathsep):
            env['PYTHONPATH'] = repo_root + (os.pathsep + env_pythonpath if env_pythonpath else '')

        if extra_env:
            env.update(extra_env)

        proc = subprocess.run([VENV_PY, fname], capture_output=True, text=True, timeout=30, env=env)
        out = proc.stdout + proc.stderr
        return proc.returncode, out
    finally:
        Path(fname).unlink(missing_ok=True)


def make_fake_import_code(token_value: str, httpx_ok: bool) -> str:
    """Gera código que injeta fakes para `tools.secrets_loader` e `httpx`, depois importa `telegram_bot`."""
    return textwrap.dedent(f"""
    import sys, types
    # fake secrets_loader
    fake_secrets = types.ModuleType('tools.secrets_loader')
    def get_telegram_token():
        return {token_value!r}
    fake_secrets.get_telegram_token = get_telegram_token
    sys.modules['tools.secrets_loader'] = fake_secrets

    # Note: do not fake httpx here; we skip validation via env var for fake tests

    # Ensure repo on path
    from pathlib import Path
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    try:
        import telegram_bot
        print('IMPORT_OK')
    except SystemExit as e:
        print('SYSTEMEXIT', e.code)
    except Exception as e:
        import traceback
        print('EXCEPTION', type(e).__name__, str(e))

    """)


def test_fake_empty_token():
    code = make_fake_import_code('', httpx_ok=False)
    rc, out = run_subprocess(code, extra_env={'TELEGRAM_SKIP_VALIDATION': '1'})
    print('\n--- Test: token vazio (fake) ---')
    print('returncode=', rc)
    print(out)


def test_fake_bad_token():
    code = make_fake_import_code('badtoken', httpx_ok=False)
    rc, out = run_subprocess(code, extra_env={'TELEGRAM_SKIP_VALIDATION': '1'})
    print('\n--- Test: token mal formatado (fake) ---')
    print('returncode=', rc)
    print(out)


def test_real_token_from_secrets():
    # Roda em subprocesso para evitar que o processo atual seja encerrado
    code = textwrap.dedent('''
    from pathlib import Path
    import sys
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        # Obtém token via secrets loader
        from tools.secrets_loader import get_telegram_token
        token = get_telegram_token()
        ok = bool(token)
        masked = (token[:6] + '...') if ok else '<empty>'
        print('TOKEN_PRESENT', masked)
    except Exception as e:
        print('TOKEN_FETCH_ERROR', type(e).__name__, str(e))
    # Agora importa telegram_bot (isso executa validação getMe)
    try:
        import telegram_bot
        print('IMPORT_OK')
    except SystemExit as e:
        print('SYSTEMEXIT', e.code)
    except Exception as e:
        import traceback
        print('EXCEPTION', type(e).__name__, str(e))
    ''')
    rc, out = run_subprocess(code)
    print('\n--- Test: token real via Secrets Agent ---')
    print('returncode=', rc)
    print(out)


if __name__ == '__main__':
    test_fake_empty_token()
    test_fake_bad_token()
    test_real_token_from_secrets()

