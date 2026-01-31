#!/usr/bin/env python3
"""
Server knowledge generator (cleaned).
Collects basic info via SSH and generates a small Markdown doc suitable for RAG.
"""

import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

HOST = "homelab@192.168.15.2"


def run_ssh_command(cmd: str) -> str:
    """Run a command via SSH and return stdout (quiet on error)."""
    try:
        p = subprocess.run(["ssh", HOST, cmd], capture_output=True, text=True, timeout=30)
        return p.stdout.strip()
    except Exception as e:
        return f"Erro: {e}"


def collect_server_info() -> Dict[str, str]:
    """Collects simple server info via SSH with fallbacks."""
    hostname = run_ssh_command("hostname -f || hostname") or "unknown"
    ip = run_ssh_command("ip -6 addr show scope global | awk '/inet6/ {print $2; exit}' | cut -d'/' -f1")
    if not ip:
        ip = run_ssh_command("hostname -I | awk '{print $1}'") or "unknown"
    os_rel = run_ssh_command(". /etc/os-release && echo \"$PRETTY_NAME\"") or "unknown"
    uptime = run_ssh_command("uptime -p || uptime") or "unknown"
    memory_cmd = "free -h --si | awk '/Mem:/ {print $2 \" total, \" $3 \" used\"}'"
    memory = run_ssh_command(memory_cmd) or "unknown"
    disk_cmd = 'df -h / | tail -1 | awk \'{print $4 " free on " $1}\''
    disk = run_ssh_command(disk_cmd) or "unknown"
    timestamp = datetime.utcnow().isoformat() + "Z"

    return {
        "hostname": hostname,
        "ip": ip,
        "os": os_rel,
        "uptime": uptime,
        "memory": memory,
        "disk": disk,
        "timestamp": timestamp,
    }


def collect_docker_info() -> List[Dict[str, str]]:
    """Return list of running containers (name, image, status, ports)."""
    out = run_ssh_command("docker ps --format '{{json .}}' || true")
    containers = []
    if not out:
        return containers
    for line in out.splitlines():
        try:
            j = json.loads(line)
            containers.append({
                "name": j.get("Names", j.get("Names", "")),
                "image": j.get("Image", ""),
                "status": j.get("Status", ""),
                "ports": j.get("Ports", ""),
            })
        except Exception:
            continue
    return containers


def collect_ollama_models() -> List[str]:
    out = run_ssh_command("curl -s http://127.0.0.1:11434/api/tags 2>/dev/null || true")
    try:
        data = json.loads(out)
        return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def collect_systemd_services() -> List[Dict[str, str]]:
    svcs = ["ollama", "docker", "specialized-agents"]
    res = []
    for s in svcs:
        st = run_ssh_command(f"systemctl is-active {s} 2>/dev/null || echo unknown")
        res.append({"name": s, "status": st})
    return res


def collect_project_structure() -> Dict[str, List[str]]:
    out = run_ssh_command("find ~/projects -maxdepth 2 -type d 2>/dev/null | head -50 || true")
    dirs = [d for d in out.splitlines() if d]
    return {"directories": dirs}


def generate_markdown_doc() -> str:
    server = collect_server_info()
    docker = collect_docker_info()
    models = collect_ollama_models()
    services = collect_systemd_services()
    projects = collect_project_structure()

    doc = f"""# Homelab Server - Documentação Curta

**Gerado**: {datetime.utcnow().isoformat()}Z

## Informações
- hostname: {server['hostname']}
- ip: {server['ip']}
- os: {server['os']}
- uptime: {server['uptime']}
- memory: {server['memory']}
- disk: {server['disk']}

## Modelos Ollama
"""
    for m in models:
        doc += f"- {m}\n"

    doc += "\n## Containers Docker\n"
    for c in docker:
        doc += f"- {c['name']} ({c['image']}) - {c['status']} - ports: {c['ports']}\n"

    doc += "\n## Systemd Services\n"
    for s in services:
        doc += f"- {s['name']}: {s['status']}\n"

    doc += "\n## Projetos (amostra)\n"
    for d in projects.get('directories', [])[:20]:
        doc += f"- {d}\n"

    return doc


def save_documentation() -> str:
    doc = generate_markdown_doc()
    local_path = Path.home() / "homelab_documentation.md"
    local_path.write_text(doc)
    # also push to the server path
    subprocess.run(["ssh", HOST, f"cat > ~/projects/homelab-documentation.md << 'END'\n{doc}\nEND"], check=False)
    return doc


if __name__ == '__main__':
    print(generate_markdown_doc())

