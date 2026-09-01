import subprocess, json, urllib.request, re
from pathlib import Path

tf = Path("/tmp/new_tg_token")
token = tf.read_text().strip()

# Busca chat_id via secrets agent
try:
    out = subprocess.check_output(
        ["sudo","systemctl","show","secrets_agent","--property=Environment"],
        text=True, stderr=subprocess.DEVNULL)
    m = re.search(r"SECRETS_AGENT_API_KEY=(\S+)", out)
    api_key = m.group(1) if m else ""
except Exception:
    api_key = ""

chat_id = ""
base_url = "http://localhost:8088"
hdrs = {"Content-Type": "application/json"}
if api_key:
    hdrs["X-API-Key"] = api_key
for field in ("chat_id", "password"):
    try:
        req = urllib.request.Request(
            f"{base_url}/secrets/shared%2Ftelegram_chat_id?field={field}",
            headers=hdrs)
        with urllib.request.urlopen(req, timeout=10) as r:
            v = json.loads(r.read()).get("value", "").strip()
            if v:
                chat_id = v
                break
    except Exception:
        pass
print("chat_id obtido:", bool(chat_id))

# Atualiza /etc/default/eddie-common
r = subprocess.run(["sudo", "cat", "/etc/default/eddie-common"],
                   capture_output=True, text=True)
keep = [l for l in r.stdout.splitlines()
        if not l.startswith("TELEGRAM_BOT_TOKEN=")
        and not l.startswith("TELEGRAM_CHAT_ID=")]
keep.append("TELEGRAM_BOT_TOKEN=" + token)
if chat_id:
    keep.append("TELEGRAM_CHAT_ID=" + chat_id)
tmp = Path("/tmp/.ec_apply")
tmp.write_text("\n".join(keep) + "\n")
subprocess.run(["sudo", "install", "-m", "644", "-o", "root", "-g", "root",
                str(tmp), "/etc/default/eddie-common"], check=True)
tmp.unlink(missing_ok=True)
print("eddie-common OK")

# Reescreve drop-ins com comentarios (sem hardcode de token)
dropin_content = "[Service]\n# token em /etc/default/eddie-common\n# chat_id em /etc/default/eddie-common\n"
for p in [
    "/etc/systemd/system/eddie-telegram-bot.service.d/telegram-token.conf",
    "/etc/systemd/system/eddie-telegram-bot.service.d/token.conf",
]:
    if not Path(p).exists():
        continue
    tmp2 = Path("/tmp/.dp_apply")
    tmp2.write_text(dropin_content)
    subprocess.run(["sudo", "cp", str(tmp2), p], check=True)
    tmp2.unlink(missing_ok=True)
    print("Drop-in OK:", p)

# Atualiza secrets agent
for name, field in [
    ("shared/telegram_bot_token", "token"),
    ("shared/telegram_bot_token", "password"),
]:
    payload = json.dumps({"name": name, "value": token, "field": field}).encode()
    req = urllib.request.Request(
        f"{base_url}/secrets", data=payload, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10):
            print("secrets OK:", name, field)
    except Exception as e:
        print("AVISO secrets:", e)

# Reload + restart servicos
subprocess.run(["sudo", "systemctl", "daemon-reload"])
for svc in ["eddie-telegram-bot", "pandaplus-telegram-bridge",
            "alertmanager-telegram-webhook", "telegram-bus-agent"]:
    r2 = subprocess.run(["systemctl", "is-enabled", "--quiet", svc],
                        capture_output=True)
    if r2.returncode == 0:
        subprocess.run(["sudo", "systemctl", "restart", svc])
        print("Reiniciado:", svc)

import time
time.sleep(3)
for svc in ["eddie-telegram-bot", "pandaplus-telegram-bridge"]:
    r3 = subprocess.run(["systemctl", "is-active", svc],
                        capture_output=True, text=True)
    print(svc + ":", r3.stdout.strip())
