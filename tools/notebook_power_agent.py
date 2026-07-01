#!/usr/bin/env python3
"""Expose local notebook power controls through TuyaLink or HA MQTT.

In Tuya mode, the notebook acts as a custom TuyaLink MQTT device registered in
the Tuya Developer Platform. In Home Assistant mode, it publishes MQTT discovery
entities to a regular broker.
"""
from __future__ import annotations

import argparse
import hmac
import json
import logging
import os
import shlex
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

LOG = logging.getLogger("notebook_power_agent")

ACTION_COMMANDS: dict[str, tuple[str, ...]] = {
    "shutdown": ("systemctl", "poweroff"),
    "hibernate": ("systemctl", "hibernate"),
    "suspend": ("systemctl", "suspend"),
    "reboot": ("systemctl", "reboot"),
    "lock": ("loginctl", "lock-sessions"),
}

DANGEROUS_ACTIONS = frozenset({"shutdown", "hibernate", "suspend", "reboot"})


@dataclass(frozen=True)
class AgentConfig:
    mode: str
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    tuya_product_id: str
    tuya_device_id: str
    tuya_device_secret: str
    device_id: str
    device_name: str
    base_topic: str
    discovery_prefix: str
    command_delay_seconds: int
    dangerous_enabled: bool
    allowed_actions: frozenset[str]
    dry_run: bool

    @classmethod
    def from_env(cls) -> "AgentConfig":
        hostname = socket.gethostname().split(".")[0] or "notebook"
        device_id = os.getenv("NOTEBOOK_POWER_DEVICE_ID", hostname).strip()
        if not device_id:
            raise ValueError("NOTEBOOK_POWER_DEVICE_ID nao pode ficar vazio")
        allowed_raw = os.getenv(
            "NOTEBOOK_POWER_ALLOWED_ACTIONS",
            "shutdown,hibernate,suspend,reboot,lock",
        )
        allowed = frozenset(
            action.strip()
            for action in allowed_raw.split(",")
            if action.strip()
        )
        unknown = allowed - set(ACTION_COMMANDS)
        if unknown:
            raise ValueError(f"Acoes desconhecidas em NOTEBOOK_POWER_ALLOWED_ACTIONS: {sorted(unknown)}")
        mode = os.getenv("NOTEBOOK_POWER_MODE", "ha-mqtt").strip().lower()
        if mode not in {"ha-mqtt", "tuya"}:
            raise ValueError("NOTEBOOK_POWER_MODE deve ser ha-mqtt ou tuya")
        tuya_device_id = os.getenv("TUYA_DEVICE_ID", "").strip()
        mqtt_host = os.getenv("NOTEBOOK_POWER_MQTT_HOST", "")
        if not mqtt_host:
            mqtt_host = "m1.tuyaus.com" if mode == "tuya" else "127.0.0.1"
        return cls(
            mode=mode,
            mqtt_host=mqtt_host,
            mqtt_port=int(os.getenv("NOTEBOOK_POWER_MQTT_PORT", "8883" if mode == "tuya" else "1883")),
            mqtt_username=os.getenv("NOTEBOOK_POWER_MQTT_USERNAME", ""),
            mqtt_password=os.getenv("NOTEBOOK_POWER_MQTT_PASSWORD", ""),
            tuya_product_id=os.getenv("TUYA_PRODUCT_ID", "").strip(),
            tuya_device_id=tuya_device_id,
            tuya_device_secret=os.getenv("TUYA_DEVICE_SECRET", "").strip(),
            device_id=device_id,
            device_name=os.getenv("NOTEBOOK_POWER_DEVICE_NAME", f"Notebook {device_id}"),
            base_topic=os.getenv("NOTEBOOK_POWER_BASE_TOPIC", f"eddie/notebook/{device_id}"),
            discovery_prefix=os.getenv("NOTEBOOK_POWER_DISCOVERY_PREFIX", "homeassistant"),
            command_delay_seconds=int(os.getenv("NOTEBOOK_POWER_COMMAND_DELAY", "3")),
            dangerous_enabled=os.getenv("NOTEBOOK_POWER_ENABLE_DANGEROUS", "0").lower()
            in {"1", "true", "yes", "on"},
            allowed_actions=allowed,
            dry_run=os.getenv("NOTEBOOK_POWER_DRY_RUN", "0").lower()
            in {"1", "true", "yes", "on"},
        )


