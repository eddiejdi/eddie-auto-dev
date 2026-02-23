#!/usr/bin/env python3
"""
Muda a cor da janela do VS Code baseado no estado dos agentes.

Cores são INDEPENDENTES por agente. O estado de maior prioridade entre
todos os agentes ativos define a cor exibida na janela.

Prioridade (maior → menor): error > prompt > processing > done > reset

Cada agente registra seu estado com um ID. Quando um agente termina
(done/reset), apenas o SEU registro é atualizado. Se outro agente
ainda estiver em processing, a janela permanece amarela.

Estados:
  processing  → Amarelo (IA trabalhando)
  done        → Verde (IA finalizou com sucesso)
  error       → Vermelho (IA encontrou erro)
  prompt      → Laranja piscante (IA aguardando input do usuário)
  reset       → Remove este agente do tracking

Uso:
  python tools/vscode_window_state.py <estado> [--agent-id <id>]

  # Agente padrão (sem ID = "default")
  python tools/vscode_window_state.py processing

  # Agente específico
  python tools/vscode_window_state.py processing --agent-id agent-1
  python tools/vscode_window_state.py done --agent-id agent-1

  # Listar agentes ativos
  python tools/vscode_window_state.py status
"""

import json
import sys
import os
import time
import subprocess
import fcntl
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(REPO_ROOT, ".vscode", "settings.json")
STATE_FILE = os.path.join(REPO_ROOT, ".vscode", ".agent_states.json")

# Prioridade: maior número = maior prioridade na exibição
STATE_PRIORITY = {
    "done": 1,
    "processing": 2,
    "prompt": 3,
    "error": 4,
}

# Paletas de cores por estado
COLORS = {
    "processing": {
        "titleBar.activeBackground": "#f9a825",
        "titleBar.activeForeground": "#000000",
        "titleBar.inactiveBackground": "#f57f17",
        "titleBar.inactiveForeground": "#000000cc",
        "activityBar.background": "#f9a825",
        "activityBar.foreground": "#000000",
        "statusBar.background": "#f57f17",
        "statusBar.foreground": "#000000",
    },
    "done": {
        "titleBar.activeBackground": "#2e7d32",
        "titleBar.activeForeground": "#ffffff",
        "titleBar.inactiveBackground": "#1b5e20",
        "titleBar.inactiveForeground": "#ffffffcc",
        "activityBar.background": "#2e7d32",
        "activityBar.foreground": "#ffffff",
        "statusBar.background": "#1b5e20",
        "statusBar.foreground": "#ffffff",
    },
    "error": {
        "titleBar.activeBackground": "#c62828",
        "titleBar.activeForeground": "#ffffff",
        "titleBar.inactiveBackground": "#b71c1c",
        "titleBar.inactiveForeground": "#ffffffcc",
        "activityBar.background": "#c62828",
        "activityBar.foreground": "#ffffff",
        "statusBar.background": "#b71c1c",
        "statusBar.foreground": "#ffffff",
    },
    "prompt": {
        "titleBar.activeBackground": "#ff6f00",
        "titleBar.activeForeground": "#ffffff",
        "titleBar.inactiveBackground": "#e65100",
        "titleBar.inactiveForeground": "#ffffffcc",
        "activityBar.background": "#ff6f00",
        "activityBar.foreground": "#ffffff",
        "statusBar.background": "#e65100",
        "statusBar.foreground": "#ffffff",
    },
    "prompt_flash": {
        "titleBar.activeBackground": "#ffab00",
        "titleBar.activeForeground": "#000000",
        "titleBar.inactiveBackground": "#ff8f00",
        "titleBar.inactiveForeground": "#000000cc",
        "activityBar.background": "#ffab00",
        "activityBar.foreground": "#000000",
        "statusBar.background": "#ff8f00",
        "statusBar.foreground": "#000000",
    },
}

# TTL em segundos — agentes inativos há mais de 10 min são removidos automaticamente
AGENT_TTL_SECONDS = 600


def read_settings():
    """Lê o settings.json atual."""
    try:
        with open(SETTINGS_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_settings(settings):
    """Salva o settings.json."""
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=4)
        f.write("\n")


