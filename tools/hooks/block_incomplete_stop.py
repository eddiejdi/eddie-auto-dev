#!/usr/bin/env python3
"""Stop hook — barra o encerramento da sessão do Claude Code enquanto houver tarefa incompleta.

Quando o agente tenta parar, escaneia o working tree (git diff HEAD) em busca de marcadores
de ALTO SINAL de trabalho incompleto (via tools/hooks/incomplete_markers.py). Se encontrar,
devolve {"decision": "block", "reason": ...} — o Claude Code é obrigado a continuar e
completar, em vez de deixar stubs/NotImplementedError/elipses de código para trás.

Proteções contra travamento eterno (memória: incidente 2026-05-23, "hooks quebrados = parar tudo"):
  - Escape hatch: ALLOW_INCOMPLETE=1 no ambiente libera imediatamente.
  - Anti-loop: no máximo MAX_BLOCKS re-prompts por sessão; depois libera com aviso.
  - Fail-open: qualquer erro interno NUNCA bloqueia o encerramento.

Registrado no evento `Stop` de .claude/settings.json. Não se aplica ao Copilot (que não
possui evento de encerramento) — para esse caso a rede é o git pre-commit.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import incomplete_markers as im  # noqa: E402

MAX_BLOCKS = 3  # re-prompts por sessão antes de liberar com aviso
MAX_LISTED = 12  # achados listados no reason


def _counter_path(session: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session)[:64]
    return Path(f"/tmp/claude-incomplete-{safe or 'default'}.count")


def _read_count(path: Path) -> int:
    try:
        return int(path.read_text().strip() or "0")
    except (OSError, ValueError):
        return 0


def _write_count(path: Path, value: int) -> None:
    try:
        path.write_text(str(value))
    except OSError:
        pass


def _allow() -> int:
    """Permite o encerramento (não imprime decisão de bloqueio)."""
    print(json.dumps({"continue": True}))
    return 0


def main() -> int:
    raw = sys.stdin.read().strip()
    payload = json.loads(raw) if raw else {}

    # Escape hatch explícito.
    if os.environ.get("ALLOW_INCOMPLETE", "").strip() in ("1", "true", "yes"):
        return _allow()

    session = str(payload.get("session_id") or payload.get("sessionId") or "default")
    counter = _counter_path(session)

    # Posiciona no diretório do projeto para o git enxergar o repo correto.
    cwd = payload.get("cwd") or payload.get("working_directory") or payload.get("workingDirectory")
    if cwd and os.path.isdir(str(cwd)):
        try:
            os.chdir(str(cwd))
        except OSError:
            pass

    findings = im.find_incomplete(im.working_tree_diff(), im.read_worktree_file)

    if not findings:
        # Nada pendente: zera o contador e libera.
        if counter.exists():
            try:
                counter.unlink()
            except OSError:
                pass
        return _allow()

    # Anti-loop: se já insistimos MAX_BLOCKS vezes, libera com aviso (não trava a sessão).
    count = _read_count(counter)
    if count >= MAX_BLOCKS:
        try:
            counter.unlink()
        except OSError:
            pass
        n = len(findings)
        print(json.dumps({
            "systemMessage": (
                f"⚠️ Encerrando com {n} marcador(es) de tarefa incompleta ainda presente(s) "
                f"após {MAX_BLOCKS} tentativas. Revise manualmente ou rode "
                f"`python3 tools/hooks/incomplete_markers.py --staged`."
            )
        }))
        return 0

    _write_count(counter, count + 1)

    shown = findings[:MAX_LISTED]
    lines = "\n".join(f.format() for f in shown)
    extra = f"\n  … e mais {len(findings) - MAX_LISTED} outro(s)." if len(findings) > MAX_LISTED else ""

    reason = (
        f"Você está encerrando com tarefa(s) incompleta(s). Foram detectados "
        f"{len(findings)} marcador(es) de alto sinal (stub/NotImplementedError/elipse de código/"
        f"placeholder) nas mudanças ainda não commitadas:\n\n"
        f"{lines}{extra}\n\n"
        f"Complete a implementação de cada ponto acima antes de encerrar. "
        f"Se algum stub for INTENCIONAL, deixe explícito ao usuário o motivo e "
        f"adicione `# stub-ok` na linha para suprimir o guardrail. "
        f"(tentativa {count + 1}/{MAX_BLOCKS})"
    )

    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # fail-open: bug no hook nunca deve travar o encerramento.
        print(f"[block_incomplete_stop] aviso: hook falhou, liberando ({exc})", file=sys.stderr)
        print(json.dumps({"continue": True}))
        raise SystemExit(0)
