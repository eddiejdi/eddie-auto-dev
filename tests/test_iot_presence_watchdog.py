from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "homelab" / "iot_presence_watchdog.py"
)
_SPEC = importlib.util.spec_from_file_location("iot_presence_watchdog", MODULE_PATH)
assert _SPEC and _SPEC.loader
wd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(wd)

NOW = 1_784_300_000.0

CONF = """ISP_GW=192.168.15.1
DEVICE_MAC=38:A5:C9:E0:5D:D9
DEVICE_MAC=4c:a9:19:0d:dd:bf
MAC_IP_4ca9190dddbf=192.168.15.127
DEVICE_MAC=4c:a9:19:0d:dd:bf
"""


def test_parse_allowlist_macs_dedup_lowercase() -> None:
    assert wd.parse_allowlist_macs(CONF) == [
        "38:a5:c9:e0:5d:d9",
        "4c:a9:19:0d:dd:bf",
    ]


def test_parse_leases_ignores_expired() -> None:
    leases = (
        f"{int(NOW) + 3600} aa:bb:cc:dd:ee:01 192.168.15.10 dev1 *\n"
        f"{int(NOW) - 10} aa:bb:cc:dd:ee:02 192.168.15.11 dev2 *\n"
        "0 40:ae:30:81:c7:6e 192.168.15.113 TL-WPA4220 *\n"
    )
    got = wd.parse_leases(leases, now=NOW)
    assert got == {"aa:bb:cc:dd:ee:01": "192.168.15.10"}


def test_parse_arp_skips_failed_and_ipv6() -> None:
    neigh = (
        "192.168.15.105 dev eth-onboard lladdr F8:17:2D:F8:59:52 REACHABLE\n"
        "192.168.15.104 dev eth-onboard FAILED\n"
        "fe80::1 dev eth-wan lladdr 00:d4:9e:16:6a:19 router STALE\n"
        "192.168.15.121 dev eth-onboard lladdr 38:a5:c9:da:4c:71 STALE\n"
    )
    got = wd.parse_arp(neigh)
    assert got == {
        "f8:17:2d:f8:59:52": "192.168.15.105",
        "38:a5:c9:da:4c:71": "192.168.15.121",
    }


def test_evaluate_presence_alert_only_after_threshold() -> None:
    macs = ["aa:bb:cc:dd:ee:01"]
    # sumiu agora — sem alerta ainda
    state, alerts = wd.evaluate_presence(macs, {}, {}, {}, now=NOW, absent_alert_s=1800)
    assert alerts == []
    assert state["devices"][macs[0]]["absent_since"] == NOW

    # 31 min depois — alerta único
    state2, alerts2 = wd.evaluate_presence(
        macs, {}, {}, state, now=NOW + 1860, absent_alert_s=1800
    )
    assert len(alerts2) == 1 and "fora do WiFi" in alerts2[0]
    assert state2["devices"][macs[0]]["alerted"] is True

    # continua fora — não repete alerta
    _, alerts3 = wd.evaluate_presence(
        macs, {}, {}, state2, now=NOW + 3600, absent_alert_s=1800
    )
    assert alerts3 == []


def test_evaluate_presence_recovery_alert_and_reset() -> None:
    macs = ["aa:bb:cc:dd:ee:01"]
    prev = {
        "devices": {
            macs[0]: {
                "present": False,
                "last_ip": "192.168.15.50",
                "absent_since": NOW - 7200,
                "alerted": True,
            }
        }
    }
    state, alerts = wd.evaluate_presence(
        macs, {macs[0]: "192.168.15.99"}, {}, prev, now=NOW
    )
    assert len(alerts) == 1 and "de volta" in alerts[0]
    dev = state["devices"][macs[0]]
    assert dev["present"] and dev["absent_since"] == 0 and dev["alerted"] is False
    assert dev["last_ip"] == "192.168.15.99"


def test_render_prom_counts() -> None:
    state = {
        "devices": {
            "aa:bb:cc:dd:ee:01": {"present": True, "last_ip": "192.168.15.10"},
            "aa:bb:cc:dd:ee:02": {"present": False, "last_ip": ""},
        },
        "alerts_sent_total": 4,
    }
    out = wd.render_prom(state)
    assert 'iot_device_present{mac="aa:bb:cc:dd:ee:01",ip="192.168.15.10"} 1' in out
    assert 'iot_device_present{mac="aa:bb:cc:dd:ee:02",ip="unknown"} 0' in out
    assert "iot_devices_present_count 1" in out
    assert "iot_devices_total 2" in out
    assert "iot_presence_alerts_sent_total 4" in out


def test_send_telegram_noop_without_creds(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert wd.send_telegram(["msg"]) is False
