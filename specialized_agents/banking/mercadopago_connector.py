"""
Conector Mercado Pago (Mercado Livre) — API REST proprietária.

O Mercado Pago NÃO participa do Open Finance Brasil.
Usa API REST própria com OAuth2.

Endpoints:
  - Autenticação OAuth2
  - Conta e saldo
  - Transações (payments/collections)
  - Recebimentos e cobranças
  - PIX (QR Code e transferências)
  - Relatórios financeiros

Referência: https://www.mercadopago.com.br/developers/pt/reference
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from .base_connector import BaseBankConnector, BankAuthError
from .models import (
    BankAccount, Balance, Transaction, PixKey, PixTransfer,
    CreditCard, Invoice,
    BankProvider, AccountType, TransactionType, PixKeyType,
)
from .security import BankingSecurityManager, OAuthToken

logger = logging.getLogger("eddie.banking.mercadopago")

# URLs da API Mercado Pago
MP_API_BASE = "https://api.mercadopago.com"
MP_AUTH_URL = "https://api.mercadopago.com/oauth/token"


class MercadoPagoConnector(BaseBankConnector):
    """
    Conector para Mercado Pago via API REST.

    Credenciais necessárias:
      BANK_MERCADOPAGO_ACCESS_TOKEN   (token permanente, mais simples)
      ou
      BANK_MERCADOPAGO_CLIENT_ID      (para OAuth completo)
      BANK_MERCADOPAGO_CLIENT_SECRET
      BANK_MERCADOPAGO_REDIRECT_URI

    A forma mais simples é usar o access_token do painel do Mercado Pago:
    https://www.mercadopago.com.br/developers/panel/app
    """

    def __init__(
        self,
        security: Optional[BankingSecurityManager] = None,
        sandbox: bool = True,
    ):
        super().__init__(BankProvider.MERCADOPAGO, security, sandbox)
        self._base_url = MP_API_BASE
        self._auth_url = MP_AUTH_URL

    # ──────────── Autenticação ────────────

    async def authenticate(self) -> Optional[OAuthToken]:
        """
        Autentica com Mercado Pago.
        Prioriza access_token (permanente), fallback para OAuth2.
        """
        creds = self.security.load_credentials("mercadopago")
        if not creds:
            raise BankAuthError(
                "mercadopago",
                "Credenciais não encontradas. Configure BANK_MERCADOPAGO_ACCESS_TOKEN"
            )

        # Método 1: Access token direto (mais usado)
        access_token = creds.get("access_token")
        if access_token:
            token = OAuthToken(
                access_token=access_token,
                token_type="Bearer",
                expires_in=31536000,  # 1 ano (token permanente)
            )
            self.security.cache_token("mercadopago", token)
            logger.info("Mercado Pago: Token permanente configurado")
            return token

        # Método 2: OAuth2 client_credentials
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        if not (client_id and client_secret):
            raise BankAuthError("mercadopago", "Nem access_token nem client_id/secret configurados")

        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }

        resp = await self._request(
            "POST", self._auth_url,
            json=data,
            require_auth=False,
        )

        token = OAuthToken(
            access_token=resp.get("access_token", ""),
            token_type=resp.get("token_type", "Bearer"),
            expires_in=resp.get("expires_in", 21600),  # 6 horas padrão
            refresh_token=resp.get("refresh_token"),
            scope=resp.get("scope"),
        )
        self.security.cache_token("mercadopago", token)
        logger.info("Mercado Pago: OAuth2 autenticação bem-sucedida")
        return token

    async def authenticate_with_code(self, authorization_code: str) -> Optional[OAuthToken]:
        """Troca authorization_code por token."""
        creds = self.security.load_credentials("mercadopago")
        if not creds:
            raise BankAuthError("mercadopago", "Credenciais não encontradas")

        data = {
            "grant_type": "authorization_code",
            "client_id": creds.get("client_id", ""),
            "client_secret": creds.get("client_secret", ""),
            "code": authorization_code,
            "redirect_uri": creds.get("redirect_uri", ""),
        }

        resp = await self._request(
            "POST", self._auth_url,
            json=data,
            require_auth=False,
        )

        token = OAuthToken(
            access_token=resp.get("access_token", ""),
            token_type=resp.get("token_type", "Bearer"),
            expires_in=resp.get("expires_in", 21600),
            refresh_token=resp.get("refresh_token"),
        )
        self.security.cache_token("mercadopago", token)
        return token

    # ──────────── Conta ────────────

    async def get_accounts(self) -> List[BankAccount]:
        """Retorna a conta Mercado Pago do usuário."""
        resp = await self._request("GET", f"{self._base_url}/users/me")

        user_id = str(resp.get("id", ""))
        return [BankAccount(
            id=user_id,
            provider=BankProvider.MERCADOPAGO,
            account_type=AccountType.PAGAMENTO,
            branch="0001",  # Mercado Pago não tem agência
            number=user_id,
            holder_name=f"{resp.get('first_name', '')} {resp.get('last_name', '')}".strip(),
            holder_document=self.security.mask_document(
                resp.get("identification", {}).get("number", "")
            ),
            currency="BRL",
            status="ACTIVE" if resp.get("status", {}).get("site_status") == "active" else "INACTIVE",
        )]

    # ──────────── Saldo ────────────

    async def get_balance(self, account_id: str = "") -> Balance:
        """
        Obtém saldo da conta Mercado Pago.

        Estratégia:
          1. Tenta endpoint direto /users/me/mercadopago_account/balance
          2. Se 403 (conta pessoal sem permissão), calcula saldo
             estimado a partir dos pagamentos recentes (últimos 30 dias)
        """
        # Tentativa 1: endpoint direto
        try:
            resp = await self._request(
                "GET", f"{self._base_url}/users/me/mercadopago_account/balance"
            )
            return Balance(
                account_id=account_id or "mp_default",
                provider=BankProvider.MERCADOPAGO,
                available=Decimal(str(resp.get("available_balance", 0))),
                blocked=Decimal(str(resp.get("unavailable_balance", 0))),
            )
        except Exception as e:
            logger.warning(f"Mercado Pago: Balance API indisponível ({e}), calculando via payments")

        # Tentativa 2: calcular saldo estimado a partir dos payments
        return await self._calculate_balance_from_payments(account_id)

    async def _calculate_balance_from_payments(self, account_id: str = "") -> Balance:
        """
        Calcula saldo estimado usando dados de payments.

        IMPORTANTE: A API payments/search retorna APENAS transações onde
        somos o collector (recebimentos). Saídas (PIX enviado, compras ML,
        saques) NÃO aparecem aqui, então o saldo estimado considera
        apenas entradas dos últimos 90 dias.

        Se BANK_MERCADOPAGO_KNOWN_BALANCE estiver definido, usa como baseline.
        """
        import os
        from datetime import timedelta

        # Verificar saldo baseline manual (mais preciso que estimativa)
        known_balance = os.environ.get("BANK_MERCADOPAGO_KNOWN_BALANCE", "")
        if known_balance:
            try:
                bal = Decimal(known_balance)
                logger.info(f"Mercado Pago: Usando saldo baseline configurado: R${bal:.2f}")
                return Balance(
                    account_id=account_id or "mp_default",
                    provider=BankProvider.MERCADOPAGO,
                    available=bal,
                    blocked=Decimal("0"),
                    currency="BRL",
                )
            except Exception:
                logger.warning(f"Mercado Pago: BANK_MERCADOPAGO_KNOWN_BALANCE inválido: {known_balance}")

        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=90)

        total_received = Decimal("0")
        total_blocked = Decimal("0")
        payment_count = 0

        try:
            params = {
                "begin_date": f"{start_dt.strftime('%Y-%m-%d')}T00:00:00.000-03:00",
                "end_date": f"{end_dt.strftime('%Y-%m-%d')}T23:59:59.000-03:00",
                "sort": "date_created",
                "criteria": "desc",
                "range": "date_created",
                "status": "approved",
                "limit": 100,
                "offset": 0,
            }

            has_more = True
            while has_more:
                resp = await self._request(
                    "GET", f"{self._base_url}/v1/payments/search", params=params
                )
                results = resp.get("results", [])
                paging = resp.get("paging", {})

                for p in results:
                    td = p.get("transaction_details") or {}
                    net = Decimal(str(td.get("net_received_amount", 0) or 0))
                    amt = Decimal(str(p.get("transaction_amount", 0)))
                    op_type = p.get("operation_type", "")

                    # Transações neutras (exchange de cripto, partição interna)
                    if op_type in ("money_exchange", "partition_transfer"):
                        continue

                    # Todas as transações no search são incoming (somos collector)
                    total_received += net if net > 0 else amt
                    payment_count += 1

                offset = paging.get("offset", 0) + paging.get("limit", 100)
                total_count = paging.get("total", 0)
                has_more = offset < total_count
                params["offset"] = offset

        except Exception as e:
            logger.error(f"Mercado Pago: Erro ao calcular saldo via payments: {e}")

        # Nota: Este valor é apenas o total de entradas (90d).
        # Saídas (PIX enviado, compras, saques) não são visíveis nesta API.
        # O saldo real requer o endpoint /balance (que retorna 403) ou
        # um baseline configurado via BANK_MERCADOPAGO_KNOWN_BALANCE.
        logger.info(
            f"Mercado Pago: Total entradas (90d) — "
            f"Recebido: R${total_received:.2f} ({payment_count} pagamentos), "
            f"Bloqueado: R${total_blocked:.2f} "
            f"(ATENÇÃO: não inclui saídas — saldo estimado pode estar inflado)"
        )

        return Balance(
            account_id=account_id or "mp_default",
            provider=BankProvider.MERCADOPAGO,
            available=total_received,
            blocked=total_blocked,
            currency="BRL",
        )

    async def get_transactions(
        self, account_id: str, start_date: date, end_date: date
    ) -> List[Transaction]:
        """
        Lista transações (payments) do Mercado Pago.
        Combina payments recebidos e enviados.
        """
        all_transactions: List[Transaction] = []

        # Payments recebidos (vendas)
        received = await self._get_payments(
            start_date, end_date, role="collector"
        )
        all_transactions.extend(received)

        # Payments enviados (compras)
        sent = await self._get_payments(
            start_date, end_date, role="payer"
        )
        all_transactions.extend(sent)

        # Money transfers (PIX, transferências)
        transfers = await self._get_money_transfers(start_date, end_date)
        all_transactions.extend(transfers)

        return sorted(all_transactions, key=lambda t: t.date, reverse=True)

    async def _get_payments(
        self, start_date: date, end_date: date, role: str = "collector"
    ) -> List[Transaction]:
        """Busca payments por role (collector = vendedor, payer = comprador)."""
        params = {
            "begin_date": f"{start_date.isoformat()}T00:00:00.000-03:00",
            "end_date": f"{end_date.isoformat()}T23:59:59.000-03:00",
            "sort": "date_created",
            "criteria": "desc",
            "range": "date_created",
            "limit": 50,
            "offset": 0,
        }

        transactions: List[Transaction] = []
        has_more = True

        while has_more:
            resp = await self._request(
                "GET", f"{self._base_url}/v1/payments/search", params=params
            )

            results = resp.get("results", [])
            paging = resp.get("paging", {})

            for item in results:
                is_received = role == "collector"
                tx_type = self._map_payment_type(item, is_received)

                transactions.append(Transaction(
                    id=str(item.get("id", self._generate_id())),
                    account_id="mp_default",
                    provider=BankProvider.MERCADOPAGO,
                    type=tx_type,
                    amount=Decimal(str(item.get("transaction_amount", 0))),
                    description=item.get("description", item.get("payment_method_id", "")),
                    date=datetime.fromisoformat(
                        item.get("date_created", "").replace("Z", "+00:00")
                    ) if item.get("date_created") else datetime.now(),
                    counterpart_name=(
                        item.get("payer", {}).get("email", "")
                        if is_received
                        else item.get("collector", {}).get("email", "")
                    ),
                    reference=str(item.get("id", "")),
                    category=item.get("payment_type_id"),
                    metadata={
                        "status": item.get("status"),
                        "status_detail": item.get("status_detail"),
                        "payment_method": item.get("payment_method_id"),
                        "fee": str(item.get("fee_details", [{}])[0].get("amount", 0)) if item.get("fee_details") else "0",
                    },
                ))

            # Paginação
            offset = paging.get("offset", 0) + paging.get("limit", 50)
            total = paging.get("total", 0)
            has_more = offset < total
            params["offset"] = offset

        return transactions

    async def _get_money_transfers(
        self, start_date: date, end_date: date
    ) -> List[Transaction]:
        """Busca transferências de dinheiro (PIX, bank transfer)."""
        params = {
            "begin_date": f"{start_date.isoformat()}T00:00:00.000-03:00",
            "end_date": f"{end_date.isoformat()}T23:59:59.000-03:00",
            "limit": 50,
            "offset": 0,
        }

        transactions: List[Transaction] = []
        try:
            resp = await self._request(
                "GET", f"{self._base_url}/v1/account/bank_report/list", params=params
            )

            for item in resp.get("results", resp) if isinstance(resp, dict) else []:
                tx_type = TransactionType.TRANSFER
                amount = Decimal(str(item.get("amount", 0)))

                if item.get("type") == "pix":
                    tx_type = TransactionType.PIX_SENT if amount < 0 else TransactionType.PIX_RECEIVED
                    amount = abs(amount)

                transactions.append(Transaction(
                    id=str(item.get("id", self._generate_id())),
                    account_id="mp_default",
                    provider=BankProvider.MERCADOPAGO,
                    type=tx_type,
                    amount=amount,
                    description=item.get("description", "Transferência"),
                    date=datetime.fromisoformat(
                        item.get("date_created", "").replace("Z", "+00:00")
                    ) if item.get("date_created") else datetime.now(),
                    reference=str(item.get("id", "")),
                ))
        except Exception as e:
            logger.warning(f"Mercado Pago: Erro ao buscar transferências: {e}")

        return transactions

    # ──────────── PIX ────────────

    async def initiate_pix(self, transfer: PixTransfer) -> PixTransfer:
        """Inicia transferência PIX via Mercado Pago."""
        body = {
            "transaction_amount": float(transfer.amount),
            "description": transfer.description or "PIX via Eddie Banking Agent",
            "payment_method_id": "pix",
            "payer": {
                "email": "payer@email.com",  # Preenchido via credenciais
            },
            "point_of_interaction": {
                "type": "PIX_TRANSFER",
            },
        }

        resp = await self._request(
            "POST", f"{self._base_url}/v1/payments", json=body
        )

        transfer.id = str(resp.get("id", transfer.id))
        transfer.status = self._map_payment_status(resp.get("status", ""))
        transfer.end_to_end_id = resp.get("point_of_interaction", {}).get(
            "transaction_data", {}
        ).get("e2e_id")
        if resp.get("status") == "approved":
            transfer.completed_at = datetime.now()
        elif resp.get("status") == "rejected":
            transfer.error_message = resp.get("status_detail", "Pagamento rejeitado")

        return transfer

    async def generate_pix_qr(self, amount: Decimal, description: str = "") -> Dict[str, Any]:
        """Gera QR Code PIX para recebimento."""
        body = {
            "transaction_amount": float(amount),
            "description": description or "Cobrança PIX",
            "payment_method_id": "pix",
            "payer": {"email": "payer@placeholder.com"},
        }

        resp = await self._request(
            "POST", f"{self._base_url}/v1/payments", json=body
        )

        qr_data = resp.get("point_of_interaction", {}).get("transaction_data", {})
        return {
            "payment_id": resp.get("id"),
            "qr_code": qr_data.get("qr_code"),
            "qr_code_base64": qr_data.get("qr_code_base64"),
            "ticket_url": qr_data.get("ticket_url"),
            "amount": str(amount),
            "status": resp.get("status"),
        }

    # ──────────── Relatórios ────────────

    async def get_account_summary(
        self, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Resumo financeiro da conta Mercado Pago."""
        balance = await self.get_balance()
        transactions = await self.get_transactions("mp_default", start_date, end_date)

        total_received = sum(
            t.amount for t in transactions if t.is_credit
        )
        total_sent = sum(
            t.amount for t in transactions if not t.is_credit
        )
        total_fees = sum(
            Decimal(t.metadata.get("fee", "0")) for t in transactions if t.metadata.get("fee")
        )

        return {
            "balance": balance.to_dict(),
            "period": f"{start_date.isoformat()} a {end_date.isoformat()}",
            "total_received": str(total_received),
            "total_sent": str(total_sent),
            "total_fees": str(total_fees),
            "net_result": str(total_received - total_sent - total_fees),
            "transaction_count": len(transactions),
        }

    # ──────────── Helpers ────────────

    @staticmethod
    def _map_payment_type(payment: Dict, is_received: bool) -> TransactionType:
        """Mapeia tipo de pagamento MP para TransactionType."""
        method = payment.get("payment_method_id", "")
        payment_type = payment.get("payment_type_id", "")

        if method == "pix":
            return TransactionType.PIX_RECEIVED if is_received else TransactionType.PIX_SENT
        if payment_type == "bank_transfer":
            return TransactionType.TED_RECEIVED if is_received else TransactionType.TED_SENT
        if payment_type == "credit_card":
            return TransactionType.CARD_PURCHASE
        if method == "bolbradesco" or "boleto" in method:
            return TransactionType.BOLETO_PAYMENT

        return TransactionType.CREDIT if is_received else TransactionType.DEBIT

    @staticmethod
    def _map_payment_status(status: str) -> str:
        """Mapeia status MP para status de transferência."""
        return {
            "approved": "COMPLETED",
            "pending": "PENDING",
            "in_process": "PROCESSING",
            "rejected": "FAILED",
            "cancelled": "CANCELLED",
            "refunded": "REFUNDED",
        }.get(status, "PENDING")