def _device_payload(cfg: AgentConfig) -> dict[str, Any]:
    return {
        "identifiers": [cfg.device_id],
        "name": cfg.device_name,
        "manufacturer": "eddie-auto-dev",
        "model": "Linux notebook power agent",
    }


def discovery_payloads(cfg: AgentConfig) -> dict[str, dict[str, Any]]:
    """Return MQTT discovery topics and payloads for Home Assistant."""
    device = _device_payload(cfg)
    availability_topic = f"{cfg.base_topic}/availability"
    state_topic = f"{cfg.base_topic}/state"
    payloads: dict[str, dict[str, Any]] = {
        f"{cfg.discovery_prefix}/sensor/{cfg.device_id}/power_state/config": {
            "name": "Power state",
            "unique_id": f"{cfg.device_id}_power_state",
            "state_topic": state_topic,
            "value_template": "{{ value_json.state }}",
            "json_attributes_topic": state_topic,
            "availability_topic": availability_topic,
            "device": device,
        },
        f"{cfg.discovery_prefix}/binary_sensor/{cfg.device_id}/dangerous_enabled/config": {
            "name": "Dangerous commands enabled",
            "unique_id": f"{cfg.device_id}_dangerous_enabled",
            "state_topic": state_topic,
            "value_template": "{{ 'ON' if value_json.dangerous_enabled else 'OFF' }}",
            "availability_topic": availability_topic,
            "device": device,
        },
    }
    for action in sorted(cfg.allowed_actions):
        payloads[
            f"{cfg.discovery_prefix}/button/{cfg.device_id}/{action}/config"
        ] = {
            "name": action.replace("_", " ").title(),
            "unique_id": f"{cfg.device_id}_{action}",
            "command_topic": f"{cfg.base_topic}/command",
            "payload_press": json.dumps({"action": action}, separators=(",", ":")),
            "availability_topic": availability_topic,
            "device": device,
        }
    return payloads


def current_state(cfg: AgentConfig, *, last_action: str | None = None, last_error: str | None = None) -> dict[str, Any]:
    return {
        "state": "online",
        "hostname": socket.gethostname(),
        "device_id": cfg.device_id,
        "dangerous_enabled": cfg.dangerous_enabled,
        "allowed_actions": sorted(cfg.allowed_actions),
        "last_action": last_action,
        "last_error": last_error,
        "updated_at": int(time.time()),
    }


def parse_action(payload: str | bytes) -> str:
    text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    text = text.strip()
    if not text:
        raise ValueError("payload vazio")
    if text.startswith("{"):
        data = json.loads(text)
        action = str(data.get("action", "")).strip()
    else:
        action = text
    if action not in ACTION_COMMANDS:
        raise ValueError(f"acao desconhecida: {action!r}")
    return action


def execute_action(action: str, cfg: AgentConfig) -> tuple[bool, str]:
    if action not in cfg.allowed_actions:
        return False, f"acao nao permitida: {action}"
    if action in DANGEROUS_ACTIONS and not cfg.dangerous_enabled:
        return False, "acoes perigosas bloqueadas; defina NOTEBOOK_POWER_ENABLE_DANGEROUS=1"

    command = ACTION_COMMANDS[action]
    if cfg.command_delay_seconds > 0 and action in DANGEROUS_ACTIONS:
        LOG.warning("executando %s em %ss", action, cfg.command_delay_seconds)
        time.sleep(cfg.command_delay_seconds)
    if cfg.dry_run:
        return True, "dry-run: " + shlex.join(command)
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        return False, f"comando falhou rc={exc.returncode}: {shlex.join(command)}"
    return True, "executado: " + shlex.join(command)


