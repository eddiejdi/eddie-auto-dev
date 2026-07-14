from __future__ import annotations

import pytest

from specialized_agents import conube_billing


LINHA_FORMATADA = "23793.38128 60007.827136 95000.063305 9 91340000025000"
LINHA_DIGITOS = "23793381286000782713695000063305991340000025000"
PIX_EMV = (
    "00020101021226880014br.gov.bcb.pix2566qrcodes-pix.vindi.com.br/v2/"
    "cobv/9d36b84fc70b4b1cb1a7a2e113b505415204000053039865802BR5906CONUBE"
    "6009SAO PAULO62070503***6304ABCD"
)


class FakeAgent:
    def __init__(self, charges: list[dict] | None = None, authenticated: bool = True):
        self._charges = charges or []
        self._authenticated = authenticated

    def login(self):
        return {"authenticated": self._authenticated, "failure_reason": "" if self._authenticated else "boom"}

    def _authenticated_api_get(self, path: str, *, api_version: str = "client", timeout: float = 25):
        assert path == "cobrancas"
        return {"docs": self._charges, "total": len(self._charges)}


class FakePayer:
    def __init__(self, ok: bool = True):
        self.ok = ok
        self.calls: list[dict] = []

    def pay_barcode(self, linha_digitavel: str, *, amount_cents: int, description: str = ""):
        self.calls.append({"linha": linha_digitavel, "amount_cents": amount_cents})
        return {"ok": self.ok, "receipt_screenshot": "/tmp/fake.png"}


def _pending_charge(amount: int = 25000, status: str = "pending") -> dict:
    return {
        "id": 999111222,
        "status": status,
        "amount": amount,
        "billing_at": "2026-07-30T03:00:00.000Z",
        "due_at": "2026-08-05T02:59:59.000Z",
        "url": "https://app.vindi.com.br/customer/bills/999111222?token=tok",
    }


# ── extract_payment_data ──────────────────────────────────────────────────────

def test_extract_payment_data_linha_formatada() -> None:
    html = f"<div>Linha digitável</div><span>{LINHA_FORMATADA}</span>"
    data = conube_billing.extract_payment_data(html)
    assert data["linha_digitavel"] == LINHA_DIGITOS


def test_extract_payment_data_linha_sem_formatacao() -> None:
    data = conube_billing.extract_payment_data(f"<input value='{LINHA_DIGITOS}'>")
    assert data["linha_digitavel"] == LINHA_DIGITOS


def test_extract_payment_data_pix() -> None:
    data = conube_billing.extract_payment_data(f"<textarea>{PIX_EMV}</textarea>")
    assert data["pix_copia_cola"] == PIX_EMV


def test_extract_payment_data_fatura_cartao_sem_boleto() -> None:
    html = "<p>Método de pagamento<br>Cartão de crédito<br>Recebido em 30/06/2026 (#526217195)</p>"
    data = conube_billing.extract_payment_data(html)
    assert data["linha_digitavel"] is None
    assert data["pix_copia_cola"] is None


# ── detecção ─────────────────────────────────────────────────────────────────

def test_pending_charges_filtra_pagas_e_canceladas() -> None:
    charges = [
        {"status": "paid"},
        {"status": "canceled"},
        {"status": "pending"},
        {"status": "Review"},
    ]
    assert len(conube_billing.pending_charges(charges)) == 2


def test_format_brl() -> None:
    assert conube_billing.format_brl(25000) == "R$ 250,00"
    assert conube_billing.format_brl(123456789) == "R$ 1.234.567,89"


def test_fetch_pending_billing_sem_login() -> None:
    result = conube_billing.fetch_pending_billing(FakeAgent(authenticated=False))
    assert result["status"] == "error"
    assert result["pending_count"] == 0


