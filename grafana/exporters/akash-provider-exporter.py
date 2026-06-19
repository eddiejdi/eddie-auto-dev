#!/usr/bin/env python3
"""Prometheus exporter for Akash Provider /status endpoint + wallet balance.

All external HTTP calls run in a background thread so the /metrics handler
always responds instantly from cache — avoids Prometheus scrape_timeout races.
"""
import json
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PROVIDER_STATUS_URL = "https://192.168.15.2:30443/status"
WALLET_ADDRESS = "akash1m6usr35wjsdads7axwemwzp3gpjwpz2grhkrnf"
WALLET_API_URLS = [
    f"https://akash-api.polkachu.com/cosmos/bank/v1beta1/balances/{WALLET_ADDRESS}",
    f"https://api.akashnet.net/cosmos/bank/v1beta1/balances/{WALLET_ADDRESS}",
    f"https://rest.cosmos.directory/akash/cosmos/bank/v1beta1/balances/{WALLET_ADDRESS}",
]
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=akash-network&vs_currencies=brl,usd"
)
METRICS_PORT = 9115
STATUS_TIMEOUT = 5      # provider is internal — fail fast
EXTERNAL_TIMEOUT = 10   # blockchain/price APIs
REFRESH_INTERVAL = 30   # background thread refresh rate (seconds)
WALLET_TTL = 300        # re-query blockchain every 5 minutes
PRICE_TTL = 300         # re-fetch price every 5 minutes

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

_lock = threading.Lock()
_cache = {
    "status_data": None,
    "status_error": "initializing",
    "status_ts": 0.0,
    "wallet_akt": None,
    "wallet_ts": 0.0,
    "price_brl": None,
    "price_usd": None,
    "price_ts": 0.0,
}


def _fetch_status():
    import urllib.request
    try:
        req = urllib.request.urlopen(PROVIDER_STATUS_URL, context=ctx, timeout=STATUS_TIMEOUT)
        return json.loads(req.read()), None
    except Exception as e:
        return None, str(e)


def _fetch_wallet_balance():
    for url in WALLET_API_URLS:
        try:
            result = subprocess.run(
                ["curl", "-sf", "--max-time", str(EXTERNAL_TIMEOUT), url],
                capture_output=True, text=True, timeout=EXTERNAL_TIMEOUT + 2,
            )
            if result.returncode != 0:
                continue
            data = json.loads(result.stdout)
            uakt = next(
                (int(b["amount"]) for b in data.get("balances", []) if b["denom"] == "uakt"),
                0,
            )
            return uakt / 1_000_000
        except Exception:
            continue
    return None


def _fetch_price():
    try:
        result = subprocess.run(
            ["curl", "-sf", "--max-time", str(EXTERNAL_TIMEOUT), COINGECKO_URL],
            capture_output=True, text=True, timeout=EXTERNAL_TIMEOUT + 2,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data["akash-network"]["brl"]), float(data["akash-network"]["usd"])
    except Exception:
        pass
    return None, None


def _background_refresh():
    while True:
        now = time.time()
        data, error = _fetch_status()

        with _lock:
            _cache["status_data"] = data
            _cache["status_error"] = error
            _cache["status_ts"] = now

            if now - _cache["wallet_ts"] >= WALLET_TTL:
                balance = _fetch_wallet_balance()
                if balance is not None:
                    _cache["wallet_akt"] = balance
                    _cache["wallet_ts"] = now

            if now - _cache["price_ts"] >= PRICE_TTL:
                brl, usd = _fetch_price()
                if brl is not None:
                    _cache["price_brl"] = brl
                    _cache["price_usd"] = usd
                    _cache["price_ts"] = now

        time.sleep(REFRESH_INTERVAL)


def _render():
    with _lock:
        data = _cache["status_data"]
        error = _cache["status_error"]
        balance = _cache["wallet_akt"]
        price_brl = _cache["price_brl"]
        price_usd = _cache["price_usd"]

    lines = []
    up = 0 if error else 1
    lines.append(f'akash_provider_up{{instance="akash-provider"}} {up}')

    if data:
        cluster = data.get("cluster", {})
        leases = cluster.get("leases", 0)
        lines.append(f'akash_provider_active_leases_total{{instance="akash-provider"}} {leases}')

        inv = cluster.get("inventory", {}).get("available", {}).get("nodes", [])
        if inv:
            node = inv[0]
            alloc = node.get("allocatable", {})
            avail = node.get("available", {})
            for key in ["cpu", "memory", "gpu", "storage_ephemeral"]:
                lines.append(f'akash_provider_allocatable_{key}{{instance="akash-provider"}} {alloc.get(key, 0)}')
                lines.append(f'akash_provider_available_{key}{{instance="akash-provider"}} {avail.get(key, 0)}')

        bidengine = data.get("bidengine", {})
        lines.append(f'akash_provider_bidengine_orders{{instance="akash-provider"}} {bidengine.get("orders", 0)}')

        manifest = data.get("manifest", {})
        lines.append(f'akash_provider_manifest_deployments{{instance="akash-provider"}} {manifest.get("deployments", 0)}')

    if balance is not None:
        lines.append(
            f'akash_provider_wallet_balance_akt{{instance="akash-provider",'
            f'address="{WALLET_ADDRESS}"}} {balance:.6f}'
        )
        if price_brl is not None:
            lines.append(
                f'akash_provider_wallet_balance_brl{{instance="akash-provider",'
                f'address="{WALLET_ADDRESS}"}} {balance * price_brl:.4f}'
            )

    if price_brl is not None:
        lines.append(f'akash_provider_akt_price_brl{{instance="akash-provider"}} {price_brl:.6f}')
        lines.append(f'akash_provider_akt_price_usd{{instance="akash-provider"}} {price_usd:.6f}')

    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        body = _render().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    t = threading.Thread(target=_background_refresh, daemon=True)
    t.start()
    server = HTTPServer(("0.0.0.0", METRICS_PORT), Handler)
    print(f"Akash exporter listening on :{METRICS_PORT}")
    server.serve_forever()