def write_discovery_file(cfg: AgentConfig, output: Path) -> None:
    output.write_text(
        json.dumps(discovery_payloads(cfg), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def tuya_credentials(device_id: str, device_secret: str, timestamp: int | None = None) -> dict[str, str]:
    """Build TuyaLink MQTT client credentials from a device certificate."""
    if not device_id or not device_secret:
        raise ValueError("TUYA_DEVICE_ID e TUYA_DEVICE_SECRET sao obrigatorios")
    ts = int(time.time()) if timestamp is None else timestamp
    username = f"{device_id}|signMethod=hmacSha256,timestamp={ts},secureMode=1,accessType=1"
    content = f"deviceId={device_id},timestamp={ts},secureMode=1,accessType=1"
    password = hmac.new(device_secret.encode("utf-8"), content.encode("utf-8"), digestmod=sha256).hexdigest()
    return {
        "client_id": f"tuyalink_{device_id}",
        "username": username,
        "password": password,
    }


def tuya_topic(device_id: str, suffix: str) -> str:
    return f"tylink/{device_id}/{suffix}"


def tuya_property_report(cfg: AgentConfig, **properties: Any) -> tuple[str, dict[str, Any]]:
    now = int(time.time() * 1000)
    data = {
        key: {"value": value, "time": now}
        for key, value in properties.items()
    }
    return (
        tuya_topic(cfg.tuya_device_id, "thing/property/report"),
        {"msgId": uuid.uuid4().hex[:32], "time": now, "data": data},
    )


def action_from_tuya_message(payload: dict[str, Any]) -> str | None:
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return None

    action_code = str(data.get("actionCode", "")).strip()
    if action_code in ACTION_COMMANDS:
        return action_code
    input_params = data.get("inputParams") or {}
    if isinstance(input_params, dict):
        requested = str(input_params.get("action", "")).strip()
        if requested in ACTION_COMMANDS:
            return requested

    command = data.get("power_command")
    if isinstance(command, str) and command.strip() in ACTION_COMMANDS:
        return command.strip()
    for action in ACTION_COMMANDS:
        if data.get(action) is True:
            return action
    return None


def tuya_response(topic: str, msg_id: str, code: int, action: str | None = None, detail: str = "") -> tuple[str, dict[str, Any]]:
    payload: dict[str, Any] = {"msgId": msg_id, "time": int(time.time() * 1000), "code": code}
    if action:
        payload["data"] = {"actionCode": action, "outputParams": {"detail": detail}}
    return topic, payload


def run_mqtt_agent(cfg: AgentConfig) -> None:
    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except ImportError as exc:
        raise RuntimeError("instale paho-mqtt: python3 -m pip install paho-mqtt") from exc

    client = mqtt.Client(client_id=f"{cfg.device_id}-power-agent")
    if cfg.mqtt_username:
        client.username_pw_set(cfg.mqtt_username, cfg.mqtt_password)
    availability_topic = f"{cfg.base_topic}/availability"
    state_topic = f"{cfg.base_topic}/state"
    command_topic = f"{cfg.base_topic}/command"
    client.will_set(availability_topic, "offline", retain=True)

    def publish_state(last_action: str | None = None, last_error: str | None = None) -> None:
        client.publish(
            state_topic,
            json.dumps(current_state(cfg, last_action=last_action, last_error=last_error), separators=(",", ":")),
            retain=True,
        )

    def on_connect(client_obj: Any, _userdata: Any, _flags: Any, rc: int) -> None:
        if rc != 0:
            LOG.error("MQTT connect rc=%s", rc)
            return
        LOG.info("conectado ao MQTT %s:%s", cfg.mqtt_host, cfg.mqtt_port)
        for topic, payload in discovery_payloads(cfg).items():
            client_obj.publish(topic, json.dumps(payload, separators=(",", ":")), retain=True)
        client_obj.publish(availability_topic, "online", retain=True)
        publish_state()
        client_obj.subscribe(command_topic)

    def on_message(_client_obj: Any, _userdata: Any, msg: Any) -> None:
        try:
            action = parse_action(msg.payload)
            ok, detail = execute_action(action, cfg)
            publish_state(last_action=action if ok else None, last_error=None if ok else detail)
            if ok:
                LOG.warning("%s", detail)
            else:
                LOG.error("%s", detail)
        except Exception as exc:  # noqa: BLE001
            LOG.exception("falha ao processar comando")
            publish_state(last_error=str(exc))

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(cfg.mqtt_host, cfg.mqtt_port, keepalive=45)
    client.loop_forever()


def run_tuya_agent(cfg: AgentConfig) -> None:
    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except ImportError as exc:
        raise RuntimeError("instale paho-mqtt: python3 -m pip install paho-mqtt") from exc
    if not cfg.tuya_device_id or not cfg.tuya_device_secret:
        raise ValueError("modo tuya exige TUYA_DEVICE_ID e TUYA_DEVICE_SECRET")

    creds = tuya_credentials(cfg.tuya_device_id, cfg.tuya_device_secret)
    client = mqtt.Client(client_id=creds["client_id"])
    client.username_pw_set(creds["username"], creds["password"])
    client.tls_set()

    property_set_topic = tuya_topic(cfg.tuya_device_id, "thing/property/set")
    action_topic = tuya_topic(cfg.tuya_device_id, "thing/action/execute")

    def publish_json(topic: str, payload: dict[str, Any], qos: int = 1) -> None:
        client.publish(topic, json.dumps(payload, separators=(",", ":")), qos=qos)

    def report_state(last_action: str | None = None, last_error: str = "") -> None:
        topic, payload = tuya_property_report(
            cfg,
            power_state="online",
            dangerous_enabled=cfg.dangerous_enabled,
            last_action=last_action or "",
            last_error=last_error,
            hostname=socket.gethostname(),
        )
        publish_json(topic, payload)

    def on_connect(client_obj: Any, _userdata: Any, _flags: Any, rc: int) -> None:
        if rc != 0:
            LOG.error("Tuya MQTT connect rc=%s", rc)
            return
        LOG.info("conectado ao Tuya MQTT %s:%s device=%s", cfg.mqtt_host, cfg.mqtt_port, cfg.tuya_device_id)
        client_obj.subscribe([(property_set_topic, 1), (action_topic, 1)])
        report_state()

    def on_message(_client_obj: Any, _userdata: Any, msg: Any) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            action = action_from_tuya_message(payload)
            msg_id = str(payload.get("msgId", uuid.uuid4().hex[:32]))
            if not action:
                response_topic = (
                    tuya_topic(cfg.tuya_device_id, "thing/action/execute_response")
                    if msg.topic == action_topic
                    else tuya_topic(cfg.tuya_device_id, "thing/property/set_response")
                )
                topic, response = tuya_response(response_topic, msg_id, 1003, detail="acao ausente ou invalida")
                publish_json(topic, response)
                report_state(last_error="acao ausente ou invalida")
                return
            ok, detail = execute_action(action, cfg)
            code = 0 if ok else 2006
            response_topic = (
                tuya_topic(cfg.tuya_device_id, "thing/action/execute_response")
                if msg.topic == action_topic
                else tuya_topic(cfg.tuya_device_id, "thing/property/set_response")
            )
            topic, response = tuya_response(
                response_topic,
                msg_id,
                code,
                action if msg.topic == action_topic else None,
                detail,
            )
            publish_json(topic, response)
            report_state(last_action=action if ok else None, last_error="" if ok else detail)
        except Exception as exc:  # noqa: BLE001
            LOG.exception("falha ao processar mensagem Tuya")
            report_state(last_error=str(exc))

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(cfg.mqtt_host, cfg.mqtt_port, keepalive=60)
    client.loop_forever()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-discovery", action="store_true", help="imprime payloads MQTT discovery e sai")
    parser.add_argument("--print-tuya-credentials", action="store_true", help="imprime client_id/username/password Tuya MQTT e sai")
    parser.add_argument("--write-discovery", type=Path, help="salva payloads MQTT discovery em JSON e sai")
    parser.add_argument("--execute", choices=sorted(ACTION_COMMANDS), help="executa uma acao local e sai")
    parser.add_argument("--dry-run", action="store_true", help="nao executa comandos de energia")
    return parser


def main() -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    args = build_arg_parser().parse_args()
    cfg = AgentConfig.from_env()
    if args.dry_run:
        cfg = AgentConfig(
            **{**cfg.__dict__, "dry_run": True}  # type: ignore[arg-type]
        )
    if args.print_discovery:
        print(json.dumps(discovery_payloads(cfg), indent=2, sort_keys=True))
        return 0
    if args.print_tuya_credentials:
        print(json.dumps(tuya_credentials(cfg.tuya_device_id, cfg.tuya_device_secret), indent=2, sort_keys=True))
        return 0
    if args.write_discovery:
        write_discovery_file(cfg, args.write_discovery)
        return 0
    if args.execute:
        ok, detail = execute_action(args.execute, cfg)
        print(detail)
        return 0 if ok else 2
    if cfg.mode == "tuya":
        run_tuya_agent(cfg)
    else:
        run_mqtt_agent(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
