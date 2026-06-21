#!/usr/bin/env python3
"""Sweep diário: move AKT excedente do provider wallet para KuCoin.

Política de segurança:
  - Mantém RESERVE_AKT no wallet (gas + operações do provider)
  - Só transfere se excedente >= MINIMUM_SWEEP_AKT (mínimo KuCoin + fee)
  - Envia notificação Telegram com resultado
  - Loga em /var/log/akash-sweep.log
"""
import json
import logging
import os
import subprocess
import sys
import urllib.request

# ── Configuração ────────────────────────────────────────────────────────────
PROVIDER_WALLET   = "akash1m6usr35wjsdads7axwemwzp3gpjwpz2grhkrnf"
KUCOIN_ADDRESS    = "akash154v75gxqhsd52hdwuudjvqa0jejh6c6fp72924"
KUCOIN_MEMO       = "2097282990"

RESERVE_AKT       = 5.0          # mínimo mantido no provider wallet
MINIMUM_SWEEP_AKT = 3.0          # só executa se excedente >= isso (fee 1 AKT + min KuCoin 2 AKT)
FEE_UAKT          = 5000         # taxa de transação

BALANCE_API       = f"https://akash-api.polkachu.com/cosmos/bank/v1beta1/balances/{PROVIDER_WALLET}"
AKASH_NODE        = "https://akash-rpc.publicnode.com:443"
CHAIN_ID          = "akashnet-2"
KUBECONFIG        = "/mnt/disk4/akash-k3s/server/cred/admin.kubeconfig"
NAMESPACE         = "akash-services"
POD               = "akash-provider-0"

SECRETS_AGENT_URL = os.environ.get("SECRETS_AGENT_URL", "http://192.168.15.2:8088")
SECRETS_AGENT_KEY = os.environ.get("SECRETS_AGENT_API_KEY", "")
LOG_FILE          = "/var/log/akash-sweep.log"

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("akash-sweep")


# ── Helpers ─────────────────────────────────────────────────────────────────
def get_secret(name: str, *fields: str) -> str:
    """Busca um secret no Secrets Agent; tenta cada field em ordem."""
    headers = {"X-API-KEY": SECRETS_AGENT_KEY} if SECRETS_AGENT_KEY else {}
    try:
        req = urllib.request.Request(
            f"{SECRETS_AGENT_URL}/secrets/{name}", headers=headers
        )
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        for field in fields:
            val = data.get(field) or (data.get("data") or {}).get(field)
            if val:
                return str(val)
    except Exception as e:
        log.warning(f"secrets agent [{name}]: {e}")
    return ""


