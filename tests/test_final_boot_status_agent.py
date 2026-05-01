"""Testes do resumo de boot enviado ao Telegram via agent."""

from __future__ import annotations

from scripts.monitoring import final_boot_status_agent as mod


def test_collect_summary_formats_critical_failures(monkeypatch) -> None:
    """Resumo deve destacar falhas criticas e units falhadas."""

    def fake_service_state(name: str) -> mod.ServiceState:
        failing = {"docker", "eddie-whatsapp-bot.service"}
        state = "failed" if name in failing else "active"
        return mod.ServiceState(name=name, state=state)

    monkeypatch.setattr(mod, "service_state", fake_service_state)
    monkeypatch.setattr(mod, "list_failed_units", lambda: ["eddie-whatsapp-exporter.service"])
    monkeypatch.setattr(
        mod,
        "read_first_line",
        lambda args, timeout=10, fallback="n/a": {
            "uptime -p": "up 3 minutes",
            "systemd-analyze": "Startup finished in 12.3s",
            "sh -lc ip route show default | head -n 1": "default via 192.168.15.1 dev eth-onboard",
        }.get(" ".join(args), fallback),
    )
    monkeypatch.setattr(mod, "url_status", lambda url, timeout=5: "200")

    summary = mod.collect_summary()

    assert "ALERTA boot finalizado com 1 falha(s) critica(s)" in summary
    assert "docker=FAILED" in summary
    assert "eddie-whatsapp-bot.service=FAILED" in summary
    assert "Failed units: eddie-whatsapp-exporter.service" in summary


def test_send_via_agent_api_falls_back_to_legacy(monkeypatch) -> None:
    """Se o endpoint atual falhar, o legado deve ser tentado."""
    calls: list[str] = []

    def fake_post_json(url: str, payload: dict[str, object], timeout: int = 10) -> dict[str, object]:
        calls.append(url)
        if url.endswith("/notify/telegram"):
            raise RuntimeError("404")
        return {"success": True, "payload": payload}

    monkeypatch.setattr(mod, "post_json", fake_post_json)

    result = mod.send_via_agent_api("boot ok")

    assert result["success"] is True
    assert calls == [mod.AGENT_NOTIFY_URL, mod.AGENT_NOTIFY_LEGACY_URL]