def test_fetch_pending_billing_com_pendencia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        conube_billing,
        "fetch_bill_payment_data",
        lambda url: {"linha_digitavel": LINHA_DIGITOS, "pix_copia_cola": None, "boleto_url": None},
    )
    result = conube_billing.fetch_pending_billing(FakeAgent([_pending_charge()]))
    assert result["pending_count"] == 1
    assert result["total_amount_cents"] == 25000
    assert result["charges"][0]["payment_data"]["linha_digitavel"] == LINHA_DIGITOS


# ── pagamento ────────────────────────────────────────────────────────────────

def _patch_billing(monkeypatch: pytest.MonkeyPatch, *, balance_cents: int | None = 100000) -> None:
    monkeypatch.setattr(
        conube_billing,
        "fetch_bill_payment_data",
        lambda url: {"linha_digitavel": LINHA_DIGITOS, "pix_copia_cola": PIX_EMV, "boleto_url": None},
    )
    monkeypatch.setattr(
        conube_billing,
        "check_mercadopago_balance",
        lambda: {"available_cents": balance_cents, "available_brl": conube_billing.format_brl(balance_cents or 0)},
    )


def test_pay_pending_charges_sucesso(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_billing(monkeypatch)
    payer = FakePayer(ok=True)
    result = conube_billing.pay_pending_charges(FakeAgent([_pending_charge()]), payer=payer)
    assert result["status"] == "ok"
    assert result["processed"] == 1
    assert payer.calls[0]["linha"] == LINHA_DIGITOS
    assert payer.calls[0]["amount_cents"] == 25000


def test_pay_pending_charges_dry_run_nao_paga(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_billing(monkeypatch)
    payer = FakePayer()
    result = conube_billing.pay_pending_charges(
        FakeAgent([_pending_charge()]), payer=payer, dry_run=True
    )
    assert result["processed"] == 0
    assert result["results"][0]["result"] == "dry_run"
    assert payer.calls == []


def test_pay_pending_charges_saldo_insuficiente(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_billing(monkeypatch, balance_cents=1000)
    payer = FakePayer()
    result = conube_billing.pay_pending_charges(FakeAgent([_pending_charge()]), payer=payer)
    assert result["results"][0]["result"] == "insufficient_balance"
    assert payer.calls == []


def test_pay_pending_charges_sem_linha_digitavel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        conube_billing,
        "fetch_bill_payment_data",
        lambda url: {"linha_digitavel": None, "pix_copia_cola": None, "boleto_url": None},
    )
    monkeypatch.setattr(
        conube_billing,
        "check_mercadopago_balance",
        lambda: {"available_cents": 100000, "available_brl": "R$ 1.000,00"},
    )
    result = conube_billing.pay_pending_charges(FakeAgent([_pending_charge()]), payer=FakePayer())
    assert result["results"][0]["result"] == "no_barcode"


def test_pay_pending_charges_payer_indisponivel(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_billing(monkeypatch)

    class BrokenPayer:
        def pay_barcode(self, *args, **kwargs):
            raise RuntimeError("sessão expirada")

    result = conube_billing.pay_pending_charges(FakeAgent([_pending_charge()]), payer=BrokenPayer())
    assert result["status"] == "warning"
    assert result["results"][0]["result"] == "manual_required"
    assert "sessão expirada" in result["results"][0]["message"]


def test_pay_pending_charges_sem_pendencia(monkeypatch: pytest.MonkeyPatch) -> None:
    result = conube_billing.pay_pending_charges(FakeAgent([]), payer=FakePayer())
    assert result["status"] == "ok"
    assert result["processed"] == 0


# ── telegram ─────────────────────────────────────────────────────────────────

def test_format_billing_telegram_lines_manual() -> None:
    result = {
        "results": [
            {
                "bill_id": 1,
                "amount_brl": "R$ 250,00",
                "result": "manual_required",
                "message": "payer off",
                "payment_data": {"linha_digitavel": LINHA_DIGITOS, "pix_copia_cola": PIX_EMV},
            }
        ]
    }
    lines = conube_billing.format_billing_telegram_lines(result)
    joined = "\n".join(lines)
    assert LINHA_DIGITOS in joined
    assert PIX_EMV in joined
    assert "payer off" in joined
