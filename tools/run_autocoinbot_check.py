#!/usr/bin/env python3
"""
Diagnóstico e correção mínima para o exporter AutoCoinBot no homelab.
Uso:
  source .venv/bin/activate
  python3 tools/run_autocoinbot_check.py

O script usa `specialized_agents.homelab_agent.get_homelab_agent()` para executar
comandos remotos. Ele coleta ss/ufw/iptables/systemctl/journal e, se `ufw` estiver
ativo e a porta 9092 não estiver permitida, tenta rodar o comando UFW para
permitir acesso da LAN `192.168.15.0/24` e reiniciar o serviço `autocoinbot-exporter`.

Observação: o agente remoto precisa permitir sudo para os comandos que alteram o
firewall (ou você será solicitado pela senha sudo no terminal remoto).
"""

import json
import sys
import traceback

try:
    from specialized_agents.homelab_agent import get_homelab_agent
except Exception as e:
    print(json.dumps({"error": "Cannot import homelab agent", "exception": str(e)}))
    sys.exit(1)

agent = get_homelab_agent()
cmds = {
    'ss': "ss -tuln | grep -w 9092 || netstat -tuln | grep -w 9092 || true",
    'ufw': 'ufw status verbose || true',
    'iptables': 'iptables -L -n --line-numbers || true',
    'systemctl': 'systemctl status autocoinbot-exporter --no-pager || true',
    'journal': 'journalctl -u autocoinbot-exporter -n 50 --no-pager || true'
}
results = {}

for k, c in cmds.items():
    try:
        out = agent.execute(c, timeout=60)
    except Exception as e:
        out = f"__exception__:{e}\n{traceback.format_exc()}"
    results[k] = out

ufw_out = results.get('ufw') or ''
try:
    if 'Status: active' in ufw_out:
        if '9092' not in ufw_out:
            results['ufw_allow'] = agent.execute(
                'sudo ufw allow proto tcp from 192.168.15.0/24 to any port 9092', timeout=30
            )
            results['restart'] = agent.execute(
                'sudo systemctl restart autocoinbot-exporter && ss -tuln | grep -w 9092 || true',
                timeout=30,
            )
        else:
            results['ufw_allow'] = 'already_allowed'
    else:
        results['ufw_allow'] = 'ufw_inactive_or_unavailable'
except Exception as e:
    results['ufw_allow'] = f'__exception__:{e}\n{traceback.format_exc()}'

print(json.dumps(results, ensure_ascii=False))
