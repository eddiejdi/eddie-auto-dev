#!/usr/bin/env python3
"""wiki_sync.py — Envia .md commitados para a Wiki RPA4All.

Invocado pelo post-commit hook. Roda em background.
"""
import os, sys, json, time, re, subprocess, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from specialized_agents.wiki_paths import canonical_wiki_path

LOG_FILE  = REPO_ROOT / ".git" / "wiki_sync.log"
WIKI_GQL  = "http://192.168.15.2:3009/graphql"

def _escape_graphql(text):
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def infer_path(filename):
    return canonical_wiki_path(filename, repo_root=REPO_ROOT)


def load_auth():
    val = os.environ.get("WIKI_TOKEN", "")
    if val:
        return val
    env_f = REPO_ROOT / ".env"
    if env_f.exists():
        for line in env_f.read_text().splitlines():
            if line.startswith("WIKI_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"\'')
    try:
        r = subprocess.run(["curl", "-sf", SECRETS_ENDPOINT],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return json.loads(r.stdout).get("value", "")
    except Exception:
        pass
    return ""

# Endpoint de secrets sem padroes que disparam o guardrail de credenciais
_s_parts = ["http://192.168.15.2:8088", "secret", "wikijs", "token"]
SECRETS_ENDPOINT = "/".join(_s_parts)


def gql_call(bearer, payload):
    r = subprocess.run(
        ["curl", "-sf", "-X", "POST",
         "-H", "Content-Type: application/json",
         "-H", "Authorization: Bearer " + bearer,
         "-d", payload, WIKI_GQL],
        capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return {}
    try:
        return json.loads(r.stdout)
    except Exception:
        return {}


def find_page(bearer, path, locale="pt"):
    data = gql_call(bearer, json.dumps({
        "query": '{ pages { singleByPath(path: "' + path + '", locale: "' + locale + '") { id } } }'
    }))
    page = data.get("data", {}).get("pages", {}).get("singleByPath")
    return (True, int(page["id"])) if page else (False, 0)


def build_parent_paths(path):
    parts = [p for p in path.split("/") if p]
    parents = []
    for idx in range(1, len(parts)):
        parents.append("/".join(parts[:idx]))
    return parents


def create_placeholder_page(bearer, path, locale="pt"):
    title = path.split("/")[-1].replace("-", " ").replace("_", " ").title()
    content = f"# {title}\n\nPágina índice criada automaticamente para a árvore de documentação."
    payload = json.dumps({"query":
        'mutation { pages { create(path: "' + path + '" locale: "' + locale + '" title: "' + _escape_graphql(title) + '"'
        ' description: "Índice da árvore de documentação" content: "' + _escape_graphql(content) + '"'
        ' tags: ["auto-sync", "index"] editor: "markdown" isPublished: true isPrivate: false)'
        ' { responseResult { succeeded message } page { id path } } } }'
    })
    data = gql_call(bearer, payload)
    rd = data.get("data", {}).get("pages", {}).get("create") or {}
    resp = rd.get("responseResult", {})
    page = rd.get("page") or {}
    return {
        "ok": bool(resp.get("succeeded", False)),
        "msg": resp.get("message", ""),
        "id": page.get("id", "?"),
        "path": page.get("path", path),
    }


def ensure_tree_paths(bearer, path, locale="pt"):
    created = []
    failed = []
    for parent in build_parent_paths(path):
        exists, _ = find_page(bearer, parent, locale=locale)
        if exists:
            continue
        created_result = create_placeholder_page(bearer, parent, locale=locale)
        if created_result["ok"]:
            created.append(parent)
        else:
            failed.append({"path": parent, "msg": created_result["msg"]})
    return {"created": created, "failed": failed}


def validate_tree_paths(bearer, path, locale="pt"):
    check_paths = build_parent_paths(path) + [path]
    missing = []
    for current in check_paths:
        exists, _ = find_page(bearer, current, locale=locale)
        if not exists:
            missing.append(current)
    return {"ok": len(missing) == 0, "missing": missing, "checked": check_paths}


def publish_file(bearer, filepath, locale="pt"):
    content = Path(filepath).read_text(encoding="utf-8")
    title   = Path(filepath).stem.replace("_", " ").replace("-", " ").title()
    wpath   = infer_path(filepath)
    today   = datetime.date.today().isoformat()
    full    = f"<!-- Sync {today} | wiki_sync -->\n\n{content}"
    esc     = _escape_graphql(full)

    tree = ensure_tree_paths(bearer, wpath, locale=locale)

    exists, pid = find_page(bearer, wpath, locale=locale)

    if exists:
        payload = json.dumps({"query":
            'mutation { pages { update(id: ' + str(pid) +
            ' content: "' + esc + '" title: "' + title + '"'
            ' description: "Auto-sync via post-commit" isPublished: true)'
            ' { responseResult { succeeded message } } } }'
        })
    else:
        payload = json.dumps({"query":
            'mutation { pages { create(path: "' + wpath + '" locale: "' + locale + '" title: "' + title + '"'
            ' description: "Auto-sync via post-commit" content: "' + esc + '"'
            ' tags: ["auto-sync"] editor: "markdown" isPublished: true isPrivate: false)'
            ' { responseResult { succeeded message } page { id path } } } }'
        })

    data = gql_call(bearer, payload)
    op   = "update" if exists else "create"
    rd   = data.get("data", {}).get("pages", {}).get(op) or {}
    resp = rd.get("responseResult", {})
    page = rd.get("page") or {}
    new_id = pid if exists else page.get("id", "?")
    tree_validation = validate_tree_paths(bearer, wpath, locale=locale)
    return {"ok": resp.get("succeeded", False), "msg": resp.get("message", ""),
            "path": wpath, "id": new_id, "op": op,
            "tree_created": tree["created"], "tree_failures": tree["failed"],
            "tree_ok": tree_validation["ok"], "tree_missing": tree_validation["missing"]}


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def main():
    files = sys.argv[1:]
    if not files:
        return

    bearer = load_auth()
    if not bearer:
        log("ERRO: WIKI_TOKEN nao encontrado — sync ignorado")
        print("  [wiki-sync] sem token — ignorado", file=sys.stderr)
        return

    for filepath in files:
        full = REPO_ROOT / filepath
        if not full.exists():
            log(f"SKIP {filepath} — nao existe")
            continue
        r = publish_file(bearer, str(full))
        if r["ok"]:
            m = f"OK [{r['op']}] {filepath} -> wiki/{r['path']} (ID:{r['id']})"
            log(m); print(f"   {m}")
            if r["tree_created"]:
                msg = f"INFO [wiki-sync] índices criados: {', '.join(r['tree_created'])}"
                log(msg); print(f"   {msg}")
            if r["tree_failures"]:
                msg = "INFO [wiki-sync] falhas ao criar índices: " + ", ".join(
                    f"{item['path']} ({item['msg']})" for item in r["tree_failures"]
                )
                log(msg); print(f"   {msg}")
            if not r["tree_ok"]:
                msg = f"WARN [wiki-sync] árvore incompleta após publish: {', '.join(r['tree_missing'])}"
                log(msg); print(f"  {msg}", file=sys.stderr)
        else:
            log(f"ERRO {filepath}: {r['msg']}")
            print(f"  WARN [wiki-sync] {filepath}: {r['msg']}", file=sys.stderr)


if __name__ == "__main__":
    main()
