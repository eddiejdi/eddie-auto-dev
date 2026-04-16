#!/usr/bin/env python3
"""Controle simples para reativar guardrails do trading via HTTP local."""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse


DEFAULT_TARGETS: dict[str, dict[str, float | int]] = {
    "aggressive": {"max_daily_trades": 9999, "max_daily_loss": 0.03},
    "conservative": {"max_daily_trades": 9999, "max_daily_loss": 0.085},
}
DEFAULT_SYMBOL = os.environ.get("TRADING_SYMBOL", "BTC-USDT")
TRADING_FEE_PCT = 0.001
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = PROJECT_ROOT / "btc_trading_agent"
for candidate in (PROJECT_ROOT, AGENT_DIR):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)


@dataclass(frozen=True)
class GuardrailStatus:
    profile: str
    max_daily_trades: int
    max_daily_loss: float
    dry_run: bool


@dataclass(frozen=True)
class ManualSellPosition:
    profile: str
    position_ref: str
    trade_ids: str
    entries: int
    position_btc: float
    avg_entry: float
    current_price: float
    target_sell: float | None
    target_reason: str


@dataclass(frozen=True)
class ManualSellResult:
    profile: str
    symbol: str
    size: float
    price: float
    pnl: float
    pnl_pct: float
    order_id: str | None
    trade_id: int
    dry_run: bool
    actor: str


def load_profile_config(config_dir: Path, profile: str) -> dict[str, Any]:
    path = _config_path(config_dir, profile)
    return json.loads(path.read_text(encoding="utf-8"))


def _config_path(config_dir: Path, profile: str) -> Path:
    return config_dir / f"config_BTC_USDT_{profile}.json"


def load_status(config_dir: Path) -> list[GuardrailStatus]:
    statuses: list[GuardrailStatus] = []
    for profile in DEFAULT_TARGETS:
        payload = load_profile_config(config_dir, profile)
        statuses.append(
            GuardrailStatus(
                profile=profile,
                max_daily_trades=int(payload.get("max_daily_trades", 0)),
                max_daily_loss=float(payload.get("max_daily_loss", 0.0)),
                dry_run=bool(payload.get("dry_run", False)),
            )
        )
    return statuses


def reactivate_guardrails(config_dir: Path) -> list[GuardrailStatus]:
    statuses: list[GuardrailStatus] = []
    for profile, targets in DEFAULT_TARGETS.items():
        path = _config_path(config_dir, profile)
        payload = load_profile_config(config_dir, profile)
        payload["max_daily_trades"] = int(targets["max_daily_trades"])
        payload["max_daily_loss"] = float(targets["max_daily_loss"])
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        statuses.append(
            GuardrailStatus(
                profile=profile,
                max_daily_trades=int(payload["max_daily_trades"]),
                max_daily_loss=float(payload["max_daily_loss"]),
                dry_run=bool(payload.get("dry_run", False)),
            )
        )
    return statuses


def restart_agents() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "systemctl",
            "restart",
            "crypto-agent@BTC_USDT_aggressive.service",
            "crypto-agent@BTC_USDT_conservative.service",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def restart_profile_agent(profile: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", "restart", f"crypto-agent@BTC_USDT_{profile}.service"],
        check=True,
        capture_output=True,
        text=True,
    )


def _load_training_db():
    from training_db import TrainingDatabase

    return TrainingDatabase()


def _compute_manual_sell_pnl(avg_entry: float, price: float, size: float) -> tuple[float, float]:
    gross_pnl = (price - avg_entry) * size
    sell_fee = price * size * TRADING_FEE_PCT
    buy_fee = avg_entry * size * TRADING_FEE_PCT
    pnl = gross_pnl - sell_fee - buy_fee
    net_sell_price = price * (1 - TRADING_FEE_PCT)
    net_buy_price = avg_entry * (1 + TRADING_FEE_PCT)
    pnl_pct = ((net_sell_price / net_buy_price) - 1) * 100 if net_buy_price > 0 else 0
    return pnl, pnl_pct


