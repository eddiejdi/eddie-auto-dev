"""Testes de integração — batem em APIs reais (Storj local + zkSync explorer).

Rodar com: pytest tests/test_storj_payout_monitor_integration.py -m integration -v

Requer:
- Acesso de rede à API local do storagenode (http://127.0.0.1:14002) — só
  funciona rodando no host 192.168.15.2, ou via túnel SSH -L 14002:127.0.0.1:14002.
- Acesso à internet para o block explorer público do zkSync Era.
Não requer nenhuma credencial. Somente leitura.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from urllib.error import URLError

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "homelab" / "storj_payout_monitor.py"
)
_SPEC = importlib.util.spec_from_file_location("storj_payout_monitor", MODULE_PATH)
assert _SPEC and _SPEC.loader
spm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(spm)


@pytest.mark.integration
def test_real_zksync_wallet_balance_is_reachable():
    """Bate no block explorer real e valida o shape da resposta p/ a carteira do nó."""
    try:
        balance = spm.fetch_wallet_storj_balance()
    except (URLError, OSError) as exc:
        pytest.skip(f"zkSync explorer inacessível deste ambiente: {exc}")
    assert isinstance(balance, float)
    assert balance >= 0.0


@pytest.mark.integration
def test_real_storj_price_feed_is_reachable():
    price = spm.fetch_storj_usd_price()
    if price is None:
        pytest.skip("CoinGecko indisponível/rate-limited neste ambiente")
    assert price > 0


@pytest.mark.integration
def test_real_storj_local_api_held_history():
    """Só passa rodando no host do storagenode (ou com túnel SSH -L 14002:...)."""
    try:
        total = spm.fetch_disposed_total()
    except (URLError, OSError) as exc:
        pytest.skip(f"API local do storagenode inacessível deste ambiente: {exc}")
    assert isinstance(total, float)
    assert total >= 0.0


@pytest.mark.integration
def test_real_end_to_end_run_writes_state_and_prom(tmp_path, monkeypatch):
    """Roda main() de ponta a ponta contra APIs reais, sem enviar alerta Telegram."""
    state_file = tmp_path / "state.json"
    prom_file = tmp_path / "metrics.prom"
    monkeypatch.setattr(spm, "STATE_FILE", state_file)
    monkeypatch.setattr(spm, "PROM_FILE", prom_file)
    # Nunca mandar alerta de verdade num teste — mas deixa o resto real.
    sent = []
    monkeypatch.setattr(spm, "send_telegram_alert", lambda msg: sent.append(msg))

    rc = spm.main()

    if rc == 2:
        pytest.skip("API do storagenode inacessível deste ambiente de teste")

    assert rc == 0
    assert state_file.exists()
    assert prom_file.exists()
    prom_content = prom_file.read_text()
    assert "storj_payout_disposed_total" in prom_content
    assert "storj_payout_wallet_balance_storj" in prom_content
