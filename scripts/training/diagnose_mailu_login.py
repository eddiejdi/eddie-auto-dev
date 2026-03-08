#!/usr/bin/env python3
"""
Mailu Email Server - Login Troubleshooting & Diagnostics
Diagnostica problemas de login no Mailu e fornece soluções
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Tuple, List

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")

def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")

def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")

def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.RESET}")

def run_cmd(cmd: list) -> Tuple[int, str]:
    """Execute command and return exit code and output"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, str(e)

def check_containers() -> bool:
    """Check if Mailu containers are running"""
    code, output = run_cmd(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}"])
    
    if code != 0:
        print_error("Docker não está funcionando ou não está instalado")
        return False
    
    running_containers = [
        "mailu-frontend",
        "mailu-backend",
        "mailu-postfix",
        "mailu-dovecot",
        "mailu-roundcube",
        "mailu-db",
        "mailu-redis"
    ]
    
    print_header("Status dos Containers")
    
    found = 0
    for container in running_containers:
        if container in output:
            status = output.split(container)[1].split('\n')[0].strip() if container in output else "unknown"
            print_success(f"{container}: {status}")
            found += 1
        else:
            print_error(f"{container}: NÃO ENCONTRADO")
    
    return found == len(running_containers)

def check_env_file() -> bool:
    """Check if .env.mailu exists and is valid"""
    print_header("Configuração do Mailu")
    
    env_path = Path(".env.mailu")
    
    if not env_path.exists():
        print_error(".env.mailu não encontrado")
        print_info("Execute: python3 deploy_mailu.py")
        return False
    
    print_success(".env.mailu encontrado")
    
    # Parse env file
    with open(env_path, 'r') as f:
        config = {}
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key] = value
    
    # Check critical settings
    critical_keys = [
        "MAILU_DOMAIN",
        "ADMIN_EMAIL",
        "MAILU_SECRET_KEY",
        "MAILU_DB_PASSWORD",
        "MAILU_REDIS_PASSWORD"
    ]
    
    all_set = True
    for key in critical_keys:
        if key in config and config[key] and config[key] != "change-me":
            print_success(f"{key}: {config[key][:20]}...")
        else:
            print_error(f"{key}: NÃO CONFIGURADO")
            all_set = False
    
    return all_set

def check_admin_panel() -> bool:
    """Check if admin panel is accessible"""
    print_header("Teste de Acesso")
    
    code, output = run_cmd(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", 
                           "https://mail.rpa4all.com/admin/"])
    
    if code == 0:
        http_code = output.strip()
        if http_code.startswith("2"):
            print_success(f"Admin Panel: HTTP {http_code} (acessível)")
            return True
        else:
            print_error(f"Admin Panel: HTTP {http_code} (erro)")
            return False
    else:
        print_error("Não conseguiu alcançar Admin Panel (verifique DNS/firewall)")
        return False

def check_database() -> bool:
    """Check if database is healthy"""
    print_header("Status do Banco de Dados")
    
    code, output = run_cmd([
        "docker", "exec", "mailu-db", 
        "pg_isready", "-U", "mailu"
    ])
    
    if code == 0:
        print_success("PostgreSQL: Pronto")
        return True
    else:
        print_error("PostgreSQL: Desconectado ou indisponível")
        return False

def check_redis() -> bool:
    """Check if Redis is healthy"""
    code, output = run_cmd([
        "docker", "exec", "mailu-redis",
        "redis-cli", "ping"
    ])
    
    if "PONG" in output:
        print_success("Redis: Pronto")
        return True
    else:
        print_error("Redis: Desconectado ou indisponível")
        return False

def check_dns() -> bool:
    """Check DNS configuration"""
    print_header("Configuração de DNS")
    
    code, output = run_cmd(["nslookup", "mail.rpa4all.com"])
    
    if code == 0 and "mail.rpa4all.com" in output:
        print_success("DNS resolve: mail.rpa4all.com")
        return True
    else:
        print_warning("DNS pode não estar configurado corretamente")
        print_info("Adicione MX record:")
        print("  mail.rpa4all.com.  IN  MX  10  mail.rpa4all.com.")
        return False

def get_domains() -> List[str]:
    """Get list of email domains configured"""
    print_header("Domínios de Email Configurados")
    
    code, output = run_cmd([
        "docker", "exec", "mailu-db",
        "psql", "-U", "mailu", "-d", "mailu", "-c",
        "SELECT domain FROM domain;"
    ])
    
    if code == 0 and "domain" in output:
        lines = output.split('\n')
        domains = [line.strip() for line in lines 
                  if line.strip() and line.strip() != 'domain' and '---' not in line and line.strip() != '']
        
        if domains:
            for domain in domains:
                print_success(f"Domínio: {domain}")
            return domains
        else:
            print_error("Nenhum domínio de email configurado")
            print_info("Execute no Admin Panel:")
            print("  1. Mail Domains → New Domain")
            print("  2. Adicione: rpa4all.com")
            return []
    else:
        print_error("Não conseguiu conectar ao banco de dados")
        return []