def build_manual_sell_path(profile: str) -> str:
    return f"/manual-sell?profile={quote_plus(profile)}"


def load_open_positions(symbol: str = DEFAULT_SYMBOL, profile: str | None = None) -> list[ManualSellPosition]:
    db = _load_training_db()
    with db._get_conn() as conn:  # noqa: SLF001 - internal helper used by control plane
        cur = conn.cursor()
        cur.execute(
            """
            WITH last_sell AS (
              SELECT
                profile,
                MAX(timestamp) FILTER (WHERE side = 'sell') AS last_sell_ts
              FROM btc.trades
              WHERE symbol = %s
                AND dry_run = false
              GROUP BY profile
            ),
            position_summary AS (
              SELECT
                t.profile,
                CONCAT(
                  t.profile,
                  '#',
                  MIN(t.id),
                  CASE WHEN MIN(t.id) <> MAX(t.id) THEN CONCAT('-', MAX(t.id)) ELSE '' END
                ) AS position_ref,
                STRING_AGG(t.id::text, ',' ORDER BY t.id) AS position_trade_ids,
                COUNT(*) AS entries,
                SUM(t.size) AS position_btc,
                SUM(t.size * t.price) / NULLIF(SUM(t.size), 0) AS avg_entry
              FROM btc.trades t
              LEFT JOIN last_sell ls ON ls.profile = t.profile
              WHERE t.symbol = %s
                AND t.dry_run = false
                AND t.side = 'buy'
                AND (%s IS NULL OR t.profile = %s)
                AND (ls.last_sell_ts IS NULL OR t.timestamp > ls.last_sell_ts)
              GROUP BY t.profile
            ),
            latest_target AS (
              SELECT DISTINCT ON (profile)
                profile,
                COALESCE(
                  NULLIF(metadata->>'target_sell_price', '')::double precision,
                  NULLIF(metadata->>'target_sell_trigger_price', '')::double precision
                ) AS sell_target,
                COALESCE(metadata->>'target_sell_reason', '') AS target_reason
              FROM btc.trades
              WHERE symbol = %s
                AND dry_run = false
                AND side = 'buy'
                AND (%s IS NULL OR profile = %s)
              ORDER BY profile, timestamp DESC, id DESC
            ),
            latest_state AS (
              SELECT (
                SELECT price
                FROM btc.market_states
                WHERE symbol = %s
                ORDER BY timestamp DESC
                LIMIT 1
              ) AS current_price
            )
            SELECT
              ps.profile,
              ps.position_ref,
              ps.position_trade_ids,
              ps.entries,
              ps.position_btc,
              ps.avg_entry,
              ls.current_price,
              lt.sell_target,
              COALESCE(lt.target_reason, '') AS target_reason
            FROM position_summary ps
            CROSS JOIN latest_state ls
            LEFT JOIN latest_target lt ON lt.profile = ps.profile
            ORDER BY ps.profile
            """,
            (symbol, symbol, profile, profile, symbol, profile, profile, symbol),
        )
        rows = cur.fetchall()

    positions: list[ManualSellPosition] = []
    for row in rows:
        positions.append(
            ManualSellPosition(
                profile=str(row[0]),
                position_ref=str(row[1]),
                trade_ids=str(row[2] or ""),
                entries=int(row[3] or 0),
                position_btc=float(row[4] or 0.0),
                avg_entry=float(row[5] or 0.0),
                current_price=float(row[6] or 0.0),
                target_sell=float(row[7]) if row[7] is not None else None,
                target_reason=str(row[8] or ""),
            )
        )
    return positions


def _fetch_live_price(symbol: str) -> float | None:
    try:
        from kucoin_api import get_price_fast
    except Exception:
        return None

    try:
        return float(get_price_fast(symbol))
    except Exception:
        return None


