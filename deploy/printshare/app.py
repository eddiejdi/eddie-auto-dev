import os
import subprocess
import json
import uuid
import base64
from flask import Flask, request, jsonify

app = Flask(__name__)

BAUD = int(os.environ.get("BAUDRATE", "9600"))
PORT = os.environ.get("PRINTER_PORT", "")
HINT = os.environ.get("PORT_HINT", "PHOMEMO")
PHOMEMO_SCRIPT = os.environ.get("PHOMEMO_SCRIPT", "/home/homelab/agents_workspace/phomemo_print.py")
CUPS_PRINTER = os.environ.get("CUPS_PRINTER", "")


def run_cmd(cmd, timeout=60):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/status", methods=["GET"])
def status():
    cmd = ["python3", PHOMEMO_SCRIPT, "--status", "--baud", str(BAUD)]
    if PORT:
        cmd.extend(["--port", PORT])
    else:
        cmd.extend(["--hint", HINT])

    code, out, err = run_cmd(cmd, timeout=15)
    if code == 0:
        try:
            data = json.loads(out)
            return jsonify({"ok": True, "data": data})
        except Exception:
            return jsonify({"ok": True, "raw": out})
    else:
        return jsonify({"ok": False, "error": err or out}), 500


@app.route("/print", methods=["POST"])
def print_job():
    job = request.get_json()
    if not job:
        return jsonify({"error": "missing json body"}), 400

    typ = job.get("type", "text")

    if typ == "text":
        text = job.get("content", "")
        if not text:
            return jsonify({"error": "empty content"}), 400
        # If a CUPS printer is configured, use lp to submit the job
        if CUPS_PRINTER:
            tmp_path = f"/tmp/print_{uuid.uuid4().hex}.txt"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(text)
            cmd = ["lp"]
            if CUPS_PRINTER:
                cmd.extend(["-d", CUPS_PRINTER])
            cmd.append(tmp_path)
            code, out, err = run_cmd(cmd, timeout=30)
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            if code == 0:
                return jsonify({"ok": True, "message": out or "queued"})
            else:
                return jsonify({"ok": False, "error": err or out}), 500

        # Fallback: use Phomemo serial driver
        cmd = ["python3", PHOMEMO_SCRIPT, "--text", text, "--baud", str(BAUD)]
        if PORT:
            cmd.extend(["--port", PORT])
        else:
            cmd.extend(["--hint", HINT])

        code, out, err = run_cmd(cmd, timeout=30)
        if code == 0:
            return jsonify({"ok": True, "message": out})
        else:
            return jsonify({"ok": False, "error": err or out}), 500

    elif typ == "image":
        image_b64 = job.get("content")
        if not image_b64:
            return jsonify({"error": "missing image content"}), 400
        try:
            data = base64.b64decode(image_b64)
        except Exception:
            return jsonify({"error": "invalid base64"}), 400
        tmp_path = f"/tmp/print_{uuid.uuid4().hex}.png"
        with open(tmp_path, "wb") as f:
            f.write(data)

        # If CUPS printer configured, send image to CUPS
        if CUPS_PRINTER:
            cmd = ["lp", "-d", CUPS_PRINTER, tmp_path]
        else:
            cmd = ["python3", PHOMEMO_SCRIPT, "--image", tmp_path, "--baud", str(BAUD)]
            if PORT:
                cmd.extend(["--port", PORT])
            else:
                cmd.extend(["--hint", HINT])

        code, out, err = run_cmd(cmd, timeout=60)
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        if code == 0:
            return jsonify({"ok": True, "message": out})
        else:
            return jsonify({"ok": False, "error": err or out}), 500

    else:
        return jsonify({"error": "unsupported type"}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8085)))
