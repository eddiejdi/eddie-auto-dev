#!/usr/bin/env python3
"""Watcher: aguarda sessão WAHA ficar WORKING e executa `test_whatsapp.py` automaticamente."""
import time
import os
import subprocess
import sys
import httpx

WAHA_URL = os.environ.get("WAHA_URL", "http://localhost:3000")
API_KEY = os.environ.get("WAHA_API_KEY", "devkey")
SESSION = os.environ.get("WAHA_SESSION", "default")
CHECK_INTERVAL = int(os.environ.get("WAHA_POLL_INTERVAL", "5"))
TIMEOUT = int(os.environ.get("WAHA_POLL_TIMEOUT", "900"))

def get_status():
    try:
        r = httpx.get(f"{WAHA_URL}/api/sessions/{SESSION}", headers={"X-Api-Key": API_KEY}, timeout=10)
        return r.json().get("status", "")
    except Exception:
        return ""

def run_test():
    env = os.environ.copy()
    env["WAHA_API_KEY"] = API_KEY
    env["PYTHONPATH"] = env.get("PYTHONPATH", ".")
    python = os.path.join("site", "code_runner", ".venv", "bin", "python")
    cmd = [python, "test_whatsapp.py"]
    print("[watcher] Executando:", " ".join(cmd))
    p = subprocess.run(cmd, env=env)
    return p.returncode

def main():
    start = time.time()
    print("[watcher] Iniciado: monitorando sessão WAHA (session=", SESSION, ")")
    while True:
        st = get_status()
        print(time.strftime("%H:%M:%S"), "status=", st)
        if st == "WORKING":
            print("[watcher] Sessão WORKING detectada — rodando teste.")
            rc = run_test()
            print("[watcher] Test finalizado, exit code", rc)
            sys.exit(rc)
        if time.time() - start > TIMEOUT:
            print("[watcher] Timeout atingido, encerrando.")
            sys.exit(2)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