def read_agent_states():
    """Lê o arquivo de estados dos agentes com lock."""
    try:
        with open(STATE_FILE, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_agent_states(states):
    """Salva o arquivo de estados dos agentes com lock exclusivo."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump(states, f, indent=2)
        f.write("\n")
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def cleanup_stale_agents(states):
    """Remove agentes inativos há mais de AGENT_TTL_SECONDS."""
    now = datetime.now(timezone.utc).timestamp()
    to_remove = []
    for agent_id, info in states.items():
        updated = info.get("updated", 0)
        if now - updated > AGENT_TTL_SECONDS:
            to_remove.append(agent_id)
    for agent_id in to_remove:
        del states[agent_id]
    return states


def resolve_winning_state(states):
    """Determina o estado de maior prioridade entre todos os agentes ativos."""
    if not states:
        return "done"  # Sem agentes = tudo ok

    best_state = "done"
    best_priority = 0

    for agent_id, info in states.items():
        state = info.get("state", "done")
        priority = STATE_PRIORITY.get(state, 0)
        if priority > best_priority:
            best_priority = priority
            best_state = state

    return best_state


def update_agent_state(agent_id, state):
    """Registra o estado de um agente e aplica a cor de maior prioridade."""
    states = read_agent_states()
    states = cleanup_stale_agents(states)

    now = datetime.now(timezone.utc)

    if state == "reset":
        states.pop(agent_id, None)
    else:
        states[agent_id] = {
            "state": state,
            "updated": now.timestamp(),
            "updated_iso": now.isoformat(),
        }

    write_agent_states(states)

    # Resolver a cor que deve ser exibida
    winning = resolve_winning_state(states)
    apply_colors(winning)

    # Resumo
    active = {k: v["state"] for k, v in states.items()}
    print(f"✅ [{agent_id}] → {state} | Janela → {winning} | Ativos: {active}")


def apply_colors(state):
    """Aplica as cores ao settings.json sem lógica de agentes."""
    settings = read_settings()

    # Garantir titleBarStyle custom no Linux (necessário para cores na title bar)
    if sys.platform.startswith("linux"):
        if settings.get("window.titleBarStyle") != "custom":
            settings["window.titleBarStyle"] = "custom"

    if state == "reset" or state not in COLORS:
        settings.pop("workbench.colorCustomizations", None)
        write_settings(settings)
        return

    colors = COLORS[state]
    existing = settings.get("workbench.colorCustomizations", {})
    existing.update(colors)
    settings["workbench.colorCustomizations"] = existing
    write_settings(settings)


def flash_prompt(agent_id):
    """Alterna cores para simular 'piscando' ao aguardar prompt do usuário."""
    # Registrar estado prompt primeiro
    states = read_agent_states()
    states = cleanup_stale_agents(states)
    now = datetime.now(timezone.utc)
    states[agent_id] = {
        "state": "prompt",
        "updated": now.timestamp(),
        "updated_iso": now.isoformat(),
    }
    write_agent_states(states)

    # Tentar trazer VS Code para frente
    try:
        subprocess.run(
            ["wmctrl", "-a", "Visual Studio Code"],
            capture_output=True, timeout=2
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Só piscar se prompt é o estado vencedor
    winning = resolve_winning_state(states)
    if winning == "prompt":
        for i in range(6):
            color_state = "prompt" if i % 2 == 0 else "prompt_flash"
            apply_colors(color_state)
            time.sleep(0.5)
        apply_colors("prompt")
    else:
        apply_colors(winning)

    active = {k: v["state"] for k, v in states.items()}
    print(f"✅ [{agent_id}] → prompt | Janela → {winning} | Ativos: {active}")


def show_status():
    """Mostra o estado de todos os agentes ativos."""
    states = read_agent_states()
    states = cleanup_stale_agents(states)
    write_agent_states(states)

    if not states:
        print("Nenhum agente ativo.")
        return

    winning = resolve_winning_state(states)
    print(f"Estado da janela: {winning}")
    print(f"{'Agente':<20} {'Estado':<12} {'Atualizado'}")
    print("-" * 55)
    for agent_id, info in sorted(states.items()):
        print(f"{agent_id:<20} {info['state']:<12} {info.get('updated_iso', '?')}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python tools/vscode_window_state.py <estado> [--agent-id <id>]")
        print("Estados: processing, done, error, prompt, reset, status")
        print("\nExemplos:")
        print("  python tools/vscode_window_state.py processing --agent-id agent-1")
        print("  python tools/vscode_window_state.py done --agent-id agent-1")
        print("  python tools/vscode_window_state.py status")
        sys.exit(1)

    state = sys.argv[1].lower()

    # Extrair --agent-id
    agent_id = "default"
    if "--agent-id" in sys.argv:
        idx = sys.argv.index("--agent-id")
        if idx + 1 < len(sys.argv):
            agent_id = sys.argv[idx + 1]

    if state == "status":
        show_status()
    elif state == "prompt":
        flash_prompt(agent_id)
    else:
        if state not in STATE_PRIORITY and state != "reset":
            print(f"❌ Estado desconhecido: {state}")
            print(f"   Estados válidos: processing, done, error, prompt, reset, status")
            sys.exit(1)
        update_agent_state(agent_id, state)


if __name__ == "__main__":
    main()
