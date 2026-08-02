"""Guard anti-regressão do timer do tuya-token-selfheal.

Incidente 2026-08-02: o timer usava OnBootSec/OnUnitActiveSec (agendamento
monotônico). Após reboot do host o systemd perdeu o disparo
(NextElapse=infinity) e o self-heal nunca mais rodou → token Tuya expirou
e a integração caiu em setup_error (0/82 entidades).

Um timer wall-clock (OnCalendar) + Persistent=true é imune a essa perda.
Estes testes falham se alguém reintroduzir o agendamento monotônico.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TIMER = REPO_ROOT / "systemd" / "tuya-token-selfheal.timer"


def _timer_text() -> str:
    return TIMER.read_text(encoding="utf-8")


def test_timer_exists() -> None:
    assert TIMER.is_file()


def test_timer_uses_calendar_not_monotonic() -> None:
    text = _timer_text()
    assert "OnCalendar=" in text, "onCalendar ausente — reintroduziu monotônico?"
    assert "OnBootSec=" not in text
    assert "OnUnitActiveSec=" not in text


def test_timer_has_randomized_delay() -> None:
    assert "RandomizedDelaySec=" in _timer_text()


def test_timer_is_persistent() -> None:
    assert "Persistent=true" in _timer_text()


def test_timer_target() -> None:
    assert "[Install]" in _timer_text()
    assert "WantedBy=timers.target" in _timer_text()


def test_timer_activates_selfheal_service() -> None:
    assert "Unit=tuya-token-selfheal.service" in _timer_text()
    assert (REPO_ROOT / "systemd" / "tuya-token-selfheal.service").is_file()


def test_deploy_workflow_guards_timer() -> None:
    """O deploy do selfheal precisa reinstalar o timer — regressão aqui
    faria um dex de 'só o script' recair no agendamento bugado."""
    workflow = (
        REPO_ROOT / ".github" / "workflows" / "deploy-tuya-token-selfheal.yml"
    ).read_text(encoding="utf-8")
    assert "tuya-token-selfheal.timer" in workflow
    assert "systemctl" in workflow