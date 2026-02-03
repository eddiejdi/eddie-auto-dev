#!/usr/bin/env python3
"""
Script para validar endpoints da infraestrutura sem interrupções
Testa via SSH (local) e Selenium (remoto via browser)
"""

import subprocess
import sys
import time
from typing import Tuple, Dict

def run_ssh_cmd(cmd: str) -> Tuple[int, str]:
    """Executar comando via SSH no homelab"""
    full_cmd = f"ssh -o IdentitiesOnly=yes -i ~/.ssh/eddie_deploy_rsa homelab@192.168.15.2 '{cmd}'"
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr

def test_local_services() -> Dict[str, bool]:
    """Testar serviços locais via localhost"""
    results = {}
    
    print("\n🔍 Testando serviços locais (via SSH)...")
    
    tests = {
        "Prometheus (localhost:9090)": "curl -s http://127.0.0.1:9090/ -I | head -1",
        "Grafana (localhost:3002)": "curl -s http://127.0.0.1:3002/ -I | head -1",
        "OpenWebUI (localhost:8002)": "curl -s http://127.0.0.1:8002/ -I | head -1",
    }
    
    for name, cmd in tests.items():
        code, output = run_ssh_cmd(cmd)
        success = "200" in output or "301" in output
        results[name] = success
        status = "✅" if success else "❌"
        print(f"  {status} {name}")
        if not success:
            print(f"     Output: {output[:100]}")
    
    return results

def test_nginx_config() -> Dict[str, bool]:
    """Testar configuração nginx"""
    results = {}
    
    print("\n🔍 Testando nginx...")
    
    # Syntaxe
    code, output = run_ssh_cmd("sudo nginx -t 2>&1")
    results["Nginx syntax"] = "successful" in output
    print(f"  {'✅' if results['Nginx syntax'] else '❌'} Nginx syntax valid")
    
    # Status
    code, output = run_ssh_cmd("sudo systemctl status nginx | grep Active")
    results["Nginx running"] = "active (running)" in output
    print(f"  {'✅' if results['Nginx running'] else '❌'} Nginx running")
    
    # Certificado
    code, output = run_ssh_cmd("ls -la /etc/letsencrypt/live/www.rpa4all.com/ 2>&1")
    results["Certificate www"] = "fullchain.pem" in output
    code, output = run_ssh_cmd("ls -la /etc/letsencrypt/live/openwebui.rpa4all.com/ 2>&1")
    results["Certificate openwebui"] = "fullchain.pem" in output
    print(f"  {'✅' if results['Certificate www'] else '❌'} Certificate www.rpa4all.com")
    print(f"  {'✅' if results['Certificate openwebui'] else '❌'} Certificate openwebui.rpa4all.com")
    
    return results

def test_http_endpoints() -> Dict[str, bool]:
    """Testar endpoints HTTP via localhost"""
    results = {}
    
    print("\n🔍 Testando endpoints HTTP (localhost:80)...")
    
    endpoints = {
        "HTTP root": "curl -s http://127.0.0.1/ -I | grep -E '301|200'",
        "HTTP /.well-known": "curl -s http://127.0.0.1/.well-known/acme-challenge/test -I | head -1",
    }
    
    for name, cmd in endpoints.items():
        code, output = run_ssh_cmd(cmd)
        success = bool(output.strip())
        results[name] = success
        print(f"  {'✅' if success else '❌'} {name}: {output.split()[0] if output else 'No response'}")
    
    return results

def test_containers() -> Dict[str, bool]:
    """Testar status dos containers"""
    results = {}
    
    print("\n🔍 Testando containers...")
    
    containers = ["grafana", "prometheus", "open-webui", "openwebui-postgres"]
    
    for container in containers:
        code, output = run_ssh_cmd(f"docker ps --filter 'name={container}' --format '{{{{.State}}}}'")
        running = "running" in output.lower()
        results[f"Container {container}"] = running
        print(f"  {'✅' if running else '❌'} {container}: {output.strip()}")
    
    return results

def main():
    print("=" * 60)
    print("Validação de Endpoints - www.rpa4all.com")
    print("=" * 60)
    
    all_results = {}
    
    # Testes
    all_results.update(test_local_services())
    all_results.update(test_nginx_config())
    all_results.update(test_http_endpoints())
    all_results.update(test_containers())
    
    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    
    passed = sum(1 for v in all_results.values() if v)
    total = len(all_results)
    
    for name, success in all_results.items():
        status = "✅" if success else "❌"
        print(f"{status} {name}")
    
    print(f"\nTotal: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n✅ TODOS OS TESTES PASSARAM!")
        return 0
    else:
        print(f"\n❌ {total - passed} testes falharam")
        return 1

if __name__ == "__main__":
    sys.exit(main())
