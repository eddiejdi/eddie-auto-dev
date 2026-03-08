#!/usr/bin/env python3
"""
Mailu Deployment Automation Script
Automates setup, validation, and initial configuration of Mailu email server
"""

import os
import sys
import subprocess
import secrets
import argparse
from pathlib import Path
from typing import Optional, Dict, Tuple
import json
from datetime import datetime

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")

def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")

def run_command(cmd: list, capture: bool = False) -> Tuple[int, str]:
    """Run shell command and return exit code and output"""
    try:
        if capture:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode, result.stdout + result.stderr
        else:
            result = subprocess.run(cmd, timeout=30)
            return result.returncode, ""
    except subprocess.TimeoutExpired:
        return 1, "Command timeout"
    except Exception as e:
        return 1, str(e)

def check_prerequisites() -> bool:
    """Check if Docker and Docker Compose are installed"""
    print_header("Checking Prerequisites")
    
    checks = {
        "Docker": ["docker", "--version"],
        "Docker Compose": ["docker-compose", "--version"],
        "Python 3": ["python3", "--version"],
    }
    
    all_ok = True
    for name, cmd in checks.items():
        code, output = run_command(cmd, capture=True)
        if code == 0:
            print_success(f"{name}:  {output.strip()}")
        else:
            print_error(f"{name}: Not found or not installed")
            all_ok = False
    
    return all_ok

def check_network() -> bool:
    """Check if homelab_monitoring network exists"""
    print_header("Checking Docker Network")
    
    code, output = run_command(["docker", "network", "ls"], capture=True)
    if "homelab_monitoring" in output:
        print_success("Network 'homelab_monitoring' already exists")
        return True
    else:
        print_warning("Network 'homelab_monitoring' not found")
        print_info("Creating network...")
        code, _ = run_command(["docker", "network", "create", "homelab_monitoring"])
        if code == 0:
            print_success("Network created successfully")
            return True
        else:
            print_error("Failed to create network")
            return False

def generate_secrets() -> Dict[str, str]:
    """Generate secure random secrets"""
    return {
        "MAILU_SECRET_KEY": secrets.token_urlsafe(32),
        "MAILU_DB_PASSWORD": secrets.token_urlsafe(32),
        "MAILU_REDIS_PASSWORD": secrets.token_urlsafe(32),
    }

def ask_for_config() -> Dict[str, str]:
    """Interactively ask for configuration values"""
    print_header("Mailu Configuration")
    
    config = {}
    
    # Domain
    domain = input(f"{Colors.BOLD}Email domain (e.g., mail.rpa4all.com): {Colors.RESET}").strip()
    if not domain:
        domain = "mail.rpa4all.com"
    config["MAILU_DOMAIN"] = domain
    
    # Admin email
    admin_email = input(f"{Colors.BOLD}Admin email (e.g., admin@{domain}): {Colors.RESET}").strip()
    if not admin_email:
        admin_email = f"admin@{domain}"
    config["ADMIN_EMAIL"] = admin_email
    
    # TLS flavor
    print(f"\nTLS/SSL Options:")
    print("  1. letsencrypt (recommended, auto-renewal)")
    print("  2. selfsigned (self-signed certificates)")
    print("  3. notls (no SSL, not recommended)")
    tls_choice = input(f"{Colors.BOLD}Choose TLS option (1-3, default=1): {Colors.RESET}").strip()
    tls_map = {"1": "letsencrypt", "2": "selfsigned", "3": "notls"}
    config["MAILU_TLS_FLAVOR"] = tls_map.get(tls_choice, "letsencrypt")
    
    # Ports
    print(f"\nPort Configuration (press Enter to keep defaults):")
    config["MAILU_HTTP_PORT"] = input(f"{Colors.BOLD}HTTP port (default 80): {Colors.RESET}").strip() or "80"
    config["MAILU_HTTPS_PORT"] = input(f"{Colors.BOLD}HTTPS port (default 443): {Colors.RESET}").strip() or "443"
    config["MAILU_SMTP_PORT"] = input(f"{Colors.BOLD}SMTP port (default 25): {Colors.RESET}").strip() or "25"
    config["MAILU_SUBMISSION_PORT"] = input(f"{Colors.BOLD}SMTP Submission port (default 587): {Colors.RESET}").strip() or "587"
    config["MAILU_IMAP_PORT"] = input(f"{Colors.BOLD}IMAP port (default 143): {Colors.RESET}").strip() or "143"
    config["MAILU_IMAPS_PORT"] = input(f"{Colors.BOLD}IMAPS port (default 993): {Colors.RESET}").strip() or "993"
    
    return config

