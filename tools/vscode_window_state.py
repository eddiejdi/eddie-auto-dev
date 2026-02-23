#!/usr/bin/env python3
"""
Muda a cor da janela do VS Code baseado no estado do agente.

Estados:
  processing  → Amarelo (IA trabalhando)
  done        → Verde (IA finalizou com sucesso)
  error       → Vermelho (IA encontrou erro)
  prompt      → Laranja piscante (IA aguardando input do usuário)
  reset       → Remove customizações de cor

Uso:
  python tools/vscode_window_state.py processing
  python tools/vscode_window_state.py done
  python tools/vscode_window_state.py error
  python tools/vscode_window_state.py prompt
  python tools/vscode_window_state.py reset
"""

import json
import sys
import os
import time
import subprocess

SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".vscode", "settings.json"
)

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


def set_colors(state: str):
    """Define as cores da janela para o estado dado."""
    if state == "reset":
        settings = read_settings()
        settings.pop("workbench.colorCustomizations", None)
        write_settings(settings)
        print(f"✅ Cores resetadas")
        return

    colors = COLORS.get(state)
    if not colors:
        print(f"❌ Estado desconhecido: {state}")
        print(f"   Estados válidos: {', '.join(COLORS.keys())}, reset")
        sys.exit(1)

    settings = read_settings()
    existing = settings.get("workbench.colorCustomizations", {})
    existing.update(colors)
    settings["workbench.colorCustomizations"] = existing
    write_settings(settings)
    print(f"✅ Janela → {state}")


def flash_prompt(cycles=6, interval=0.5):
    """Alterna cores para simular 'piscando' ao aguardar prompt do usuário."""
    # Tentar trazer VS Code para frente
    try:
        subprocess.run(
            ["wmctrl", "-a", "Visual Studio Code"],
            capture_output=True, timeout=2
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # wmctrl não disponível, segue sem focus

    for i in range(cycles):
        state = "prompt" if i % 2 == 0 else "prompt_flash"
        set_colors(state)
        time.sleep(interval)

    # Finaliza com cor de prompt (laranja fixo)
    set_colors("prompt")


def main():
    if len(sys.argv) < 2:
        print("Uso: python tools/vscode_window_state.py <estado>")
        print("Estados: processing, done, error, prompt, reset")
        sys.exit(1)

    state = sys.argv[1].lower()

    if state == "prompt":
        flash_prompt()
    else:
        set_colors(state)


if __name__ == "__main__":
    main()
