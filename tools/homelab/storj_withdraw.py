#!/usr/bin/env python3
"""Retirada manual de STORJ da carteira do nó para a KuCoin.

# USO MANUAL APENAS — NUNCA referenciar este script em .service/.timer.
#
# Este script NUNCA tem acesso a nenhuma chave privada. A assinatura da(s)
# transação(ões) real(is) é feita à mão pelo operador, no fluxo oficial da
# zkSync Era Bridge (https://portal.zksync.io/bridge), com um hardware
# wallet (Ledger/Trezor) fisicamente conectado — ver
# docs/storj-withdrawal-runbook.md.
#
# O que este script FAZ:
#   1. Lê o saldo STORJ atual na carteira do nó (só leitura, API pública).
#   2. Busca (ou cria) o endereço de depósito STORJ da KuCoin, rede ERC20/L1
#      (reaproveita btc_trading_agent.kucoin_api — precisa das credenciais
#      KuCoin no secrets agent).
#   3. Imprime o PLANO de transferência em duas etapas — bridge L2->L1 e
#      depois transfer ERC20 L1 -> endereço KuCoin — sem executar nada.
#
# O que este script NÃO faz (de propósito):
#   - Não assina nem transmite nenhuma transação on-chain.
#   - Não importa nenhuma lib de hardware wallet no caminho --dry-run
#     (padrão), para não criar dependência de USB nesse modo.
#   - O modo sem --dry-run está deliberadamente NÃO IMPLEMENTADO por ora
#     (levanta NotImplementedError) — construir e assinar a transação real
#     é trabalho futuro, feito manualmente pelo operador via zkSync Portal
#     oficial + hardware wallet, não por este script.

STORJ é um ERC-20 nativo do Ethereum L1 (contrato
0xB64ef51C888972c908CFacf59B47C1AfBC0Ab8aC). O saldo do nó fica representado
no zkSync Era (L2); para chegar numa exchange que só aceita depósito L1
(caso da KuCoin, presumivelmente — confirmar chain exata antes de qualquer
transferência real), o caminho oficial documentado pela Storj é:
  1) Bridge L2 (zkSync Era) -> L1 (Ethereum) via zkSync Era Bridge —
     taxa pode ser paga no próprio STORJ (meta-transação gasless).
  2) Transfer ERC-20 padrão em L1 até o endereço de depósito da exchange.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("storj-withdraw")

WALLET_ADDRESS = "0x4787E8bA11d9D32f8A51336a1844e663105a7d24"
ZKSYNC_EXPLORER_BASE = "https://block-explorer-api.mainnet.zksync.io"
STORJ_L1_CONTRACT = "0xB64ef51C888972c908CFacf59B47C1AfBC0Ab8aC"
KUCOIN_DEPOSIT_CHAIN = "eth"  # chainId real da KuCoin p/ STORJ (chainName exibido é "ERC20")

# Este script roda standalone em /usr/local/bin no host — não dentro do
# checkout do repo — então o diretório de kucoin_api.py precisa ser
# configurável em vez de derivado de __file__ (que só funciona em dev).
_DEFAULT_CANDIDATES = (
    "/apps/crypto-trader/trading/btc_trading_agent",
    "/apps/crypto-trader/btc_trading_agent",
    "/home/homelab/myClaude/btc_trading_agent",
)
KUCOIN_API_DIR = os.environ.get("KUCOIN_API_DIR", "")


def _http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_wallet_storj_balance(wallet: str = WALLET_ADDRESS) -> float:
    data = _http_json(f"{ZKSYNC_EXPLORER_BASE}/address/{wallet}")
    for entry in data.get("balances", {}).values():
        token = entry.get("token", {})
        if token.get("symbol") == "STORJ":
            decimals = int(token.get("decimals", 8))
            raw = int(entry.get("balance", "0") or "0")
            return raw / (10**decimals)
    return 0.0


def _resolve_kucoin_api_dir() -> str:
    if KUCOIN_API_DIR:
        return KUCOIN_API_DIR
    for candidate in _DEFAULT_CANDIDATES:
        if (Path(candidate) / "kucoin_api.py").is_file():
            return candidate
    # Fallback dev: dentro do checkout do repo (parents[2] a partir deste arquivo).
    return str(Path(__file__).resolve().parents[2] / "btc_trading_agent")


def fetch_kucoin_deposit_address(chain: str = KUCOIN_DEPOSIT_CHAIN) -> dict:
    """Busca (ou cria) o endereço de depósito STORJ na KuCoin.

    Reaproveita btc_trading_agent/kucoin_api.py — não duplica autenticação.
    """
    api_dir = _resolve_kucoin_api_dir()
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)
    import kucoin_api  # type: ignore

    result = kucoin_api.get_deposit_addresses("STORJ", chain=chain)
    addresses = result.get("addresses") or []
    if result.get("success") and addresses:
        return {"success": True, **addresses[0]}

    log.info("Nenhum endereço STORJ/%s existente — criando um novo", chain)
    return kucoin_api.create_deposit_address("STORJ", chain=chain)


def print_transfer_plan(wallet_balance: float, deposit_info: dict) -> None:
    print("=" * 70)
    print("PLANO DE TRANSFERÊNCIA STORJ (dry-run — nada foi executado)")
    print("=" * 70)
    print(f"Origem (carteira do nó, zkSync Era): {WALLET_ADDRESS}")
    print(f"Saldo disponível: {wallet_balance:.4f} STORJ")
    print()
    if not deposit_info.get("success"):
        print(f"⚠️  Falha ao obter endereço de depósito KuCoin: {deposit_info.get('error')}")
    else:
        print(f"Destino (KuCoin, rede ERC20/Ethereum, chainId KuCoin={KUCOIN_DEPOSIT_CHAIN}): {deposit_info.get('address')}")
        if deposit_info.get("memo"):
            print(f"Memo/Tag obrigatório: {deposit_info['memo']}")
    print()
    print("Etapa 1 — Bridge L2 -> L1:")
    print("  Via zkSync Era Bridge oficial (https://portal.zksync.io/bridge)")
    print(f"  Token: STORJ (contrato L1 {STORJ_L1_CONTRACT})")
    print(f"  Valor: {wallet_balance:.4f} STORJ")
    print("  Taxa: paga no próprio STORJ (meta-transação gasless)")
    print("  Assinatura: hardware wallet (Ledger/Trezor) conectado, confirmação física")
    print()
    print("Etapa 2 — Transfer ERC-20 padrão em L1:")
    print(f"  De: {WALLET_ADDRESS} (após bridge concluído)")
    print(f"  Para: endereço de depósito KuCoin acima (rede ERC20/Ethereum, chainId KuCoin={KUCOIN_DEPOSIT_CHAIN})")
    print("  Assinatura: mesmo hardware wallet")
    print()
    print("⚠️  RECOMENDADO: testar com $1-2 primeiro e confirmar crédito na KuCoin")
    print("    antes de mover o saldo total. Ver docs/storj-withdrawal-runbook.md.")
    print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="(padrão) só calcula e imprime o plano, não executa nada",
    )
    parser.add_argument(
        "--i-am-present",
        action="store_true",
        help="Confirma que um humano está fisicamente presente com o hardware wallet "
        "conectado — necessário para sair do modo --dry-run (ainda não implementado).",
    )
    parser.add_argument("--chain", default=KUCOIN_DEPOSIT_CHAIN, help="Rede de depósito na KuCoin")
    args = parser.parse_args()

    try:
        wallet_balance = fetch_wallet_storj_balance()
    except Exception as exc:  # noqa: BLE001
        log.error("Falha ao ler saldo on-chain: %s", exc)
        return 2

    try:
        deposit_info = fetch_kucoin_deposit_address(chain=args.chain)
    except Exception as exc:  # noqa: BLE001
        log.error("Falha ao buscar endereço de depósito KuCoin: %s", exc)
        deposit_info = {"success": False, "error": str(exc)}

    print_transfer_plan(wallet_balance, deposit_info)

    if not args.i_am_present:
        return 0

    raise NotImplementedError(
        "Assinatura e transmissão automatizada NÃO estão implementadas por design. "
        "Siga docs/storj-withdrawal-runbook.md: use o zkSync Era Bridge oficial "
        "(portal.zksync.io/bridge) com hardware wallet conectado."
    )


if __name__ == "__main__":
    raise SystemExit(main())
