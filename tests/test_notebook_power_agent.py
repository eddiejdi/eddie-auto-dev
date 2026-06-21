from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "notebook_power_agent.py"
spec = importlib.util.spec_from_file_location("notebook_power_agent", MODULE_PATH)
assert spec is not None and spec.loader is not None
agent = importlib.util.module_from_spec(spec)
sys.modules["notebook_power_agent"] = agent
spec.loader.exec_module(agent)


def make_config(**overrides):
    values = {
        "mode": "ha-mqtt",
        "mqtt_host": "mqtt.local",
        "mqtt_port": 1883,
        "mqtt_username": "",
        "mqtt_password": "",
        "tuya_product_id": "",
        "tuya_device_id": "tuya-device-test",
        "tuya_device_secret": "tuya-secret-test",
        "device_id": "note-test",
        "device_name": "Notebook Test",
        "base_topic": "eddie/notebook/note-test",
        "discovery_prefix": "homeassistant",
        "command_delay_seconds": 0,
        "dangerous_enabled": False,
        "allowed_actions": frozenset({"hibernate", "shutdown", "lock"}),
        "dry_run": True,
    }
    values.update(overrides)
    return agent.AgentConfig(**values)


def test_discovery_payloads_create_buttons_and_state_sensor():
    cfg = make_config()
    payloads = agent.discovery_payloads(cfg)

    assert "homeassistant/sensor/note-test/power_state/config" in payloads
    assert "homeassistant/button/note-test/hibernate/config" in payloads
    button = payloads["homeassistant/button/note-test/hibernate/config"]
    assert button["command_topic"] == "eddie/notebook/note-test/command"
    assert button["payload_press"] == '{"action":"hibernate"}'
    assert button["device"]["identifiers"] == ["note-test"]


def test_parse_action_accepts_json_and_plain_payloads():
    assert agent.parse_action('{"action":"shutdown"}') == "shutdown"
    assert agent.parse_action("lock") == "lock"


def test_dangerous_action_is_blocked_until_enabled():
    cfg = make_config(dangerous_enabled=False)
    ok, detail = agent.execute_action("hibernate", cfg)

    assert ok is False
    assert "bloqueadas" in detail


def test_dry_run_executes_allowed_safe_action():
    cfg = make_config(dangerous_enabled=False)
    ok, detail = agent.execute_action("lock", cfg)

    assert ok is True
    assert detail == "dry-run: loginctl lock-sessions"


def test_tuya_credentials_match_official_hmac_example_shape():
    creds = agent.tuya_credentials(
        "6c828cba434ff40c074wF2",
        "ffad8eb66ae8c717",
        timestamp=1607635284,
    )

    assert creds["client_id"] == "tuyalink_6c828cba434ff40c074wF2"
    assert creds["username"] == (
        "6c828cba434ff40c074wF2|signMethod=hmacSha256,"
        "timestamp=1607635284,secureMode=1,accessType=1"
    )
    assert creds["password"] == "9088f1608df4744e2a933ff905ffdde58dc7213510f25ad786a89896a5ea1104"


def test_tuya_action_can_come_from_action_or_property_payload():
    assert agent.action_from_tuya_message(
        {"data": {"actionCode": "hibernate", "inputParams": {}}}
    ) == "hibernate"
    assert agent.action_from_tuya_message(
        {"data": {"actionCode": "power_action", "inputParams": {"action": "shutdown"}}}
    ) == "shutdown"
    assert agent.action_from_tuya_message(
        {"data": {"power_command": "lock"}}
    ) == "lock"