def execute_manual_sell(
    *,
    config_dir: Path,
    profile: str,
    actor: str,
    symbol: str = DEFAULT_SYMBOL,
) -> ManualSellResult:
    positions = load_open_positions(symbol=symbol, profile=profile)
    if not positions:
        raise ValueError(f"Nenhuma posição aberta encontrada para {profile}.")
    position = positions[0]
    if position.position_btc <= 0:
        raise ValueError(f"Posição inválida para {profile}.")

    config = load_profile_config(config_dir, profile)
    dry_run = bool(config.get("dry_run", False))
    price = _fetch_live_price(symbol) or position.current_price or position.avg_entry
    if price <= 0:
        raise RuntimeError("Não foi possível resolver o preço atual para a venda manual.")

    order_id = None
    if not dry_run:
        try:
            from kucoin_api import place_market_order
        except Exception as exc:  # pragma: no cover - runtime-only safeguard
            raise RuntimeError("KuCoin API indisponível para venda manual.") from exc

        result = place_market_order(symbol, "sell", size=position.position_btc)
        if not result.get("success"):
            raise RuntimeError(f"Falha ao executar ordem SELL: {result}")
        order_id = result.get("orderId")

    pnl, pnl_pct = _compute_manual_sell_pnl(position.avg_entry, price, position.position_btc)
    db = _load_training_db()
    metadata = {
        "source": "manual_sell_menu",
        "actor": actor,
        "position_ref": position.position_ref,
        "trade_ids": position.trade_ids,
        "target_sell": position.target_sell,
        "target_reason": position.target_reason,
        "manual": True,
        "executed_at": int(time.time()),
    }
    trade_id = db.record_trade(
        symbol=symbol,
        side="sell",
        price=price,
        size=position.position_btc,
        funds=round(price * position.position_btc, 2),
        order_id=order_id,
        dry_run=dry_run,
        metadata=metadata,
        profile=profile,
    )
    db.update_trade_pnl(trade_id, pnl, pnl_pct)
    restart_profile_agent(profile)
    return ManualSellResult(
        profile=profile,
        symbol=symbol,
        size=position.position_btc,
        price=price,
        pnl=pnl,
        pnl_pct=pnl_pct,
        order_id=order_id,
        trade_id=trade_id,
        dry_run=dry_run,
        actor=actor,
    )


def _basic_auth_ok(header_value: str | None, username: str, password: str) -> bool:
    if not header_value or not header_value.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header_value[6:]).decode("utf-8")
    except Exception:
        return False
    return decoded == f"{username}:{password}"


def _authentik_auth_ok(headers: dict[str, str], required_group: str | None) -> bool:
    username = (headers.get("X-authentik-username") or "").strip()
    if not username:
        return False
    if not required_group:
        return True
    raw_groups = headers.get("X-authentik-groups") or ""
    groups = {item.strip() for item in raw_groups.split(",") if item.strip()}
    return required_group in groups


