#!/usr/bin/env python3
"""
Saque de BTC (ou qualquer moeda) via KuCoin API — requer vault LUKS montado.
Lê credenciais de /mnt/vault/keepass/kucoin.env

Uso:
  sudo python3 vault-kucoin-withdraw.py --coin BTC --amount 0.001 --address <addr> --network BTC
  sudo python3 vault-kucoin-withdraw.py --coin BTC --amount 0.001 --address <addr> --dry-run
  sudo python3 vault-kucoin-withdraw.py --list-chains BTC
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path

import urllib.request
import urllib.error

VAULT_ENV = Path("/mnt/vault/keepass/kucoin.env")
KUCOIN_BASE = "https://api.kucoin.com"


# ── credenciais ───────────────────────────────────────────────────────────────

def load_credentials() -> dict:
    if not Path("/mnt/vault").is_mount():
        sys.exit("ERRO: Vault não montado. Execute: sudo ./vault-open.sh open")
    if not VAULT_ENV.exists():
        sys.exit(f"ERRO: {VAULT_ENV} não encontrado. Execute backup-to-vault.sh primeiro.")

    creds = {}
    for line in VAULT_ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            creds[k.strip()] = v.strip()

    required = ["KUCOIN_API_KEY", "KUCOIN_API_SECRET", "KUCOIN_API_PASSPHRASE"]
    missing = [k for k in required if not creds.get(k)]
    if missing:
        sys.exit(f"ERRO: credenciais ausentes em {VAULT_ENV}: {missing}")
    return creds


# ── assinatura KuCoin ─────────────────────────────────────────────────────────

def _sign(secret: str, message: str) -> str:
    return base64.b64encode(
        hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()


def kucoin_headers(creds: dict, method: str, path: str, body: str = "") -> dict:
    ts = str(int(time.time() * 1000))
    version = creds.get("API_KEY_VERSION", "1")

    sig_msg = ts + method.upper() + path + body
    signature = _sign(creds["KUCOIN_API_SECRET"], sig_msg)

    passphrase = creds["KUCOIN_API_PASSPHRASE"]
    if version == "2":
        passphrase = _sign(creds["KUCOIN_API_SECRET"], passphrase)

    return {
        "KC-API-KEY": creds["KUCOIN_API_KEY"],
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": ts,
        "KC-API-PASSPHRASE": passphrase,
        "KC-API-KEY-VERSION": version,
        "Content-Type": "application/json",
    }


# ── chamadas API ──────────────────────────────────────────────────────────────

def api_get(creds: dict, path: str) -> dict:
    headers = kucoin_headers(creds, "GET", path)
    req = urllib.request.Request(KUCOIN_BASE + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        sys.exit(f"ERRO API {e.code}: {body}")


def api_post(creds: dict, path: str, payload: dict) -> dict:
    body = json.dumps(payload)
    headers = kucoin_headers(creds, "POST", path, body)
    req = urllib.request.Request(
        KUCOIN_BASE + path,
        data=body.encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        sys.exit(f"ERRO API {e.code}: {body}")


# ── operações ─────────────────────────────────────────────────────────────────

def get_balance(creds: dict, coin: str) -> float:
    data = api_get(creds, f"/api/v1/accounts?currency={coin}&type=main")
    accounts = data.get("data", [])
    for acc in accounts:
        if acc.get("currency") == coin and acc.get("type") == "main":
            return float(acc.get("available", 0))
    return 0.0


def list_chains(creds: dict, coin: str):
    data = api_get(creds, f"/api/v3/currencies/{coin}")
    chains = data.get("data", {}).get("chains", [])
    print(f"\nRedes disponíveis para {coin}:")
    print(f"{'Rede':<20} {'Taxa saque':<15} {'Mín. saque':<15} {'Depósito'}")
    print("-" * 65)
    for c in chains:
        print(
            f"{c.get('chainName','?'):<20} "
            f"{c.get('withdrawalMinFee','?'):<15} "
            f"{c.get('withdrawalMinSize','?'):<15} "
            f"{'✓' if c.get('isDepositEnabled') else '✗'}"
        )


def withdraw(creds: dict, coin: str, amount: float, address: str, network: str,
             memo: str = "", dry_run: bool = False):

    balance = get_balance(creds, coin)
    print(f"\nSaldo disponível ({coin} main): {balance:.8f}")

    if amount > balance:
        sys.exit(f"ERRO: saldo insuficiente ({balance:.8f} < {amount:.8f})")

    payload = {
        "currency": coin,
        "address": address,
        "amount": str(amount),
        "chain": network,
    }
    if memo:
        payload["memo"] = memo

    print(f"\nSaque:")
    print(f"  Moeda   : {coin}")
    print(f"  Valor   : {amount:.8f}")
    print(f"  Rede    : {network}")
    print(f"  Endereço: {address}")
    if memo:
        print(f"  Memo    : {memo}")

    if dry_run:
        print("\n[DRY-RUN] Saque NÃO enviado. Remova --dry-run para executar.")
        return

    print("\nConfirmar saque? [s/N] ", end="", flush=True)
    ans = input()
    if ans.strip().lower() != "s":
        print("Abortado.")
        return

    resp = api_post(creds, "/api/v1/withdrawals", payload)
    if resp.get("code") == "200000":
        wid = resp.get("data", {}).get("withdrawalId", "?")
        print(f"\nSaque solicitado com sucesso! ID: {wid}")
    else:
        print(f"\nERRO na resposta da API: {json.dumps(resp, indent=2)}")
        sys.exit(1)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Saque KuCoin via vault LUKS")
    sub = parser.add_subparsers(dest="cmd")

    # saque
    w = sub.add_parser("withdraw", help="Iniciar saque")
    w.add_argument("--coin", required=True, help="Ex: BTC, USDT")
    w.add_argument("--amount", required=True, type=float)
    w.add_argument("--address", required=True)
    w.add_argument("--network", required=True, help="Ex: BTC, ERC20, TRC20")
    w.add_argument("--memo", default="")
    w.add_argument("--dry-run", action="store_true")

    # listar redes
    lc = sub.add_parser("chains", help="Listar redes e taxas de uma moeda")
    lc.add_argument("coin")

    # saldo
    bal = sub.add_parser("balance", help="Ver saldo de uma moeda")
    bal.add_argument("coin")

    # compat: flags diretas na raiz (forma curta)
    parser.add_argument("--coin")
    parser.add_argument("--amount", type=float)
    parser.add_argument("--address")
    parser.add_argument("--network")
    parser.add_argument("--memo", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-chains", metavar="COIN")
    parser.add_argument("--balance", metavar="COIN")

    args = parser.parse_args()
    creds = load_credentials()

    if args.cmd == "chains" or args.list_chains:
        coin = (args.coin if args.cmd == "chains" else args.list_chains).upper()
        list_chains(creds, coin)
    elif args.cmd == "balance" or args.balance:
        coin = (args.coin if args.cmd == "balance" else args.balance).upper()
        b = get_balance(creds, coin)
        print(f"Saldo {coin} (main): {b:.8f}")
    elif args.cmd == "withdraw" or args.coin:
        coin = (args.coin or "").upper()
        if not coin or not args.amount or not args.address or not args.network:
            parser.print_help()
            sys.exit(1)
        withdraw(
            creds, coin, args.amount, args.address,
            args.network, args.memo, args.dry_run,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
