#!/usr/bin/env python3
from __future__ import annotations
"""
send1_loop.py
Envia '1' + Backspace a cada intervalo usando xdotool (X11), wtype (Wayland) ou pyautogui.
"""
import argparse
import shutil
import subprocess
import sys
import time

def has_cmd(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def run_xdotool(interval: float) -> None:
    cmd = ["xdotool", "key", "--clearmodifiers", "1", "BackSpace"]
    print("Using xdotool")
    while True:
        try:
            subprocess.run(cmd, check=False)
        except Exception as e:
            print("xdotool error:", e, file=sys.stderr)
        time.sleep(interval)

def run_wtype(interval: float) -> None:
    print("Using wtype")
    # wtype accepts string arguments; use '\\b' escape for backspace
    while True:
        try:
            subprocess.run(["wtype", "1\\b"], check=False)
        except Exception as e:
            print("wtype error:", e, file=sys.stderr)
        time.sleep(interval)

def run_pyautogui(interval: float) -> None:
    try:
        import pyautogui
    except Exception as e:
        print("pyautogui not available:", e, file=sys.stderr)
        raise
    pyautogui.FAILSAFE = False
    print("Using pyautogui")
    while True:
        try:
            pyautogui.press("1")
            pyautogui.press("backspace")
        except Exception as e:
            print("pyautogui error:", e, file=sys.stderr)
        time.sleep(interval)

def main() -> None:
    parser = argparse.ArgumentParser(description="Send '1' then Backspace repeatedly.")
    parser.add_argument("--interval", "-i", type=float, default=5.0, help="Seconds between presses")
    parser.add_argument("--display", "-d", help="Set DISPLAY environment variable (e.g. :0)")
    args = parser.parse_args()

    if args.display:
        import os
        os.environ["DISPLAY"] = args.display

    if has_cmd("xdotool"):
        run_xdotool(args.interval)
    elif has_cmd("wtype"):
        run_wtype(args.interval)
    else:
        try:
            run_pyautogui(args.interval)
        except Exception:
            print("Nenhuma ferramenta disponível. Instale 'xdotool', 'wtype' ou 'pyautogui'.", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
