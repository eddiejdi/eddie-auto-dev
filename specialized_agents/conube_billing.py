"""Cobranças da Conube (faturas Vindi) — detecção de boleto pendente e pagamento via Mercado Pago.

A mensalidade da Conube é faturada pela Vindi (endpoint ``client/cobrancas``).
Quando a cobrança no cartão falha ou o método é boleto, a fatura fica pendente
e a página pública da Vindi (``url`` com token) expõe a linha digitável do
boleto e/ou o PIX copia-e-cola.

Fluxo de resolução::

    fetch_charges → pending_charges → fetch_bill_payment_data (Vindi)
        → check_mercadopago_balance (API oficial MP)
        → payer.pay_barcode (Mercado Pago web, sessão persistente)

O pagamento movimenta dinheiro real: só é executado sob intent aprovada no
Telegram (ConubeBillingPaymentAgent, risk=high). Sem payer disponível, o
resultado é ``manual_required`` com os códigos prontos para copiar.
"""

from __future__ import annotations

import logging
import os
import re
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

CHARGE_OPEN_STATUSES = {"pending", "review", "scheduled", "overdue"}
VINDI_HTTP_TIMEOUT = float(os.getenv("CONUBE_VINDI_TIMEOUT", "30"))
DEFAULT_PAY_LIMIT = int(os.getenv("CONUBE_BILLING_PAY_LIMIT", "3"))

# Linha digitável de boleto: 47 dígitos (cobrança) ou 48 (arrecadação),
# com ou sem pontuação/espaços.
_DIGITABLE_FORMATTED_RE = re.compile(
    r"\d{5}[.\s]?\d{5}\s*\d{5}[.\s]?\d{6}\s*\d{5}[.\s]?\d{6}\s*\d\s*\d{14}"
)
_DIGITABLE_PLAIN_RE = re.compile(r"(?<!\d)\d{47,48}(?!\d)")
# PIX copia-e-cola (payload EMV): começa em 000201 e termina no CRC 6304XXXX.
_PIX_EMV_RE = re.compile(r"000201[\x20-\x7e]{20,600}?6304[0-9A-Fa-f]{4}")
_BOLETO_PDF_RE = re.compile(r"https?://[^\s\"'<>]+(?:boleto|bank_slip)[^\s\"'<>]*", re.IGNORECASE)


def charge_amount_cents(charge: dict[str, Any]) -> int:
    try:
        return int(charge.get("amount") or 0)
    except (TypeError, ValueError):
        return 0


def format_brl(amount_cents: int) -> str:
    value = Decimal(amount_cents) / 100
    return f"R$ {value:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def fetch_charges(agent: Any) -> list[dict[str, Any]]:
    """Lista as cobranças (faturas Vindi) via API autenticada da Conube."""
    payload = agent._authenticated_api_get("cobrancas", api_version="client")
    docs = payload.get("docs") if isinstance(payload, dict) else None
    return docs if isinstance(docs, list) else []


def pending_charges(charges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        charge
        for charge in charges
        if str(charge.get("status") or "").strip().lower() in CHARGE_OPEN_STATUSES
    ]


def summarize_charge(charge: dict[str, Any]) -> dict[str, Any]:
    return {
        "bill_id": charge.get("id"),
        "status": charge.get("status"),
        "amount_cents": charge_amount_cents(charge),
        "amount_brl": format_brl(charge_amount_cents(charge)),
        "billing_at": charge.get("billing_at"),
        "due_at": charge.get("due_at"),
        "url": charge.get("url"),
    }


def extract_payment_data(html: str) -> dict[str, Any]:
    """Extrai linha digitável, PIX copia-e-cola e link do boleto do HTML da Vindi."""
    digitable: str | None = None
    match = _DIGITABLE_FORMATTED_RE.search(html)
    if match:
        digitable = re.sub(r"\D", "", match.group(0))
    else:
        for candidate in _DIGITABLE_PLAIN_RE.findall(html):
            digitable = candidate
            break

    pix_match = _PIX_EMV_RE.search(html)
    pdf_match = _BOLETO_PDF_RE.search(html)
    return {
        "linha_digitavel": digitable,
        "pix_copia_cola": pix_match.group(0) if pix_match else None,
        "boleto_url": pdf_match.group(0) if pdf_match else None,
    }


def fetch_bill_payment_data(url: str, *, timeout: float = VINDI_HTTP_TIMEOUT) -> dict[str, Any]:
    """Baixa a página pública da fatura Vindi (URL com token) e extrai dados de pagamento."""
    import httpx

    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    data = extract_payment_data(response.text)
    data["bill_page_status"] = response.status_code
    return data


def check_mercadopago_balance() -> dict[str, Any]:
    """Consulta o saldo disponível na conta Mercado Pago (API oficial)."""
    import asyncio

    from specialized_agents.banking.mercadopago_connector import MercadoPagoConnector

    async def _run() -> dict[str, Any]:
        connector = MercadoPagoConnector()
        balance = await connector.get_balance()
        return {
            "available_cents": int(balance.available * 100),
            "available_brl": format_brl(int(balance.available * 100)),
            "source": balance.source,
        }

    try:
        return asyncio.run(_run())
    except RuntimeError:
        # Já existe event loop rodando neste thread (ex.: chamada de rota async).
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _run()).result()
    except Exception as exc:
        logger.warning("Saldo Mercado Pago indisponível: %s", exc)
        return {"available_cents": None, "error": str(exc)}


