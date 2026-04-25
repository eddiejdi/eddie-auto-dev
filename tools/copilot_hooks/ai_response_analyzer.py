from __future__ import annotations

import json
import sys
from typing import Any


def _load_input() -> dict[str, Any]:
    """Lê o payload JSON do stdin e retorna um dicionário.

    Retorna um dicionário vazio se stdin estiver vazio.
    """
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    """Analisa a resposta do assistente e produz uma decisão de hook.

    Implementação mínima: sempre permite continuar (não bloqueia).
    Esta versão serve como stub para evitar erros quando o hook tenta
    invocar o analisador que pode estar ausente em ambientes locais.
    """
    # Implementação simples: não bloquear nem pedir confirmação
    return {"continue": True}


def main() -> int:
    payload = _load_input()
    result = analyze(payload)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