def fetch_balance_uakt() -> int:
    result = subprocess.run(
        ["curl", "-sf", "--max-time", "15", BALANCE_API],
        capture_output=True, text=True, timeout=20,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Falha ao consultar saldo: {result.stderr}")
    data = json.loads(result.stdout)
    uakt = next((int(b["amount"]) for b in data.get("balances", []) if b["denom"] == "uakt"), 0)
    return uakt


def fetch_akt_price_brl() -> float:
    result = subprocess.run(
        ["curl", "-sf", "--max-time", "10",
         "https://api.coingecko.com/api/v3/simple/price?ids=akash-network&vs_currencies=brl"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode == 0:
        return float(json.loads(result.stdout)["akash-network"]["brl"])
    return -1.0


def send_telegram(msg: str) -> None:
    token   = (get_secret("authentik/eddie/telegram_bot_token", "token", "password")
               or os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    chat_id = (get_secret("authentik/eddie/telegram_chat_id", "chat_id", "password")
               or os.environ.get("TELEGRAM_CHAT_ID", ""))
    if not token or not chat_id:
        log.warning("Telegram: credenciais não encontradas")
        return
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}).encode()
    req  = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
        log.info("Telegram: notificação enviada")
    except Exception as e:
        log.warning(f"Telegram: {e}")


def kubectl_exec(cmd: list[str]) -> tuple[int, str, str]:
    full_cmd = [
        "sudo", f"KUBECONFIG={KUBECONFIG}",
        "kubectl", "exec", POD, "-n", NAMESPACE, "--",
    ] + cmd
    # sudo não aceita env inline — usar env diretamente
    full_cmd = [
        "sudo",
        "kubectl", f"--kubeconfig={KUBECONFIG}",
        "exec", POD, "-n", NAMESPACE, "--",
    ] + cmd
    result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=60)
    return result.returncode, result.stdout, result.stderr


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("=== akash-sweep iniciado ===")

    # 1. Saldo atual
    try:
        balance_uakt = fetch_balance_uakt()
    except Exception as e:
        msg = f"❌ *Akash Sweep* — falha ao consultar saldo:\n`{e}`"
        log.error(msg)
        send_telegram(msg)
        sys.exit(1)

    balance_akt  = balance_uakt / 1_000_000
    reserve_uakt = int(RESERVE_AKT * 1_000_000)
    sweep_uakt   = balance_uakt - reserve_uakt   # fee descontada automaticamente pelo gas-auto
    sweep_akt    = sweep_uakt / 1_000_000

    price_brl = fetch_akt_price_brl()
    brl_str   = f"R$ {sweep_akt * price_brl:.2f}" if price_brl > 0 else "N/A"

    log.info(f"Saldo: {balance_akt:.6f} AKT | Reserva: {RESERVE_AKT} AKT | Excedente: {sweep_akt:.6f} AKT")

    # 2. Verificar se vale a pena transferir
    if sweep_akt < MINIMUM_SWEEP_AKT:
        msg = (
            f"ℹ️ *Akash Sweep* — saldo insuficiente para sweep\n"
            f"Saldo: `{balance_akt:.4f} AKT`\n"
            f"Excedente: `{sweep_akt:.4f} AKT` (mínimo: {MINIMUM_SWEEP_AKT} AKT)\n"
            f"Reserva mantida: `{RESERVE_AKT} AKT`"
        )
        log.info("Excedente abaixo do mínimo — nenhuma transferência")
        send_telegram(msg)
        sys.exit(0)

    # 3. Executar transferência
    log.info(f"Transferindo {sweep_uakt} uakt → KuCoin {KUCOIN_ADDRESS} (memo: {KUCOIN_MEMO})")

    tx_cmd = [
        "provider-services", "tx", "bank", "send",
        PROVIDER_WALLET, KUCOIN_ADDRESS,
        f"{sweep_uakt}uakt",
        "--chain-id", CHAIN_ID,
        "--node", AKASH_NODE,
        "--gas", "auto",
        "--gas-adjustment", "1.5",
        "--note", KUCOIN_MEMO,
        "--yes",
        "--output", "json",
    ]

    rc, stdout, stderr = kubectl_exec(tx_cmd)

    if rc != 0:
        msg = (
            f"❌ *Akash Sweep* — falha na transação\n"
            f"Valor: `{sweep_akt:.4f} AKT`\n"
            f"Erro: `{(stderr or stdout)[:300]}`"
        )
        log.error(f"Transação falhou (rc={rc}): {stderr or stdout}")
        send_telegram(msg)
        sys.exit(1)

    # Extrair txhash
    try:
        tx_data = json.loads(stdout)
        txhash  = tx_data.get("txhash", "desconhecido")
        tx_code = tx_data.get("code", -1)
    except Exception:
        txhash  = "parse-error"
        tx_code = -1

    if tx_code != 0:
        raw_log = json.loads(stdout).get("raw_log", stdout[:200]) if stdout else stderr[:200]
        msg = (
            f"❌ *Akash Sweep* — transação rejeitada (code={tx_code})\n"
            f"txhash: `{txhash}`\n"
            f"Log: `{raw_log[:200]}`"
        )
        log.error(f"Chain rejeitou tx (code={tx_code}): {raw_log}")
        send_telegram(msg)
        sys.exit(1)

    msg = (
        f"✅ *Akash Sweep* — transferência concluída\n"
        f"Valor: `{sweep_akt:.4f} AKT` (~{brl_str})\n"
        f"Para: `{KUCOIN_ADDRESS}`\n"
        f"Memo: `{KUCOIN_MEMO}`\n"
        f"Reserva: `{RESERVE_AKT} AKT` mantidos\n"
        f"TxHash: `{txhash}`"
    )
    log.info(f"Sucesso! txhash={txhash} sweep={sweep_akt:.4f} AKT")
    send_telegram(msg)


if __name__ == "__main__":
    main()
