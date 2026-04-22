from __future__ import annotations

import pytest

from scripts.system import legacy_wifi_probe


def test_parse_hidden_form_fields() -> None:
    html = (
        '<form>'
        '<input type="hidden" name="Frm_Logintoken" value="0">'
        '<input type="hidden" name="_lang" value="en">'
        '</form>'
    )

    fields = legacy_wifi_probe.parse_hidden_form_fields(html)

    assert fields["Frm_Logintoken"] == "0"
    assert fields["_lang"] == "en"


def test_login_zte_router_success(monkeypatch: pytest.MonkeyPatch) -> None:
    states = [
        '<html><input type="hidden" name="Frm_Logintoken" value="0"></html>',
        '<html><title>Logged in</title><a href="logout">Logout</a></html>',
    ]

    def fake_fetch_url(url: str, opener, data=None, timeout=5):
        return states.pop(0)

    monkeypatch.setattr(legacy_wifi_probe, "fetch_url", fake_fetch_url)

    success, body, opener = legacy_wifi_probe.login_zte_router(
        "http://192.168.15.1", "admin", "admin"
    )

    assert success is True
    assert "Logged in" in body
    assert opener is not None


def test_probe_zte_router_http_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(legacy_wifi_probe, "is_port_open", lambda host, port, timeout=5: False)

    lines = legacy_wifi_probe.probe_zte_router("192.168.15.1", "admin", "admin")

    assert any("HTTP port 80 open: no" in line for line in lines)
    assert any("não é possível avançar" in line for line in lines)


def test_probe_network_device_with_http_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(legacy_wifi_probe, "is_port_open", lambda host, port, timeout=5: True)
    monkeypatch.setattr(legacy_wifi_probe, "fetch_url", lambda url, opener, data=None, timeout=5: '<html><title>AP Login</title><form>login</form></html>')

    lines = legacy_wifi_probe.probe_network_device("192.168.15.103")

    assert any("HTTP title: AP Login" in line for line in lines)
    assert any("HTTP login page detected" in line for line in lines)