def create_env_file(config: Dict[str, str]):
    """Create .env.mailu from configuration"""
    env_path = Path(".env.mailu")
    
    env_content = f"""# ═══════════════════════════════════════════════════════════════════════════
# MAILU Configuration - Auto-generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# ═══════════════════════════════════════════════════════════════════════════

# Email Server Domain
MAILU_DOMAIN={config['MAILU_DOMAIN']}

# Admin User
ADMIN_EMAIL={config['ADMIN_EMAIL']}
POSTMASTER_EMAIL=postmaster@{config['MAILU_DOMAIN']}

# Secret Keys (Generated automatically)
MAILU_SECRET_KEY={config.get('MAILU_SECRET_KEY', 'generate-me')}
MAILU_DB_PASSWORD={config.get('MAILU_DB_PASSWORD', 'generate-me')}
MAILU_REDIS_PASSWORD={config.get('MAILU_REDIS_PASSWORD', 'generate-me')}

# TLS/SSL Configuration
MAILU_TLS_FLAVOR={config.get('MAILU_TLS_FLAVOR', 'letsencrypt')}

# Port Configuration
MAILU_HTTP_PORT={config.get('MAILU_HTTP_PORT', '80')}
MAILU_HTTPS_PORT={config.get('MAILU_HTTPS_PORT', '443')}
MAILU_SMTP_PORT={config.get('MAILU_SMTP_PORT', '25')}
MAILU_SUBMISSION_PORT={config.get('MAILU_SUBMISSION_PORT', '587')}
MAILU_IMAP_PORT={config.get('MAILU_IMAP_PORT', '143')}
MAILU_IMAPS_PORT={config.get('MAILU_IMAPS_PORT', '993')}
MAILU_POP3_PORT={config.get('MAILU_POP3_PORT', '110')}
MAILU_POP3S_PORT={config.get('MAILU_POP3S_PORT', '995')}

# Prometheus Exporters
POSTFIX_EXPORTER_PORT=9307
DOVECOT_EXPORTER_PORT=9308

# Mail Settings
MAX_EMAIL_SIZE=25
AUTH_RATELIMIT=100/minute

# Database Settings
DATABASE_URL=postgresql://mailu:${{MAILU_DB_PASSWORD}}@mailu-db/mailu
REDIS_URL=redis://:${{MAILU_REDIS_PASSWORD}}@mailu-redis

# Optional: OAuth2 / OIDC with Authentik
# ENABLE_OAUTH2=true
# OAUTH2_PROVIDER_URL=https://auth.rpa4all.com
# OAUTH2_CLIENT_ID=mailu-client
# OAUTH2_CLIENT_SECRET=your_authentik_oauth2_secret
"""
    
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print_success(f"Configuration saved to {env_path}")

def deploy_mailu() -> bool:
    """Deploy Mailu with Docker Compose"""
    print_header("Deploying Mailu")
    
    compose_file = "docker-compose.mailu.yml"
    
    if not Path(compose_file).exists():
        print_error(f"{compose_file} not found")
        return False
    
    print_info("Starting Mailu containers... (this may take a few minutes)")
    code, output = run_command(["docker-compose", "-f", compose_file, "up", "-d"])
    
    if code == 0:
        print_success("Mailu containers started")
        return True
    else:
        print_error(f"Failed to start containers:\n{output}")
        return False

def wait_for_services(timeout: int = 120) -> bool:
    """Wait for services to be healthy"""
    print_header("Waiting for Services to Start")
    
    services = [
        ("mailu-db", "PostgreSQL Database"),
        ("mailu-redis", "Redis Cache"),
        ("mailu-backend", "Mailu Backend"),
        ("mailu-frontend", "Mailu Frontend"),
        ("mailu-postfix", "Postfix SMTP"),
        ("mailu-dovecot", "Dovecot IMAP/POP3"),
        ("mailu-roundcube", "Roundcube Webmail"),
    ]
    
    elapsed = 0
    while elapsed < timeout:
        healthy = 0
        for service_name, display_name in services:
            code, output = run_command(
                ["docker", "inspect", "--format", "{{.State.Health.Status}}", service_name],
                capture=True
            )
            if "healthy" in output.lower():
                print_success(f"{display_name} is healthy")
                healthy += 1
            elif "none" in output.lower():  # No healthcheck configured
                healthy += 1
        
        if healthy == len(services):
            print_success("All services are ready!")
            return True
        
        elapsed += 5
        if elapsed < timeout:
            print_info(f"Waiting... ({elapsed}s elapsed, {timeout - elapsed}s remaining)")
            import time
            time.sleep(5)
    
    print_warning("Timeout waiting for services. Some may still be starting.")
    return False