def _status_table(statuses: list[GuardrailStatus]) -> str:
    rows = []
    for item in statuses:
        rows.append(
            "<tr>"
            f"<td>{html.escape(item.profile)}</td>"
            f"<td>{item.max_daily_trades}</td>"
            f"<td>{item.max_daily_loss:.3f}</td>"
            f"<td>{'true' if item.dry_run else 'false'}</td>"
            "</tr>"
        )
    return (
        "<table border='1' cellpadding='8' cellspacing='0' "
        "style='border-collapse:collapse;font-family:monospace;'>"
        "<tr><th>profile</th><th>max_daily_trades</th><th>max_daily_loss</th><th>dry_run</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def _positions_table(positions: list[ManualSellPosition]) -> str:
    if not positions:
        return "<p>Nenhuma posição aberta encontrada.</p>"

    rows = []
    for item in positions:
        current = item.current_price or item.avg_entry
        open_pnl, open_pnl_pct = _compute_manual_sell_pnl(item.avg_entry, current, item.position_btc)
        target_sell_html = f"${item.target_sell:,.2f}" if item.target_sell is not None else "--"
        rows.append(
            "<tr>"
            f"<td>{html.escape(item.profile)}</td>"
            f"<td><a href=\"{html.escape(build_manual_sell_path(item.profile))}\">{html.escape(item.position_ref)}</a></td>"
            f"<td>{item.entries}</td>"
            f"<td>{item.position_btc:.8f}</td>"
            f"<td>${item.avg_entry:,.2f}</td>"
            f"<td>${current:,.2f}</td>"
            f"<td>{target_sell_html}</td>"
        )
        rows[-1] += f"<td>{open_pnl_pct:.2f}%</td><td>${open_pnl:.4f}</td></tr>"
    return (
        "<table border='1' cellpadding='8' cellspacing='0' "
        "style='border-collapse:collapse;font-family:monospace;width:100%;'>"
        "<tr><th>profile</th><th>posição</th><th>entradas</th><th>size BTC</th><th>entry médio</th>"
        "<th>preço atual</th><th>target sell</th><th>pnl aberto %</th><th>pnl aberto $</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def _manual_sell_menu_body(position: ManualSellPosition) -> str:
    current_price = position.current_price or position.avg_entry
    open_pnl, open_pnl_pct = _compute_manual_sell_pnl(position.avg_entry, current_price, position.position_btc)
    target_line = (
        f"<p><strong>Target sell:</strong> ${position.target_sell:,.2f} "
        f"<span style='color:#9ca3af;'>({html.escape(position.target_reason or 'sem razão registrada')})</span></p>"
        if position.target_sell is not None
        else "<p><strong>Target sell:</strong> --</p>"
    )
    return (
        "<p>Esta ação vende a <strong>posição aberta inteira</strong> do profile selecionado. "
        "Não executa venda parcial por trade individual.</p>"
        f"<p><strong>Profile:</strong> {html.escape(position.profile)}</p>"
        f"<p><strong>Posição:</strong> {html.escape(position.position_ref)}</p>"
        f"<p><strong>Trades IDs:</strong> {html.escape(position.trade_ids)}</p>"
        f"<p><strong>Entradas:</strong> {position.entries}</p>"
        f"<p><strong>BTC:</strong> {position.position_btc:.8f}</p>"
        f"<p><strong>Entry médio:</strong> ${position.avg_entry:,.2f}</p>"
        f"<p><strong>Preço atual:</strong> ${current_price:,.2f}</p>"
        + target_line
        + f"<p><strong>PnL aberto:</strong> ${open_pnl:.4f} / {open_pnl_pct:.2f}%</p>"
        + (
            "<form method='post' action='/manual-sell/execute' "
            "onsubmit=\"return confirm('Confirmar SELL MARKET da posição inteira?');\">"
            f"<input type='hidden' name='profile' value='{html.escape(position.profile)}' />"
            "<button type='submit' "
            "style='background:#dc2626;color:#fff;border:none;padding:12px 16px;border-radius:8px;"
            "font-weight:700;cursor:pointer;'>Executar SELL market</button>"
            "</form>"
        )
        + "<p style='margin-top:12px;'><a href='/manual-sell' style='color:#7dd3fc;'>Voltar para posições abertas</a></p>"
    )


def build_handler(config_dir: Path, username: str, password: str | None) -> type[BaseHTTPRequestHandler]:
    required_group = os.environ.get("AUTHENTIK_REQUIRED_GROUP", "").strip() or None

    class Handler(BaseHTTPRequestHandler):
        server_version = "TradingGuardrailsControl/1.0"

        def _actor(self) -> str:
            return (
                (self.headers.get("X-authentik-username") or "").strip()
                or username
            )

        def _parsed_path(self):
            return urlparse(self.path)

        def _form_data(self) -> dict[str, str]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else ""
            parsed = parse_qs(raw, keep_blank_values=True)
            return {key: values[0] for key, values in parsed.items() if values}

        def _require_auth(self) -> bool:
            headers = {key: value for key, value in self.headers.items()}
            if _authentik_auth_ok(headers, required_group):
                return True
            if not password:
                self.send_response(HTTPStatus.FORBIDDEN)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Authentik authorization required.\n")
                return False
            if _basic_auth_ok(self.headers.get("Authorization"), username, password):
                return True
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.send_header("WWW-Authenticate", 'Basic realm="Trading Guardrails"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Authentication required.\n")
            return False

        def _send_html(self, status: HTTPStatus, title: str, body: str) -> None:
            payload = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                f"<title>{html.escape(title)}</title>"
                "<style>body{font-family:Arial,sans-serif;margin:24px;color:#dce3ea;background:#111827;}"
                "a{color:#7dd3fc;} .card{max-width:720px;padding:24px;border-radius:12px;background:#1f2937;}"
                "h1{margin-top:0;} code{background:#0f172a;padding:2px 6px;border-radius:6px;}</style>"
                "</head><body><div class='card'>"
                f"<h1>{html.escape(title)}</h1>{body}</div></body></html>"
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            parsed = self._parsed_path()

            if parsed.path == "/health":
                payload = json.dumps(
                    {
                        "ok": True,
                        "profiles": [item.__dict__ for item in load_status(config_dir)],
                    }
                ).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            if parsed.path == "/reactivate":
                if not self._require_auth():
                    return
                try:
                    statuses = reactivate_guardrails(config_dir)
                    restart_agents()
                except subprocess.CalledProcessError as exc:
                    body = (
                        "<p>Falha ao reiniciar os agents.</p>"
                        f"<pre>{html.escape(exc.stderr or exc.stdout or str(exc))}</pre>"
                    )
                    self._send_html(HTTPStatus.INTERNAL_SERVER_ERROR, "Erro ao reativar guardrails", body)
                    return
                except Exception as exc:  # pragma: no cover - safety net
                    body = f"<p>Falha inesperada.</p><pre>{html.escape(str(exc))}</pre>"
                    self._send_html(HTTPStatus.INTERNAL_SERVER_ERROR, "Erro ao reativar guardrails", body)
                    return

                body = (
                    "<p>Guardrails reativados com sucesso.</p>"
                    + _status_table(statuses)
                    + "<p>Os agents foram reiniciados.</p>"
                )
                self._send_html(HTTPStatus.OK, "Guardrails reativados", body)
                return

            if parsed.path == "/manual-sell":
                if not self._require_auth():
                    return
                params = parse_qs(parsed.query)
                profile = (params.get("profile") or [""])[0].strip()
                if profile:
                    positions = load_open_positions(profile=profile)
                    if not positions:
                        self._send_html(
                            HTTPStatus.NOT_FOUND,
                            "Venda manual indisponível",
                            f"<p>Nenhuma posição aberta encontrada para <code>{html.escape(profile)}</code>.</p>"
                            "<p><a href='/manual-sell' style='color:#7dd3fc;'>Voltar</a></p>",
                        )
                        return
                    self._send_html(
                        HTTPStatus.OK,
                        f"Venda manual • {profile}",
                        _manual_sell_menu_body(positions[0]),
                    )
                    return

                positions = load_open_positions()
                body = (
                    "<p>Selecione uma posição para abrir o menu de venda manual.</p>"
                    + _positions_table(positions)
                )
                self._send_html(HTTPStatus.OK, "Venda manual", body)
                return

            if not self._require_auth():
                return

            statuses = load_status(config_dir)
            body = (
                "<p>Use <code>/reactivate</code> para restaurar os caps de perda diária.</p>"
                + _status_table(statuses)
            )
            self._send_html(HTTPStatus.OK, "Trading Guardrails Control", body)

        def do_POST(self) -> None:  # noqa: N802
            parsed = self._parsed_path()
            if parsed.path == "/manual-sell/execute":
                if not self._require_auth():
                    return
                profile = self._form_data().get("profile", "").strip()
                if not profile:
                    self._send_html(
                        HTTPStatus.BAD_REQUEST,
                        "Venda manual inválida",
                        "<p>Profile não informado.</p>",
                    )
                    return
                try:
                    result = execute_manual_sell(
                        config_dir=config_dir,
                        profile=profile,
                        actor=self._actor(),
                    )
                except subprocess.CalledProcessError as exc:
                    body = (
                        "<p>Falha ao reiniciar o agent após a venda manual.</p>"
                        f"<pre>{html.escape(exc.stderr or exc.stdout or str(exc))}</pre>"
                    )
                    self._send_html(HTTPStatus.INTERNAL_SERVER_ERROR, "Erro na venda manual", body)
                    return
                except Exception as exc:
                    body = f"<p>Falha ao executar SELL manual.</p><pre>{html.escape(str(exc))}</pre>"
                    self._send_html(HTTPStatus.INTERNAL_SERVER_ERROR, "Erro na venda manual", body)
                    return

                body = (
                    "<p>Venda manual executada com sucesso.</p>"
                    f"<p><strong>Profile:</strong> {html.escape(result.profile)}</p>"
                    f"<p><strong>Size:</strong> {result.size:.8f} BTC</p>"
                    f"<p><strong>Preço:</strong> ${result.price:,.2f}</p>"
                    f"<p><strong>PnL:</strong> ${result.pnl:.4f} / {result.pnl_pct:.2f}%</p>"
                    f"<p><strong>Trade ID:</strong> {result.trade_id}</p>"
                    f"<p><strong>Order ID:</strong> {html.escape(result.order_id or 'dry-run')}</p>"
                    f"<p><strong>Executado por:</strong> {html.escape(result.actor)}</p>"
                    "<p>O agent do profile foi reiniciado para restaurar o estado.</p>"
                    "<p><a href='/manual-sell' style='color:#7dd3fc;'>Voltar para posições abertas</a></p>"
                )
                self._send_html(HTTPStatus.OK, "Venda manual executada", body)
                return

            if parsed.path != "/reactivate":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not self._require_auth():
                return

            try:
                statuses = reactivate_guardrails(config_dir)
                restart_agents()
            except subprocess.CalledProcessError as exc:
                body = (
                    "<p>Falha ao reiniciar os agents.</p>"
                    f"<pre>{html.escape(exc.stderr or exc.stdout or str(exc))}</pre>"
                )
                self._send_html(HTTPStatus.INTERNAL_SERVER_ERROR, "Erro ao reativar guardrails", body)
                return
            except Exception as exc:  # pragma: no cover - safety net
                body = f"<p>Falha inesperada.</p><pre>{html.escape(str(exc))}</pre>"
                self._send_html(HTTPStatus.INTERNAL_SERVER_ERROR, "Erro ao reativar guardrails", body)
                return

            body = (
                "<p>Guardrails reativados com sucesso.</p>"
                + _status_table(statuses)
                + "<p>Os agents foram reiniciados.</p>"
            )
            self._send_html(HTTPStatus.OK, "Guardrails reativados", body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("CONTROL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CONTROL_PORT", "8765")))
    parser.add_argument(
        "--config-dir",
        default=os.environ.get("TRADING_CONFIG_DIR", "/apps/crypto-trader/trading/btc_trading_agent"),
    )
    args = parser.parse_args()

    username = os.environ.get("CONTROL_USER", "guardrails")
    password = os.environ.get("CONTROL_PASSWORD")

    config_dir = Path(args.config_dir)
    server = ThreadingHTTPServer((args.host, args.port), build_handler(config_dir, username, password))
    server.serve_forever()


if __name__ == "__main__":
    main()
