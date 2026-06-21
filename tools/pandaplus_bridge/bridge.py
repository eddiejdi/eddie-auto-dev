"""Bridge principal — orquestra Tuya MQ, Telegram e endpoint HTTP de decisão.

Eventos relevantes da fechadura PandaPlus:
- ``unlock_request`` (Integer > 0): alguém pediu abertura remota.
- ``alarm_lock`` (Enum ``wrong_*``): tentativa falha de credencial.

Para cada evento relevante, gera um *request_token* único, envia mensagem
Telegram e (se ENABLE_REPLY ativo) registra estado pendente aguardando
decisão via endpoint HTTP local.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aiohttp import web

from .config import BridgeConfig, load_tuya_tokens
from .telegram_client import TelegramSender
from .tuya_client import TuyaBridgeClient, TuyaStatusEvent

logger = logging.getLogger(__name__)

TUYA_RETRY_SECONDS = 30
TUYA_HEALTHCHECK_SECONDS = 120
TUYA_POLL_SECONDS = 5

# DPs que disparam notificação. unlock_request > 0 indica pedido ativo.
RELEVANT_CODES = frozenset({"unlock_request", "alarm_lock"})
# Códigos de alarme considerados como "alguém na porta".
DOOR_ALARM_VALUES = frozenset({
    "wrong_finger",
    "wrong_password",
    "wrong_card",
    "wrong_face",
    "key_in",
})


@dataclass
class PendingRequest:
    """Pedido de abertura aguardando decisão.

    Attributes:
        token: Token único do pedido (curto, URL-safe).
        device_id: ID da fechadura.
        created_at: Timestamp Unix de criação.
        ttl_seconds: TTL configurado.
        telegram_message_id: ID da mensagem Telegram para edição posterior.
        chat_id: Chat onde a mensagem foi postada.
        unlock_request_seconds: Valor inicial de unlock_request.
        alarm: Código de alarme se aplicável.
        decided: Decisão final (None=pendente, True=aprovado, False=negado).
        decided_by: User ID que decidiu.
        decided_at: Timestamp da decisão.
    """

    token: str
    device_id: str
    created_at: float
    ttl_seconds: int
    telegram_message_id: int = 0
    chat_id: int = 0
    unlock_request_seconds: int = 0
    alarm: str | None = None
    decided: bool | None = None
    decided_by: int = 0
    decided_at: float = 0.0

    def is_expired(self, now: float | None = None) -> bool:
        """Retorna True se o pedido passou do TTL."""
        if now is None:
            now = time.time()
        return (now - self.created_at) > self.ttl_seconds


class PandaplusBridge:
    """Orquestrador: consome eventos Tuya e envia/recebe decisões via Telegram.

    Args:
        config: Configuração carregada de env.
    """

    def __init__(self, config: BridgeConfig) -> None:
        self._cfg = config
        self._pending: dict[str, PendingRequest] = {}
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._tuya: TuyaBridgeClient | None = None
        self._telegram: TelegramSender | None = None
        self._event_queue: asyncio.Queue[TuyaStatusEvent] = asyncio.Queue()
        self._http_runner: web.AppRunner | None = None
        self._tuya_supervisor_task: asyncio.Task | None = None
        self._runtime_tokens_path = (
            self._cfg.ha_storage_path.parent / "tuya_tokens_runtime.json"
        )
        # deduplicação: (code, str(value)) → timestamp do último disparo
        self._last_event_seen: dict[tuple[str, str], float] = {}

    async def start(self) -> None:
        """Inicia bridge: Tuya MQ, HTTP server, Telegram sender e consumer."""
        logger.info(
            "Iniciando bridge PandaPlus (device=%s, observe_only=%s)",
            self._cfg.device_id,
            self._cfg.observe_only,
        )

        # Telegram sender (async context)
        self._telegram = await TelegramSender(self._cfg.telegram_bot_token).__aenter__()

        self._tuya_supervisor_task = asyncio.create_task(
            self._tuya_supervisor_loop()
        )

        # HTTP listener (apenas se ENABLE_REPLY)
        if not self._cfg.observe_only:
            await self._start_http_server()

        # Mensagem inicial de status
        try:
            await self._telegram.send_event(
                self._cfg.telegram_chat_id,
                f"🟢 *PandaPlus bridge online*\n"
                f"device: `{self._cfg.device_id}`\n"
                f"modo: "
                f"{'observação' if self._cfg.observe_only else 'aprovação ativa'}",
            )
        except Exception:  # noqa: BLE001
            logger.exception("falha ao enviar mensagem inicial Telegram")

        # Consumer loop
        await self._consumer_loop()

    async def stop(self) -> None:
        """Encerra bridge limpando recursos."""
        self._stop_event.set()
        if self._tuya_supervisor_task is not None:
            self._tuya_supervisor_task.cancel()
            await asyncio.gather(self._tuya_supervisor_task, return_exceptions=True)
            self._tuya_supervisor_task = None
        if self._tuya is not None:
            await asyncio.to_thread(self._tuya.stop)
            self._tuya = None
        if self._http_runner is not None:
            await self._http_runner.cleanup()
        if self._telegram is not None:
            await self._telegram.__aexit__(None, None, None)
        logger.info("Bridge encerrado")

    async def _tuya_supervisor_loop(self) -> None:
        """Mantém conexão Tuya ativa com retry automático quando houver falhas."""
        while not self._stop_event.is_set():
            if self._tuya is None:
                try:
                    await self._connect_tuya()
                    logger.info("Conexão Tuya estabelecida")
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Falha ao conectar Tuya: %s. Tentando novamente em %ss",
                        exc,
                        TUYA_RETRY_SECONDS,
                    )
                    await self._sleep_or_stop(TUYA_RETRY_SECONDS)
                    continue

            assert self._tuya is not None
            try:
                await asyncio.to_thread(self._tuya.session_check)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Sessão Tuya inválida: %s", exc)
                await self._disconnect_tuya()
                await self._sleep_or_stop(TUYA_RETRY_SECONDS)
                continue

            await self._sleep_or_stop(TUYA_HEALTHCHECK_SECONDS)

    async def _connect_tuya(self) -> None:
        """Cria cliente Tuya e inicia subscrição MQ."""
        tokens = self._load_best_tokens()
        client = TuyaBridgeClient(
            client_id=self._cfg.tuya_client_id,
            user_code=tokens["user_code"],
            terminal_id=tokens["terminal_id"],
            endpoint=tokens["endpoint"],
            token_info=tokens["token_info"],
            target_device_id=self._cfg.device_id,
            event_queue=self._event_queue,
            token_update_callback=self._persist_runtime_tokens,
        )
        await asyncio.to_thread(client.start)
        self._tuya = client

    async def _disconnect_tuya(self) -> None:
        """Encerra cliente Tuya atual, se existir."""
        if self._tuya is None:
            return
        await asyncio.to_thread(self._tuya.stop)
        self._tuya = None

    async def _sleep_or_stop(self, seconds: int) -> None:
        """Dorme com interrupção antecipada quando o bridge for finalizado."""
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            return

    def _load_best_tokens(self) -> dict:
        """Carrega tokens preferindo runtime cache quando mais novo que o HA."""
        tokens = load_tuya_tokens(self._cfg.ha_storage_path)
        runtime = self._load_runtime_tokens(self._runtime_tokens_path)
        if runtime is None:
            return tokens

        file_exp = self._token_expiry_ms(tokens["token_info"])
        runtime_exp = self._token_expiry_ms(runtime)
        if runtime_exp > file_exp:
            logger.info("Usando token runtime mais novo que core.config_entries")
            tokens["token_info"] = runtime
        return tokens

    def _persist_runtime_tokens(self, token_info: dict[str, Any]) -> None:
        """Persiste token atualizado em arquivo local para reuso após restart."""
        try:
            payload = json.dumps(token_info, ensure_ascii=True)
            self._runtime_tokens_path.write_text(payload, encoding="utf-8")
        except Exception:  # noqa: BLE001
            logger.exception("falha ao persistir token runtime")

    @staticmethod
    def _load_runtime_tokens(path: Path) -> dict[str, Any] | None:
        """Lê token runtime salvo em disco.

        Returns:
            Dicionário do token ou None quando ausente/inválido.
        """
        if not path.exists():
            return None
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(content, dict):
                return None
            required = {"access_token", "refresh_token", "expire_time", "t", "uid"}
            if not required.issubset(set(content.keys())):
                return None
            return content
        except Exception:  # noqa: BLE001
            logger.warning("token runtime inválido em %s", path)
            return None

    @staticmethod
    def _token_expiry_ms(token_info: dict[str, Any]) -> int:
        """Calcula timestamp de expiração em milissegundos."""
        try:
            issued_ms = int(token_info.get("t", 0))
            ttl_s = int(token_info.get("expire_time", 0))
            return issued_ms + ttl_s * 1000
        except (TypeError, ValueError):
            return 0

    # --- consumer ---

    async def _consumer_loop(self) -> None:
        """Loop que processa eventos da fila Tuya."""
        while not self._stop_event.is_set():
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(), timeout=TUYA_POLL_SECONDS
                )
            except asyncio.TimeoutError:
                await self._poll_tuya_fallback()
                await self._gc_pending()
                continue
            await self._handle_event(event)

    async def _poll_tuya_fallback(self) -> None:
        """Executa polling leve para locks que não emitem todos os eventos no MQ."""
        if self._tuya is None:
            return
        try:
            events = await self._tuya.poll_status_changes(RELEVANT_CODES)
        except Exception:  # noqa: BLE001
            logger.exception("falha no polling de fallback Tuya")
            return

        for event in events:
            await self._handle_event(event)

    async def _handle_event(self, event: TuyaStatusEvent) -> None:
        """Processa um evento Tuya: filtra, notifica e enfileira pendência.

        Args:
            event: Evento bruto recebido do MQ/Manager.
        """
        if event.code not in RELEVANT_CODES:
            logger.debug(
                "evento ignorado code=%s value=%s", event.code, event.value
            )
            return

        # Deduplicar eventos idênticos chegando via múltiplos listeners (raw + manager)
        dedup_key = (event.code, str(event.value))
        now = time.time()
        last = self._last_event_seen.get(dedup_key, 0.0)
        if now - last < 5.0:
            logger.debug("evento deduplicado code=%s value=%s (%.1fs atrás)", event.code, event.value, now - last)
            return
        self._last_event_seen[dedup_key] = now

        is_alarm = event.code == "alarm_lock" and event.value in DOOR_ALARM_VALUES
        is_request = event.code == "unlock_request" and self._coerce_int(event.value) > 0

        if not (is_alarm or is_request):
            return

        token = secrets.token_urlsafe(8)
        pending = PendingRequest(
            token=token,
            device_id=event.device_id,
            created_at=time.time(),
            ttl_seconds=self._cfg.request_ttl_seconds,
            unlock_request_seconds=(
                self._coerce_int(event.value) if is_request else 0
            ),
            alarm=event.value if is_alarm else None,
        )

        try:
            assert self._telegram is not None
            msg = await self._telegram.send_unlock_request(
                self._cfg.telegram_chat_id,
                request_token=token,
                unlock_request_seconds=pending.unlock_request_seconds,
                alarm=pending.alarm,
                observe_only=self._cfg.observe_only,
            )
            pending.telegram_message_id = msg.get("message_id", 0)
            pending.chat_id = self._cfg.telegram_chat_id
        except Exception:  # noqa: BLE001
            logger.exception("falha ao enviar Telegram para token=%s", token)

        async with self._lock:
            self._pending[token] = pending
        logger.info(
            "pedido registrado token=%s code=%s value=%s",
            token,
            event.code,
            event.value,
        )

    async def _gc_pending(self) -> None:
        """Remove pedidos expirados."""
        async with self._lock:
            expired = [t for t, p in self._pending.items() if p.is_expired()]
            for t in expired:
                p = self._pending.pop(t)
                logger.info("pedido expirado token=%s", t)
                if p.telegram_message_id and self._telegram is not None:
                    try:
                        await self._telegram.edit_message(
                            p.chat_id,
                            p.telegram_message_id,
                            f"⌛ *Pedido expirado* (token `{t}`)",
                        )
                    except Exception:  # noqa: BLE001
                        logger.debug("edit expired falhou para %s", t)

    @staticmethod
    def _coerce_int(value: Any) -> int:
        """Converte valor para int de forma tolerante."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    # --- HTTP server (modo reply ativo) ---

    async def _start_http_server(self) -> None:
        """Inicia servidor HTTP para receber decisões do bot Telegram."""
        app = web.Application()
        app.router.add_post("/reply", self._http_reply_handler)
        app.router.add_get("/health", self._http_health_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(
            runner, self._cfg.reply_listen_host, self._cfg.reply_listen_port
        )
        await site.start()
        self._http_runner = runner
        logger.info(
            "HTTP reply listener em %s:%d",
            self._cfg.reply_listen_host,
            self._cfg.reply_listen_port,
        )

    async def _http_health_handler(self, _: web.Request) -> web.Response:
        return web.json_response({"ok": True, "pending": len(self._pending)})

    async def _http_reply_handler(self, request: web.Request) -> web.Response:
        """Recebe decisão JSON ``{token, decision, user_id}`` e executa.

        Returns:
            JSON com resultado da operação.
        """
        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001
            return web.json_response(
                {"error": "json inválido"}, status=400
            )

        token = str(payload.get("token", ""))
        decision_raw = str(payload.get("decision", "")).lower()
        user_id = self._coerce_int(payload.get("user_id"))

        if not token or decision_raw not in ("approve", "deny"):
            return web.json_response(
                {"error": "campos obrigatórios: token, decision"},
                status=400,
            )
        if user_id not in self._cfg.allowed_user_ids:
            logger.warning(
                "tentativa não autorizada token=%s user_id=%s", token, user_id
            )
            return web.json_response(
                {"error": "user_id não autorizado"}, status=403
            )

        async with self._lock:
            pending = self._pending.get(token)
        if pending is None:
            return web.json_response(
                {"error": "token desconhecido ou expirado"}, status=404
            )
        if pending.is_expired():
            return web.json_response(
                {"error": "pedido expirado"}, status=410
            )
        if pending.decided is not None:
            return web.json_response(
                {"error": "pedido já decidido"}, status=409
            )

        approve = decision_raw == "approve"
        if self._tuya is None:
            return web.json_response(
                {"error": "Tuya indisponível no momento"}, status=503
            )
        try:
            tuya_resp = await self._tuya.reply_unlock_request(approve)
        except Exception as exc:  # noqa: BLE001
            logger.exception("falha em reply_unlock_request token=%s", token)
            return web.json_response(
                {"error": f"erro Tuya: {exc}"}, status=502
            )

        pending.decided = approve
        pending.decided_by = user_id
        pending.decided_at = time.time()

        # editar msg Telegram
        if pending.telegram_message_id and self._telegram is not None:
            status_emoji = "✅" if approve else "❌"
            try:
                await self._telegram.edit_message(
                    pending.chat_id,
                    pending.telegram_message_id,
                    f"{status_emoji} *Pedido {('aprovado' if approve else 'negado')}*\n"
                    f"por user_id `{user_id}` em "
                    f"{time.strftime('%Y-%m-%d %H:%M:%S')}",
                )
            except Exception:  # noqa: BLE001
                logger.debug("edit decision falhou token=%s", token)

        return web.json_response(
            {
                "ok": True,
                "token": token,
                "decision": decision_raw,
                "tuya_response_success": tuya_resp.get("success"),
            }
        )


async def main() -> None:
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = BridgeConfig.from_env()
    bridge = PandaplusBridge(config)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig, lambda: asyncio.create_task(bridge.stop())
        )

    try:
        await bridge.start()
    finally:
        await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
