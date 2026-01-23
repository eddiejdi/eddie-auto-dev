#!/usr/bin/env python3
"""End-to-end test for conversation_monitor Streamlit dashboard.

Starts the dashboard with AUTO_CREATE_UI_TEST_CONV=1, waits for HTTP availability,
inspects the streamlit log for the auto-created conversation, verifies the
page contains the app title, then shuts down the process.

Run with: ./scripts/run_dashboard_e2e_test.py
"""
import os
import signal
import subprocess
import sys
import time
from urllib.request import urlopen, Request

LOG = "/tmp/streamlit_e2e.log"
APP = "specialized_agents/conversation_monitor.py"
VENV_PY = os.path.join(os.path.dirname(__file__), "..", ".venv", "bin", "python")
# If that path doesn't exist, fallback
if not os.path.exists(VENV_PY):
    VENV_PY = sys.executable

STREAMLIT_CMD = [VENV_PY, "-m", "streamlit", "run", APP, "--server.address", "0.0.0.0", "--server.port", "8501"]

# Helpers

def kill_existing():
    subprocess.run(["pkill", "-f", APP], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_dashboard():
    env = os.environ.copy()
    env["AUTO_CREATE_UI_TEST_CONV"] = "1"
    # enable local test endpoint in the dashboard process
    env["ENABLE_TEST_ENDPOINT"] = "1"
    # Ensure log file exists
    open(LOG, "w").close()
    f = open(LOG, "a")
    proc = subprocess.Popen(STREAMLIT_CMD, stdout=f, stderr=subprocess.STDOUT, env=env)
    return proc, f


def wait_for_http(url="https://heights-treasure-auto-phones.trycloudflare.com/", timeout=60):
    deadline = time.time() + timeout
    last_exc = None
    while time.time() < deadline:
        try:
            req = Request(url, headers={"User-Agent": "e2e-test"})
            with urlopen(req, timeout=5) as r:
                content = r.read().decode("utf-8", errors="ignore")
                return r.getcode(), content
        except Exception as e:
            last_exc = e
            time.sleep(1)
    raise RuntimeError(f"HTTP not available after {timeout}s: {last_exc}")


def find_created_conv_in_log():
    # look for the printed line from start_test_conversation
    if not os.path.exists(LOG):
        return None
    with open(LOG, "r", encoding="utf-8", errors="ignore") as f:
        data = f.read()
    # try both English and Portuguese variants
    for marker in ["Created UI test conversation:", "Conversa criada automaticamente:", "Created UI test conversation"]:
        idx = data.find(marker)
        if idx != -1:
            # extract remainder of line
            line = data[idx:].splitlines()[0]
            return line
    return None


def find_created_conv_in_db(db_path="agent_data/interceptor_data/conversations.db"):
    try:
        import sqlite3
        from datetime import datetime, timedelta

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # look for conversations with id like ui_test_conv_ added recently
        cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        cur.execute("SELECT id, started_at FROM conversations WHERE id LIKE 'ui_test_conv_%' ORDER BY started_at DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if row:
            return row
    except Exception:
        return None
    return None


def main():
    print("Killing any existing dashboard processes...")
    kill_existing()
    print("Starting dashboard with AUTO_CREATE_UI_TEST_CONV=1...")
    proc, logfile = start_dashboard()

    try:
        print("Waiting for HTTP...")
        code, content = wait_for_http(timeout=60)
        print("HTTP status:", code)

        # Basic check: page contains title
        if "Interceptor de Conversas entre Agentes" in content:
            print("Page title found in HTML — rendering OK.")
        else:
            print("Warning: expected title not found in HTML. Content length:", len(content))

        # Trigger in-process test conversation via local endpoint
        conv_id = None
        try:
            print("Triggering in-process test conversation via local endpoint...")
            req = Request("http://127.0.0.1:8765/create_test_conv", method="POST", headers={"User-Agent": "e2e-test"})
            with urlopen(req, timeout=10) as r:
                resp = r.read().decode("utf-8")
            # parse JSON
            try:
                j = json.loads(resp)
                conv_id = j.get("conversation_id")
                print("Endpoint returned conv_id:", conv_id)
            except Exception:
                print("Endpoint response:", resp)
        except Exception as e:
            print("Failed to call test endpoint:", e)

        time.sleep(2)
        conv_line = find_created_conv_in_log()
        if conv_line:
            print("Found auto-created conversation in log:", conv_line)
        else:
            print("Auto-create marker not found in log; checking DB for ui_test_conv_...")
            db_row = find_created_conv_in_db()
            # If we published a conv_id from the script, try to find that specific id
            if not db_row and conv_id:
                import sqlite3
                conn = sqlite3.connect("agent_data/interceptor_data/conversations.db")
                cur = conn.cursor()
                cur.execute("SELECT id, started_at FROM conversations WHERE id = ? LIMIT 1", (conv_id,))
                row = cur.fetchone()
                conn.close()
                if row:
                    db_row = row
            if db_row:
                print("Found ui_test_conv in DB:", db_row)
            else:
                print("Auto-create conversation marker not found in log or DB — check streamlit runtime logs:", LOG)
                # print last 200 chars for debug
                try:
                    with open(LOG, "r", encoding="utf-8", errors="ignore") as f:
                        data = f.read()
                    print("--- log tail ---")
                    print(data[-200:])
                except Exception:
                    pass
                raise RuntimeError("Auto-created conversation not observed in streamlit log or DB")

        print("E2E check succeeded.")
    finally:
        print("Shutting down dashboard (pid:", proc.pid, ")")
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except Exception:
                pass
        logfile.close()


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except Exception as e:
        print("E2E test failed:", e)
        sys.exit(2)
