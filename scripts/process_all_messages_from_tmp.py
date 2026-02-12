import json
import os
import sqlite3
import base64
import urllib.request
import urllib.error
from datetime import datetime

WAHA_API = os.getenv("WAHA_URL", "http://127.0.0.1:3001")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL_NAME = os.getenv("WHATSAPP_MODEL", "eddie-whatsapp:latest")
MESSAGES_PER_CHAT = int(os.getenv("WAHA_MESSAGES_PER_CHAT", "500"))

JOB_TERMS = [
    "vaga", "oportunidade", "contrat", "selecion", "processo seletivo",
    "clt", "pj", "remoto", "hibrido", "presencial", "salario", "requisitos",
    "devops", "sre", "engenheiro", "engenheira", "cloud", "kubernetes",
    "aws", "gcp", "azure", "infraestrutura", "plataforma", "desenvolvedor",
    "analista", "senior", "junior", "pleno", "tech lead", "architect"
]

PRODUCT_INDICATORS = [
    "r$", "reais", "desconto", "compre", "oferta", "promoção", "mercado",
    "🔥", "💰", "🛒", "link:", "comprar", "frete", "parcelado", "à vista",
    "http", "https", "loja", "cupom", "pix"
]


def get_waha_api_key():
    env_key = os.getenv("WAHA_API_KEY")
    if env_key:
        return env_key
    db_path = "/var/lib/eddie/secrets_agent/audit.db"
    if not os.path.exists(db_path):
        raise RuntimeError("WAHA_API_KEY not found and secrets DB missing")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT value FROM secrets_store WHERE name=\"eddie/waha_api_key\"")
    row = cur.fetchone()
    conn.close()
    if not row:
        raise RuntimeError("WAHA_API_KEY not found in secrets DB")
    try:
        return base64.b64decode(row[0]).decode()
    except Exception:
        return row[0]


def http_get(url, headers, timeout=15):
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        return e.code, body
    except Exception:
        return 0, ""
        body = e.read().decode("utf-8", errors="ignore")
        return e.code, body


def call_ollama(prompt, temperature=0.1):
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "num_predict": 20
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return json.loads(body).get("response", "").strip()
    except Exception:
        return None


def classify_message_rule(text):
    if not text or len(text) < 30:
        return "ignore", "short_or_empty"
    lower = text.lower()
    if any(ind in lower for ind in PRODUCT_INDICATORS):
        return "false_positive", "product_indicator"
    if any(term in lower for term in JOB_TERMS):
        return "job", "job_terms"
    return "ignore", "no_job_terms"


def classify_message_llm(text):
    if not text or len(text) < 30:
        return "ignore", "short_or_empty"
    prompt = (
        "Voce e um classificador de mensagens. Diga se o texto e uma vaga de emprego.\n\n"
        "Responda APENAS com um dos rotulos abaixo:\n"
        "- JOB\n- FALSE_POSITIVE\n- IGNORE\n\n"
        "Texto:\n"
    ) + text[:1200]
    response = call_ollama(prompt, temperature=0.1)
    if not response:
        return "ignore", "llm_no_response"
    label = response.strip().upper()
    if "JOB" in label:
        return "job", "llm_job"
    if "FALSE" in label:
        return "false_positive", "llm_false_positive"
    if "IGNORE" in label:
        return "ignore", "llm_ignore"
    return "ignore", "llm_unknown"


def is_group(chat):
    cid = chat.get("id") or chat.get("chatId") or ""
    return ("@g.us" in cid) or chat.get("isGroup") is True or chat.get("type") == "group"


def main():
    api_key = get_waha_api_key()
    headers = {"X-Api-Key": api_key, "Accept": "application/json"}

    status, sessions_out = http_get(f"{WAHA_API}/api/sessions", headers)
    if status != 200:
        print(f"Sessions status: {status}")
        print(sessions_out[:200])
        return

    sessions = json.loads(sessions_out)
    if isinstance(sessions, dict):
        sessions = sessions.get("data") or sessions
    if not sessions:
        print("No sessions found")
        return

    session_name = sessions[0].get("name") or sessions[0].get("id") or sessions[0].get("session") or "default"
    status, chats_out = http_get(f"{WAHA_API}/api/{session_name}/chats", headers)
    if status != 200:
        print(f"Chats status: {status}")
        print(chats_out[:200])
        return

    chats = json.loads(chats_out) if chats_out else []
    groups = [c for c in chats if is_group(c)]

    summary = {
        "groups": len(groups),
        "total_messages": 0,
        "job": 0,
        "false_positive": 0,
        "ignore": 0,
        "timestamp": datetime.now().isoformat(),
        "messages_per_chat": MESSAGES_PER_CHAT
    }

    group_stats = []

    for g in groups:
        gid = g.get("id") or g.get("chatId")
        name = g.get("name") or g.get("subject") or g.get("title") or "(no name)"
        status, msgs_out = http_get(f"{WAHA_API}/api/{session_name}/chats/{gid}/messages?limit={MESSAGES_PER_CHAT}", headers)
        if status != 200:
            continue
        msgs = json.loads(msgs_out) if msgs_out else []
        counts = {"job": 0, "false_positive": 0, "ignore": 0}
        for m in msgs:
            text = (m.get("body") or "").strip()
            if not text:
                continue
            rule_label, _ = classify_message_rule(text)
            if rule_label == "false_positive":
                counts["false_positive"] += 1
                continue
            llm_label, _ = classify_message_llm(text)
            counts[llm_label] += 1
        total = sum(counts.values())
        summary["total_messages"] += total
        summary["job"] += counts["job"]
        summary["false_positive"] += counts["false_positive"]
        summary["ignore"] += counts["ignore"]
        group_stats.append({
            "id": gid,
            "name": name,
            "messages": total,
            **counts
        })
        print(f"{name} | messages={total} | job={counts['job']} | false_positive={counts['false_positive']} | ignore={counts['ignore']}")

    out_path = f"/home/homelab/message_audit_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "groups": group_stats}, f, ensure_ascii=False, indent=2)

    print("\nSummary:")
    print(summary)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
