"""UserPromptSubmit hook — preferência de internet do usuário.

Quando o usuário fala de internet/rede/conectividade, injeta additionalContext
com a ordem preferida de saída:

1. RJ45 (enp0s31f6 / Wired connection 1) — preferencial
2. Wi-Fi GVT-38AA (SSID GVT-38AA) — preferencial
3. TANK e outros SSIDs — só fallback / diagnóstico secundário

Não altera rotas do sistema: apenas orienta o agente (Claude/Grok/Pi).
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

# Frases/termos que disparam o contexto de preferência de internet.
_TRIGGER_RE = re.compile(
    r"""
    \b(
        minha\s+internet
      | nossa\s+internet
      | a\s+internet
      | internet
      | conectividade
      | sem\s+net
      | sem\s+internet
      | net\s+caiu
      | internet\s+caiu
      | internet\s+inst[aá]vel
      | rede\s+inst[aá]vel
      | wi[\-\s]?fi
      | wifi
      | wlan
      | rj45
      | cabo\s+(de\s+)?rede
      | ethernet
      | enp0s31f6
      | wlp2s0
      | gvt[\-\s]?38aa
      | default\s+route
      | rota\s+padr[aã]o
      | gateway
      | networkmanager
      | nmcli
      | dns
      | ping\b
      | packet\s+loss
      | perda\s+de\s+pacotes
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

CONTEXT = """# Preferência de internet (hook 2026-07-29)

Quando o usuário fala de **internet / rede / conectividade** nesta workstation:

## Ordem preferida de saída
1. **RJ45** — interface `enp0s31f6`, perfil NM `Wired connection 1`, MAC `18:66:da:fe:58:94`, LAN `192.168.15.0/24`
2. **Wi‑Fi GVT-38AA** — SSID `GVT-38AA`, perfis NM `GVT-38AA Automático(a)`, mesma subnet do homelab quando associado
3. **TANK / outros SSIDs** — **não preferidos**; só fallback explícito ou diagnóstico secundário

## Como diagnosticar (ordem)
1. Cabo UP + IP em `enp0s31f6`? (`ip -br a`, `nmcli device status`)
2. Gateway homelab/ISP via cabo: `192.168.15.2` (LAN) e/ou `192.168.15.1` (ZTE GPON)
3. Internet **por interface**: `curl --interface enp0s31f6 -sS --max-time 5 https://1.1.1.1`
4. Se cabo sem WAN: Wi‑Fi **GVT-38AA** (não TANK primeiro): `nmcli device wifi`, `nmcli connection up "GVT-38AA Automático(a)"`
5. Só então considerar TANK (`wlp2s0` em 10.x) como fallback

## Notas operacionais
- RJ45 pode estar com `ipv4.never-default=yes` (só LAN). Preferência do usuário = **tentar internet real pelo cabo** (rota via .1/.2 / isp-bypass no homelab) antes de confiar no Wi‑Fi vizinho TANK.
- Browser/PAC: `http://192.168.15.2/wpad.dat` — depende da rota LAN via cabo.
- Não reconfigure firewall/rotas do homelab sem confirmação; mudanças de NM no notebook ok se forem para priorizar cabo + GVT-38AA.
"""


def _load_input() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _extract_prompt(payload: dict[str, Any]) -> str:
    """Extrai texto do prompt de vários formatos (Claude / Grok / Pi)."""
    candidates: list[Any] = [
        payload.get("prompt"),
        payload.get("user_prompt"),
        payload.get("userPrompt"),
        payload.get("message"),
        payload.get("text"),
        payload.get("content"),
    ]
    # envelopes aninhados comuns
    for key in ("hook_event_input", "hookEventInput", "input"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidates.extend(
                [
                    nested.get("prompt"),
                    nested.get("user_prompt"),
                    nested.get("userPrompt"),
                    nested.get("message"),
                    nested.get("text"),
                ]
            )
    parts: list[str] = []
    for c in candidates:
        if isinstance(c, str) and c.strip():
            parts.append(c)
        elif isinstance(c, list):
            for item in c:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
    return "\n".join(parts)


def matches_internet_topic(text: str) -> bool:
    if not text or not text.strip():
        return False
    return bool(_TRIGGER_RE.search(text))


def build_output(event_name: str = "UserPromptSubmit") -> dict[str, Any]:
    return {
        "continue": True,
        "additionalContext": CONTEXT,
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": CONTEXT,
        },
    }


def main() -> int:
    payload = _load_input()
    event = str(
        payload.get("hook_event_name")
        or payload.get("hookEventName")
        or "UserPromptSubmit"
    )
    # Normaliza nome para saída Claude/Grok
    if event.lower() in {"user_prompt_submit", "usersubmitprompt", "beforesubmitprompt"}:
        event = "UserPromptSubmit"

    prompt = _extract_prompt(payload)
    # Fail-open: sem prompt legível não injeta (evita poluir todos os turns)
    if not matches_internet_topic(prompt):
        print(json.dumps({"continue": True}))
        return 0

    print(json.dumps(build_output(event), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