def fetch_pending_billing(agent: Any, *, with_payment_data: bool = True) -> dict[str, Any]:
    """Snapshot somente-leitura das cobranças pendentes da Conube."""
    login_result = agent.login()
    if not login_result.get("authenticated"):
        return {
            "status": "error",
            "pending_count": 0,
            "charges": [],
            "message": str(login_result.get("failure_reason") or "Login da Conube nao autenticou."),
        }

    pending = pending_charges(fetch_charges(agent))
    charges: list[dict[str, Any]] = []
    for charge in pending:
        summary = summarize_charge(charge)
        if with_payment_data and summary.get("url"):
            try:
                summary["payment_data"] = fetch_bill_payment_data(str(summary["url"]))
            except Exception as exc:
                summary["payment_data"] = {"error": str(exc)}
        charges.append(summary)

    return {
        "status": "ok",
        "pending_count": len(charges),
        "total_amount_cents": sum(item["amount_cents"] for item in charges),
        "charges": charges,
    }


def _build_payer() -> Any:
    from specialized_agents.banking.mercadopago_payer import MercadoPagoWebPayer

    return MercadoPagoWebPayer()


def pay_pending_charges(
    agent: Any,
    *,
    payer: Any | None = None,
    dry_run: bool = False,
    limit: int = DEFAULT_PAY_LIMIT,
) -> dict[str, Any]:
    """Resolve boletos pendentes da Conube pagando via Mercado Pago.

    Deve rodar apenas sob intent aprovada (dinheiro real). Cada cobrança:
    extrai a linha digitável, valida saldo MP e delega ao payer. Sem payer
    utilizável, marca ``manual_required`` com os códigos para pagamento manual.
    """
    snapshot = fetch_pending_billing(agent, with_payment_data=True)
    if snapshot.get("status") != "ok":
        return {"status": "error", "processed": 0, "results": [], "message": snapshot.get("message")}

    charges = snapshot.get("charges") or []
    if not charges:
        return {"status": "ok", "processed": 0, "results": [], "message": "Nenhuma cobrança pendente."}

    balance = check_mercadopago_balance()
    results: list[dict[str, Any]] = []
    processed = 0

    for summary in charges[: max(1, limit)]:
        entry: dict[str, Any] = dict(summary)
        payment_data = summary.get("payment_data") or {}
        digitable = payment_data.get("linha_digitavel")

        if not digitable:
            entry["result"] = "no_barcode"
            entry["message"] = (
                "Fatura pendente sem linha digitável na página da Vindi "
                "(provável cobrança por cartão em retentativa)."
            )
            results.append(entry)
            continue

        available = balance.get("available_cents")
        if available is not None and available < entry["amount_cents"]:
            entry["result"] = "insufficient_balance"
            entry["message"] = (
                f"Saldo Mercado Pago {balance.get('available_brl')} menor que "
                f"{entry['amount_brl']}."
            )
            results.append(entry)
            continue

        if dry_run:
            entry["result"] = "dry_run"
            results.append(entry)
            continue

        active_payer = payer
        if active_payer is None:
            try:
                active_payer = _build_payer()
            except Exception as exc:
                entry["result"] = "manual_required"
                entry["message"] = f"Payer Mercado Pago indisponível: {exc}"
                results.append(entry)
                continue

        try:
            payment = active_payer.pay_barcode(
                digitable,
                amount_cents=entry["amount_cents"],
                description=f"Conube fatura #{entry.get('bill_id')}",
            )
            entry["result"] = "paid" if payment.get("ok") else "payment_failed"
            entry["payment"] = payment
            if payment.get("ok"):
                processed += 1
        except Exception as exc:
            entry["result"] = "manual_required"
            entry["message"] = str(exc)
        results.append(entry)

    failed = [item for item in results if item.get("result") in {"payment_failed", "manual_required"}]
    return {
        "status": "ok" if not failed else "warning",
        "processed": processed,
        "pending_count": snapshot.get("pending_count"),
        "mercadopago_balance": balance,
        "dry_run": dry_run,
        "results": results,
    }


def format_billing_telegram_lines(result: dict[str, Any]) -> list[str]:
    """Linhas HTML para o resumo Telegram (usadas pela remediação e pelo intent)."""
    lines: list[str] = []
    for item in result.get("results") or result.get("charges") or []:
        label = f"Fatura #{item.get('bill_id')} — {item.get('amount_brl')}"
        outcome = item.get("result") or item.get("status") or ""
        lines.append(f"• {label} ({outcome})")
        payment_data = item.get("payment_data") or {}
        if item.get("result") in {"manual_required", "no_barcode", "insufficient_balance"}:
            if payment_data.get("linha_digitavel"):
                lines.append(f"  Boleto: <code>{payment_data['linha_digitavel']}</code>")
            if payment_data.get("pix_copia_cola"):
                lines.append(f"  PIX: <code>{payment_data['pix_copia_cola']}</code>")
            if item.get("message"):
                lines.append(f"  ↳ {item['message']}")
    return lines
