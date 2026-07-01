"""Cliente Tuya: subscribe MQ + envio de comando reply_unlock_request.

Encapsula `tuya_sharing` SDK. Aceita callback assíncrono para eventos de
status. A subscrição MQ roda numa thread separada (paho-mqtt) e os eventos
são empurrados para uma `asyncio.Queue` thread-safe.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

POLL_ACTIVITY_CODES = frozenset(
    {
        "unlock_fingerprint",
        "unlock_password",
        "unlock_card",
        "unlock_face",
        "unlock_app",
        "unlock_hand",
    }
)


@dataclass(frozen=True)
class TuyaStatusEvent:
    """Evento de mudança de status publicado pela fechadura via MQ.

    Attributes:
        device_id: ID do dispositivo Tuya.
        code: Código do DP (ex: ``unlock_request``, ``alarm_lock``).
        value: Novo valor do DP.
        raw: Payload bruto recebido do MQ (para auditoria).
    """

    device_id: str
    code: str
    value: Any
    raw: dict


class TuyaBridgeClient:
    """Wrapper assíncrono sobre `tuya_sharing` para o bridge.

    Args:
        client_id: Client ID da integração (HA usa constante pública).
        user_code: User code Tuya.
        terminal_id: Terminal ID emitido pelo OAuth.
        endpoint: Endpoint Tuya (``https://apigw.tuyaus.com``).
        token_info: Dict com ``access_token``, ``refresh_token``, ``expire_time``, ``t``, ``uid``.
        target_device_id: Filtro: só emite eventos deste device.
        event_queue: Fila assíncrona para entregar eventos ao consumidor.
    """

    def __init__(
        self,
        *,
        client_id: str,
        user_code: str,
        terminal_id: str,
        endpoint: str,
        token_info: dict,
        target_device_id: str,
        event_queue: asyncio.Queue,
        token_update_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._client_id = client_id
        self._user_code = user_code
        self._terminal_id = terminal_id
        self._endpoint = endpoint
        self._token_info = token_info
        self._target_device_id = target_device_id
        self._queue = event_queue
        self._loop = asyncio.get_event_loop()
        self._manager: Any = None
        self._stop = threading.Event()
        self._token_update_callback = token_update_callback
        self._last_polled_update_time: int | None = None
        self._last_polled_status: dict[str, Any] = {}

    def start(self) -> None:
        """Inicializa o Manager e a conexão MQ (síncrono, chamado em executor).

        Raises:
            RuntimeError: Se o SDK não estiver instalado.
        """
        try:
            from tuya_sharing.customerapi import (  # type: ignore
                SharingTokenListener,
            )
            from tuya_sharing.manager import Manager  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "tuya_sharing não está instalado neste venv"
            ) from exc

        client = self

        class _BridgeTokenListener(SharingTokenListener):
            """Listener para receber rotação de token do SDK Tuya."""

            def update_token(self, token_info: dict[str, Any]) -> None:
                client._on_token_update(token_info)

        listener = _BridgeTokenListener()
        # Manager internamente constrói CustomerTokenInfo(token_response),
        # portanto passamos o dict cru — não instanciamos CustomerTokenInfo aqui.
        self._manager = Manager(
            self._client_id,
            self._user_code,
            self._terminal_id,
            self._endpoint,
            self._token_info,  # dict: {access_token, refresh_token, expire_time, t, uid}
            listener,
        )

        # Registrar nosso listener no Manager (recebemos update_device callbacks)
        self._manager.add_device_listener(self)

        # Carregar cache de devices e iniciar MQ — o Manager gerencia tudo internamente
        self._manager.update_device_cache()
        self._manager.refresh_mq()

        # Listener raw direto no MQ — fallback caso o Manager filtre/engula eventos
        if self._manager.mq is not None:
            self._manager.mq.add_message_listener(self._on_mq_message)
            logger.info("Listener raw MQ registrado")

        logger.info(
            "Tuya MQ iniciado para device %s", self._target_device_id
        )

    def _on_token_update(self, token_info: dict[str, Any]) -> None:
        """Persiste token atualizado em memória e repassa para callback externo."""
        self._token_info = token_info
        if self._token_update_callback is not None:
            try:
                self._token_update_callback(token_info)
            except Exception:  # noqa: BLE001
                logger.exception("falha no callback de update_token")

    def stop(self) -> None:
        """Encerra MQ e Manager."""
        self._stop.set()
        if self._manager is not None and getattr(self._manager, "mq", None) is not None:
            try:
                self._manager.mq.stop()
            except Exception as exc:  # noqa: BLE001
                logger.warning("erro ao parar MQ: %s", exc)

    # --- callbacks tuya_sharing.Manager (interface device listener) ---

    def update_device(
        self,
        device: Any,
        updated_status_properties: list[str] | None = None,
        dp_timestamps: dict | None = None,
    ) -> None:
        """Callback do Manager quando um device sofre update.

        Args:
            device: objeto CustomerDevice do tuya_sharing.
            updated_status_properties: lista de códigos atualizados neste evento.
            dp_timestamps: timestamps dos DPs (ignorado pelo bridge).
        """
        device_id = getattr(device, "id", None)
        if device_id != self._target_device_id:
            return
        status = getattr(device, "status", {}) or {}
        # Emitir apenas os DPs que mudaram neste evento (ou todos se lista ausente)
        codes_to_emit = updated_status_properties if updated_status_properties else list(status.keys())
        for code in codes_to_emit:
            value = status.get(code)
            event = TuyaStatusEvent(
                device_id=device_id,
                code=code,
                value=value,
                raw={"source": "manager_update", "updated_properties": codes_to_emit},
            )
            self._enqueue(event)

    def add_device(self, device: Any) -> None:  # noqa: D401 - SDK interface
        """Interface do SDK; sem operação."""

    def remove_device(self, device_id: str) -> None:  # noqa: D401
        """Interface do SDK; sem operação."""

    # --- handler MQ bruto (paho.mqtt thread) ---

    def _on_mq_message(self, msg: dict) -> None:
        """Recebe mensagens cruas do MQ Tuya (listener direto no SharingMQ)."""
        try:
            data = msg.get("data") or msg
            if isinstance(data, str):
                data = json.loads(data)
            dev_id = data.get("devId") or data.get("dataId")
            logger.debug("MQ raw msg: devId=%s protocol=%s", dev_id, msg.get("protocol"))
            if dev_id != self._target_device_id:
                return
            status_list = data.get("status") or []
            logger.info("MQ raw: evento do device alvo — %d DPs: %s", len(status_list), status_list)
            for item in status_list:
                code = item.get("code")
                value = item.get("value")
                if not code:
                    continue
                event = TuyaStatusEvent(
                    device_id=dev_id,
                    code=code,
                    value=value,
                    raw={"source": "mq_raw", "data": data},
                )
                self._enqueue(event)
        except Exception:  # noqa: BLE001
            logger.exception("erro processando msg MQ")

    def _enqueue(self, event: TuyaStatusEvent) -> None:
        """Empurra evento de thread paho para o loop asyncio."""
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, event)
        except RuntimeError:
            logger.warning("loop fechado, descartando evento")

    @staticmethod
    def build_poll_events(
        device_id: str,
        device_payload: dict[str, Any],
        tracked_codes: set[str] | frozenset[str],
        previous_status: dict[str, Any],
        previous_update_time: int | None,
    ) -> tuple[int, dict[str, Any], list[TuyaStatusEvent]]:
        """Converte payload do devices/detail em eventos de polling.

        Args:
            device_id: ID esperado do dispositivo.
            device_payload: Item retornado por `/devices/detail`.
            tracked_codes: Códigos de interesse para o bridge.
            previous_status: Último status conhecido via polling.
            previous_update_time: Último `update_time` observado.

        Returns:
            Tupla com `update_time`, mapa de status atual e eventos detectados.
        """
        update_time = int(device_payload.get("update_time", 0) or 0)
        status_map: dict[str, Any] = {}
        for item in device_payload.get("status", []) or []:
            code = item.get("code")
            if not code:
                continue
            status_map[code] = item.get("value")

        if previous_update_time is None:
            return update_time, status_map, []

        activity_changed = any(
            status_map.get(code) != previous_status.get(code)
            for code in POLL_ACTIVITY_CODES
        )

        events: list[TuyaStatusEvent] = []
        for code in tracked_codes:
            if code not in status_map:
                continue
            value = status_map[code]
            previous = previous_status.get(code)
            should_emit = value != previous
            if not should_emit and code == "alarm_lock" and activity_changed:
                should_emit = True
            if not should_emit:
                continue
            events.append(
                TuyaStatusEvent(
                    device_id=device_id,
                    code=code,
                    value=value,
                    raw={
                        "source": "poll",
                        "update_time": update_time,
                        "previous": previous,
                    },
                )
            )

        return update_time, status_map, events

    def _poll_status_changes_sync(
        self, tracked_codes: set[str] | frozenset[str]
    ) -> list[TuyaStatusEvent]:
        """Consulta estado atual via API e gera eventos quando houver mudança."""
        if self._manager is None:
            raise RuntimeError("Manager não inicializado")

        response = self._manager.customer_api.get(
            "/v1.0/m/life/ha/devices/detail",
            {"devIds": self._target_device_id},
        )
        devices = response.get("result", []) or []
        if not devices:
            return []

        update_time, status_map, events = self.build_poll_events(
            self._target_device_id,
            devices[0],
            tracked_codes,
            self._last_polled_status,
            self._last_polled_update_time,
        )
        self._last_polled_update_time = update_time
        self._last_polled_status = status_map
        if events:
            logger.info(
                "Polling detectou %d evento(s) do device alvo: %s",
                len(events),
                [(event.code, event.value) for event in events],
            )
        return events

    async def poll_status_changes(
        self, tracked_codes: set[str] | frozenset[str]
    ) -> list[TuyaStatusEvent]:
        """Fallback por polling para dispositivos que não publicam no MQ."""
        return await asyncio.to_thread(
            self._poll_status_changes_sync,
            tracked_codes,
        )

    # --- comando de resposta ---

    async def reply_unlock_request(self, approve: bool) -> dict:
        """Envia comando reply_unlock_request.

        Args:
            approve: True para aprovar abertura, False para negar.

        Returns:
            Resposta da API Tuya.
        """
        if self._manager is None:
            raise RuntimeError("Manager não inicializado")
        path = (
            f"/v1.0/m/life/devices/{self._target_device_id}/commands"
        )
        body = {
            "commands": [
                {"code": "reply_unlock_request", "value": bool(approve)}
            ]
        }
        return await asyncio.to_thread(
            self._manager.customer_api.post, path, body
        )

    def session_check(self) -> None:
        """Valida sessão atual executando chamada simples de API.

        Raises:
            RuntimeError: Se o manager não foi inicializado.
            Exception: Erros de autenticação/rede vindos do SDK.
        """
        if self._manager is None:
            raise RuntimeError("Manager não inicializado")
        self._manager.customer_api.get("/v1.0/m/life/users/homes")