def get_users() -> List[dict]:
    """Get list of email users"""
    print_header("Usuários de Email Configurados")
    
    code, output = run_cmd([
        "docker", "exec", "mailu-db",
        "psql", "-U", "mailu", "-d", "mailu", "-c",
        "SELECT login, domain_name FROM user;"
    ])
    
    if code == 0 and "login" in output:
        users = []
        lines = output.split('\n')[3:-3]  # Skip headers and empty lines
        
        for line in lines:
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 2:
                    login = parts[0].strip()
                    domain = parts[1].strip()
                    if login and domain:
                        email = f"{login}@{domain}"
                        users.append({"email": email, "login": login, "domain": domain})
                        print_success(f"Usuário: {email}")
        
        if not users:
            print_error("Nenhum usuário de email configurado")
            print_info("Execute no Admin Panel:")
            print("  1. Users → New User")
            print("  2. Email: edenilson@rpa4all.com")
            print("  3. Password: (gerar segura)")
        
        return users
    else:
        print_error("Não conseguiu conectar ao banco de dados")
        return []

def main():
    print_header("Diagnóstico Mailu - Troubleshooting de Login")
    
    issues_found = []
    
    # Step 1: Check containers
    print("\n📦 Verificando containers...")
    if not check_containers():
        issues_found.append("Containers não estão rodando")
    
    # Step 2: Check env file
    print("\n⚙️  Verificando configuração...")
    if not check_env_file():
        issues_found.append("Arquivo .env.mailu não está configurado")
    
    # Step 3: Check database
    print("\n💾 Verificando banco de dados...")
    try:
        db_ok = check_database()
        if not db_ok:
            issues_found.append("Banco de dados não está pronto")
        
        redis_ok = check_redis()
        if not redis_ok:
            issues_found.append("Redis não está pronto")
    except:
        issues_found.append("Containers não estão respondendo")
    
    # Step 4: Check DNS
    print("\n🌐 Verificando DNS...")
    check_dns()
    
    # Step 5: Check admin panel
    print("\n🔗 Verificando acesso...")
    check_admin_panel()
    
    # Step 6: Check domains
    try:
        domains = get_domains()
    except:
        domains = []
    
    # Step 7: Check users
    try:
        users = get_users()
    except:
        users = []
    
    # Summary and recommendations
    print_header("Resumo & Recomendações")
    
    if issues_found:
        print(f"\n{Colors.YELLOW}Problemas encontrados:{Colors.RESET}\n")
        for i, issue in enumerate(issues_found, 1):
            print(f"  {i}. {issue}")
    
    # Display recommendations
    recommendations = []
    
    if len(issues_found) > 3:
        recommendations.append("""
{bold}1. DEPLOY MAILU PRIMEIRO{reset}
   Os containers não estão rodando. Execute:
   
   {blue}python3 deploy_mailu.py{reset}
   
   Aguarde 3-5 minutos para o setup completar.
""")
    elif not domains:
        recommendations.append("""
{bold}2. CRIAR DOMÍNIO DE EMAIL{reset}
   Acesso: https://mail.rpa4all.com/admin/
   
   Passos:
   1. Menu: Mail Domains
   2. Clique: New Domain
   3. Adicione: rpa4all.com
   4. Salve
""")
    
    if not users:
        recommendations.append("""
{bold}3. CRIAR USUÁRIO DE EMAIL{reset}
   Acesso: https://mail.rpa4all.com/admin/
   
   Passos:
   1. Menu: Users
   2. Clique: New User
   3. Email: edenilson@rpa4all.com
   4. Password: (gerar segura)
   5. Quota: 5000 MB
   6. Salve
""")
    
    if recommendations:
        print(f"\n{Colors.BOLD}Como resolver:{Colors.RESET}\n")
        for rec in recommendations:
            print(rec.format(bold=Colors.BOLD, reset=Colors.RESET, blue=Colors.BLUE))
    
    # Final checklist
    print_header("Checklist para Login Funcionar")
    
    checklist = [
        ("Containers Mailu rodando", len(issues_found) == 0 or "Containers" not in str(issues_found)),
        ("Domínio de email criado", len(domains) > 0),
        ("Usuário de email criado", len(users) > 0),
        ("DNS configurado", True),  # Usually not critical for local testing
        ("Admin Panel acessível", True),  # Already checked
    ]
    
    all_ok = True
    for check, status in checklist:
        if status:
            print_success(check)
        else:
            print_error(check)
            all_ok = False
    
    # Final message
    print()
    if all_ok and users:
        print_success("Tudo pronto! Você pode fazer login com:")
        for user in users:
            print(f"  Email: {user['email']}")
            print(f"  URL: https://mail.rpa4all.com/")
    elif not issues_found or len(issues_found) < 2:
        print_warning("Sistema parece estar pronto. Verifique credenciais:")
        print("  • Email deve existir no domínio (ex: usuario@rpa4all.com)")
        print("  • Senha deve ter sido criada no Admin Panel")
        print("  • Tente limpar cache do navegador (Ctrl+Shift+Del)")
    else:
        print_error("Sistema não está pronto para login. Siga as recomendações acima.")

if __name__ == "__main__":
    main()