def display_status():
    """Display current Mailu status"""
    print_header("Mailu Status")
    
    code, output = run_command(["docker-compose", "-f", "docker-compose.mailu.yml", "ps"], capture=True)
    print(output)

def display_next_steps(config: Dict[str, str]):
    """Display next steps for user"""
    print_header("Next Steps")
    
    domain = config.get('MAILU_DOMAIN', 'mail.rpa4all.com')
    admin_email = config.get('ADMIN_EMAIL', f'admin@{domain}')
    
    steps = f"""
{Colors.BOLD}1. Access Mailu Admin Panel:{Colors.RESET}
   URL: https://{domain}/admin/
   Email: {admin_email}
   Password: Check docker logs or Authentik if SSO enabled

{Colors.BOLD}2. Create First Email Domain:{Colors.RESET}
   Admin Panel → Mail Domains → Add Domain
   Domain: (your domain, e.g., rpa4all.com)

{Colors.BOLD}3. Create Email Users:{Colors.RESET}
   Admin Panel → Users → Add User
   Create test accounts for team members

{Colors.BOLD}4. Access Webmail (Roundcube):{Colors.RESET}
   URL: https://{domain}/
   Login with created email accounts

{Colors.BOLD}5. DNS Configuration (Important!):{Colors.RESET}
   Add MX record pointing to your mail server:
   
   {domain}.  IN  MX  10  {domain}.
   {domain}.  IN  A   <your-ip>

{Colors.BOLD}6. Configure SPF/DKIM/DMARC:{Colors.RESET}
   Admin Panel → Relayed Domains
   Copy DKIM public key to DNS TXT records
   
{Colors.BOLD}7. Monitor with Grafana:{Colors.RESET}
   URL: http://192.168.15.2:3002/
   Dashboard: "Mailu Email Server Monitoring"
   
   Note: Ensure Prometheus is scraping postfix-exporter:9307

{Colors.BOLD}8. (Optional) Integrate with Authentik SSO:{Colors.RESET}
   Edit .env.mailu and uncomment OAuth2 settings
   Create OAuth2 application in Authentik
   Restart mailu-backend: docker-compose -f docker-compose.mailu.yml restart mailu-backend

{Colors.BOLD}9. Backup Configuration:{Colors.RESET}
   mkdir -p /mnt/backups/mailu
   Setup cron job for automated backups
   See MAILU_DEPLOYMENT.md for backup script

{Colors.BOLD}10. Check Logs:{Colors.RESET}
    docker-compose -f docker-compose.mailu.yml logs -f
    docker logs mailu-postfix
    docker logs mailu-dovecot
    docker logs mailu-roundcube
"""
    print(steps)

def main():
    """Main deployment flow"""
    parser = argparse.ArgumentParser(description="Mailu Email Server Deployment")
    parser.add_argument("--non-interactive", action="store_true", help="Skip interactive prompts")
    parser.add_argument("--domain", type=str, help="Mail server domain")
    parser.add_argument("--admin-email", type=str, help="Admin email address")
    args = parser.parse_args()
    
    print_header("Mailu Email Server - Automated Deployment")
    print_info("This script will set up a complete self-hosted email server with webmail")
    
    # Prerequisites
    if not check_prerequisites():
        print_error("Missing required tools. Please install Docker and Docker Compose.")
        sys.exit(1)
    
    # Network
    if not check_network():
        print_error("Failed to setup Docker network")
        sys.exit(1)
    
    # Configuration
    if args.non_interactive:
        config = {
            "MAILU_DOMAIN": args.domain or "mail.rpa4all.com",
            "ADMIN_EMAIL": args.admin_email or f"admin@{args.domain or 'mail.rpa4all.com'}",
            "MAILU_TLS_FLAVOR": "letsencrypt",
        }
    else:
        config = ask_for_config()
    
    # Generate secrets
    secrets = generate_secrets()
    config.update(secrets)
    
    # Create env file
    create_env_file(config)
    
    # Deploy
    if not deploy_mailu():
        print_error("Deployment failed")
        sys.exit(1)
    
    # Wait for services
    wait_for_services()
    
    # Display status
    display_status()
    
    # Display next steps
    display_next_steps(config)
    
    print_success("Deployment complete! Check logs and follow next steps above.")

if __name__ == "__main__":
    main()
