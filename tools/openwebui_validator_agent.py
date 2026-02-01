#!/usr/bin/env python3
import requests
import json
import time
from typing import Dict

ENV_TARGETS = {
    "dev": "http://192.168.15.2:3000",
    "cer": "http://192.168.15.2:3000",
    "prod": "http://192.168.15.2:3000",
}

CHECKS = [
    "root",
    "api_config",
    "static_loader",
    "signin",
    "create_chat",
    "list_chats",
]

ADMIN_CRED = {"email": "admin@localhost", "password": "admin"}


def check_root(base: str, s: requests.Session, out: Dict):
    try:
        r = s.get(base, timeout=10)
        out["root"] = {"status_code": r.status_code, "ok": r.ok}
    except Exception as e:
        out["root"] = {"error": str(e)}


def check_api_config(base: str, s: requests.Session, out: Dict):
    for p in ("/api/config", "/api/v1/config", "/api/config/"):
        try:
            r = s.get(base.rstrip("/") + p, timeout=10)
            if r.status_code == 200:
                out["api_config"] = {"path": p, "json": r.json()}
                return
        except Exception as e:
            out.setdefault("api_config_errors", []).append({p: str(e)})
    out.setdefault("api_config_errors", []).append("no-200-response")


def check_static_loader(base: str, s: requests.Session, out: Dict):
    try:
        r = s.get(base.rstrip("/") + "/static/loader.js", timeout=10)
        out["static_loader"] = {"status_code": r.status_code, "length": len(r.content)}
    except Exception as e:
        out["static_loader"] = {"error": str(e)}


def attempt_signin(base: str, s: requests.Session, out: Dict):
    try:
        r = s.post(
            base.rstrip("/") + "/api/v1/auths/signin", json=ADMIN_CRED, timeout=10
        )
        out["signin_raw_status"] = r.status_code
        try:
            out["signin_raw_json"] = r.json()
        except Exception:
            out["signin_raw_text"] = r.text
        if r.ok:
            token = r.json().get("token")
            out["token_present"] = bool(token)
            return token
    except Exception as e:
        out["signin_error"] = str(e)
    return None


def create_chat(base: str, session_token: str, out: Dict):
    try:
        s = requests.Session()
        headers = {
            "Authorization": f"Bearer {session_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "chat": {
                "history": {
                    "messages": {
                        "m1": {
                            "id": "m1",
                            "role": "user",
                            "content": "Validation ping",
                            "timestamp": int(time.time()),
                        }
                    },
                    "currentId": "m1",
                }
            }
        }
        r = s.post(
            base.rstrip("/") + "/api/v1/chats/new",
            headers=headers,
            json=payload,
            timeout=15,
        )
        out["create_chat_status"] = r.status_code
        try:
            out["create_chat_json"] = r.json()
        except Exception:
            out["create_chat_text"] = r.text
    except Exception as e:
        out["create_chat_error"] = str(e)


def list_chats(base: str, session_token: str, out: Dict):
    try:
        s = requests.Session()
        headers = {"Authorization": f"Bearer {session_token}"}
        r = s.get(base.rstrip("/") + "/api/v1/chats/list", headers=headers, timeout=10)
        out["list_chats_status"] = r.status_code
        try:
            out["list_chats_json"] = r.json()
        except Exception:
            out["list_chats_text"] = r.text
    except Exception as e:
        out["list_chats_error"] = str(e)


def run_checks_for_env(name: str, base: str) -> Dict:
    out = {"env": name, "base": base, "timestamp": int(time.time()), "checks": {}}
    s = requests.Session()
    # root
    check_root(base, s, out["checks"])
    # api config
    check_api_config(base, s, out["checks"])
    # static loader
    check_static_loader(base, s, out["checks"])
    # signin
    token = attempt_signin(base, s, out["checks"])
    if token:
        # create chat
        create_chat(base, token, out["checks"])
        list_chats(base, token, out["checks"])
    else:
        out["checks"]["note"] = "no token; chat checks skipped"
    return out


if __name__ == "__main__":
    report = {}
    for env, url in ENV_TARGETS.items():
        print(f"Running validation for {env} -> {url}")
        report[env] = run_checks_for_env(env, url)
        fn = f"/tmp/openwebui_validation_{env}.json"
        with open(fn, "w") as f:
            json.dump(report[env], f, indent=2)
        print(f"Saved report to {fn}")
    # combine
    combo = "/tmp/openwebui_validation_summary.json"
    with open(combo, "w") as f:
        json.dump(report, f, indent=2)
    print("Validation complete. Summary saved to", combo)
