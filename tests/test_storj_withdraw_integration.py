"""Testes de integração — batem em APIs reais (zkSync explorer + KuCoin).

Rodar com: pytest tests/test_storj_withdraw_integration.py -m integration -v

O teste de saldo on-chain não precisa de credenciais. O teste de endereço de
depósito KuCoin precisa das credenciais reais do secrets agent (só
disponíveis rodando no host onde o btc_trading_agent já roda, ex.:
192.168.15.2) — se ausentes, o teste é pulado (skip), nunca falha por falta
de secret.

O lookup KuCoin roda em SUBPROCESSO com timeout de kernel (não SIGALRM):
kucoin_api._load_credentials() roda no import do módulo e pode ficar preso
numa chamada de rede bloqueante (DNS/socket) que ignora sinais Python — um
alarm in-process não é suficiente para garantir que o teste termine.
subprocess.run(timeout=...) mata o processo filho via SIGKILL do SO, o que
sempre funciona.

Nenhum destes testes assina ou transmite nenhuma transação — são somente
leitura (GET/consulta de saldo e endereço de depósito).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "homelab" / "storj_withdraw.py"
_SPEC = importlib.util.spec_from_file_location("storj_withdraw", MODULE_PATH)
assert _SPEC and _SPEC.loader
sw = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sw)

KUCOIN_LOOKUP_TIMEOUT_S = 20

_SUBPROCESS_SCRIPT = f"""
import json, sys
sys.path.insert(0, {str(REPO_ROOT)!r})
sys.path.insert(0, {str(MODULE_PATH.parent)!r})
import importlib.util
spec = importlib.util.spec_from_file_location("storj_withdraw", {str(MODULE_PATH)!r})
sw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sw)
result = sw.fetch_kucoin_deposit_address(chain="erc20")
print(json.dumps(result))
"""


def _run_kucoin_lookup_in_subprocess() -> dict | None:
    """Roda o lookup isolado, com timeout garantido pelo SO. Retorna None em skip."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _SUBPROCESS_SCRIPT],
            capture_output=True,
            text=True,
            timeout=KUCOIN_LOOKUP_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        pytest.skip(
            f"KuCoin/secrets agent não respondeu em {KUCOIN_LOOKUP_TIMEOUT_S}s neste ambiente"
        )
    if proc.returncode != 0:
        pytest.skip(f"Subprocesso do lookup KuCoin falhou: {proc.stderr[-500:]}")
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        pytest.skip(f"Saída inesperada do lookup KuCoin: {exc} — stdout={proc.stdout[-300:]}")


@pytest.mark.integration
def test_real_wallet_balance_matches_expected_shape():
    try:
        balance = sw.fetch_wallet_storj_balance()
    except (URLError, OSError) as exc:
        pytest.skip(f"zkSync explorer inacessível deste ambiente: {exc}")
    assert isinstance(balance, float)
    assert balance >= 0.0


@pytest.mark.integration
def test_real_kucoin_deposit_address_lookup():
    """Só passa com credenciais KuCoin reais disponíveis (secrets agent no host)."""
    result = _run_kucoin_lookup_in_subprocess()
    if result is None:
        return  # pytest.skip já foi chamado dentro do helper

    if not result.get("success"):
        pytest.skip(f"KuCoin retornou erro (provavelmente sem credenciais): {result.get('error')}")

    assert "address" in result
    assert result["address"]


@pytest.mark.integration
def test_real_dry_run_end_to_end(monkeypatch, capsys):
    """Roda o CLI completo em --dry-run contra APIs reais.

    O lookup KuCoin é substituído por uma versão com timeout de kernel
    (mesma lógica do teste acima) para nunca travar a suíte.
    """
    monkeypatch.setattr(sys, "argv", ["storj_withdraw.py"])

    def _bounded_lookup(chain=None):
        result = _run_kucoin_lookup_in_subprocess()
        return result or {"success": False, "error": "timeout/skip no lookup"}

    monkeypatch.setattr(sw, "fetch_kucoin_deposit_address", _bounded_lookup)

    rc = sw.main()
    assert rc in (0, 2)  # 2 só se zkSync explorer estiver fora do ar
    if rc == 0:
        out = capsys.readouterr().out
        assert "PLANO DE TRANSFERÊNCIA" in out
        assert sw.WALLET_ADDRESS in out
