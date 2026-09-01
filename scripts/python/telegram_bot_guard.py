#!/usr/bin/env python3
"""Watchdog: monitora e restaura a descricao do bot Telegram se for adulterada."""
import os, sys, requests, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tg-bot-guard")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BASE  = f"https://api.telegram.org/bot{TOKEN}"

EXPECTED_DESC  = "Bot do homelab Eddie - automacao, IA, monitoramento e infra."
EXPECTED_SHORT = "Homelab Eddie - automacao e IA"

SPAM_MARKERS = ["FREEVPN", "CRYPTO", "vpn38_bot", "t.me/vpn", "PROVNIK", "PROB"]

def get_api(endpoint):
    r = requests.get(f"{BASE}/{endpoint}", timeout=10)
    r.raise_for_status()
    return r.json().get("result", {})

def set_desc(text):
    r = requests.post(f"{BASE}/setMyDescription", data={"description": text}, timeout=10)
    return r.json().get("ok")

def set_short(text):
    r = requests.post(f"{BASE}/setMyShortDescription", data={"short_description": text}, timeout=10)
    return r.json().get("ok")

def is_spam(text):
    return any(m.upper() in text.upper() for m in SPAM_MARKERS)

def check():
    dirty = False

    desc  = get_api("getMyDescription").get("description", "")
    short = get_api("getMyShortDescription").get("short_description", "")

    if is_spam(desc) or desc != EXPECTED_DESC:
        log.warning("ALERTA: description adulterada: %r", desc[:80])
        if set_desc(EXPECTED_DESC):
            log.info("Description restaurada.")
        dirty = True

    if is_spam(short) or short != EXPECTED_SHORT:
        log.warning("ALERTA: short_description adulterada: %r", short[:80])
        if set_short(EXPECTED_SHORT):
            log.info("Short description restaurada.")
        dirty = True

    if dirty:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if chat_id:
            msg = "ALERTA Bot Guard: descricao do bot foi adulterada e restaurada automaticamente!"
            requests.post(f"{BASE}/sendMessage",
                data={"chat_id": chat_id, "text": msg},
                timeout=10)
    else:
        log.info("OK: descricao intacta.")

if __name__ == "__main__":
    if not TOKEN:
        log.error("TELEGRAM_BOT_TOKEN nao definido")
        sys.exit(1)
    check()
