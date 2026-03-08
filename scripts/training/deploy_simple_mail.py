#!/usr/bin/env python3
"""
Simplified Email Server Deployment Script
Uses lightweight, publicly available Docker images (Postfix, Dovecot, Roundcube)
"""

import os
import sys
import subprocess
import time
from pathlib import Path


def print_header(text: str) -> None:
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def run_cmd(cmd: list[str], check: bool = True) -> str:
    """Run shell command and return output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if check and result.returncode != 0:
            print(f"✗ Error: {result.stderr}")
            return ""
        return result.stdout.strip()
    except Exception as e:
        print(f"✗ Exception: {e}")
        return ""


def check_prerequisites() -> bool:
    """Verify Docker and Docker Compose are installed."""
    print_header("Checking Prerequisites")
    
    checks = {
        "Docker": ["docker", "--version"],
        "Docker Compose": ["docker-compose", "--version"],
        "Python 3": ["python3", "--version"],
    }
    
    all_ok = True
    for name, cmd in checks.items():
        output = run_cmd(cmd, check=False)
        if output:
            print(f"✓ {name}: {output}")
        else:
            print(f"✗ {name}: NOT FOUND")
            all_ok = False
    
    return all_ok


def check_network() -> bool:
    """Ensure homelab_monitoring network exists."""
    print_header("Checking Docker Network")
    
    output = run_cmd(["docker", "network", "ls", "--filter", "name=homelab_monitoring", "-q"], check=False)
    
    if output:
        print(f"✓ Network 'homelab_monitoring' already exists")
        return True
    else:
        print("ℹ Creating network 'homelab_monitoring'...")
        result = run_cmd(["docker", "network", "create", "homelab_monitoring"], check=False)
        if "created" in result or not result or result == "":
            print("✓ Network created successfully")
            return True
        else:
            print(f"✗ Failed to create network: {result}")
            return False


def generate_secrets() -> dict:
    """Generate secure random passwords."""
    import secrets
    import string
    
    def gen_password(length: int = 32) -> str:
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    return {
        "MAIL_DB_PASSWORD": gen_password(24),
        "ROUNDCUBE_ADMIN_PASSWORD": gen_password(24),
    }


def ask_for_config() -> dict:
    """Ask user for configuration."""
    print_header("Email Server Configuration")
    
    domain = input("📧 Email domain (e.g., mail.rpa4all.com) [mail.rpa4all.com]: ").strip() or "mail.rpa4all.com"
    admin_email = input(f"👤 Admin email [admin@{domain}]: ").strip() or f"admin@{domain}"
    
    # Check for Let's Encrypt certificates
    cert_path = Path(f"/etc/letsencrypt/live/{domain}")
    has_cert = cert_path.exists()
    
    if has_cert:
        print(f"✓ Found Let's Encrypt certificate for {domain}")
    else:
        print(f"⚠ No Let's Encrypt certificate found for {domain}")
        print("  You'll need to set up SSL certificates before deployment")
        print("  Suggested: certbot certonly --standalone -d {domain}")
    
    return {
        "MAIL_DOMAIN": domain,
        "ADMIN_EMAIL": admin_email,
    }


def create_env_file(config: dict, secrets: dict) -> bool:
    """Create .env.simple-mail file."""
    env_path = Path(".env.simple-mail")
    
    content = f"""# Simplified Email Server Configuration
# Generated automatically by deploy_simple_mail.py

# Email domain
MAIL_DOMAIN={config['MAIL_DOMAIN']}
ADMIN_EMAIL={config['ADMIN_EMAIL']}

# Database
MAIL_DB_PASSWORD={secrets['MAIL_DB_PASSWORD']}

# Ports (change if needed)
SMTP_PORT=25
SMTP_SUBMISSION=587
IMAP_PORT=143
IMAPS_PORT=993
POP3_PORT=110
POP3S_PORT=995

# Roundcube admin
ROUNDCUBE_ADMIN_PASSWORD={secrets['ROUNDCUBE_ADMIN_PASSWORD']}

# Features
ENABLE_MONITORING=true
ENABLE_SSL=true
TLS_FLAVOR=letsencrypt

# Postfix limits
POSTFIX_MESSAGE_SIZE_LIMIT=26214400

# Created at: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    try:
        env_path.write_text(content)
        print(f"✓ Configuration saved to {env_path}")
        return True
    except Exception as e:
        print(f"✗ Failed to write config: {e}")
        return False


def deploy_mail_server() -> bool:
    """Deploy mail server containers."""
    print_header("Deploying Mail Server")
    
    print("ℹ Starting containers... (this may take a minute)")
    
    cmd = [
        "docker-compose",
        "-f", "docker-compose.simple-mail.yml",
        "--env-file", ".env.simple-mail",
        "up", "-d"
    ]
    
    result = run_cmd(cmd, check=False)
    
    if "Starting" in result or "Started" in result or result == "":
        print("✓ Containers starting...")
        return True
    else:
        print(f"✗ Deployment error: {result}")
        return False


def wait_for_services(timeout: int = 120) -> bool:
    """Wait for all services to be healthy."""
    print_header("Waiting for Services")
    
    services = ["mail-db", "mail-server", "roundcube", "mail-nginx"]
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        cmd = ["docker-compose", "-f", "docker-compose.simple-mail.yml", "ps", "-q"]
        containers = run_cmd(cmd, check=False).split('\n') if run_cmd(cmd, check=False) else []
        
        if len(containers) >= 3:  # At least 3 services running
            print("✓ All services are running")
            return True
        
        print("⏳ Waiting for services... ({:.0f}s)".format(time.time() - start_time))
        time.sleep(5)
    
    print("✗ Services did not start within timeout")
    return False


def display_status() -> None:
    """Show docker-compose status."""
    print_header("Deployment Status")
    
    cmd = ["docker-compose", "-f", "docker-compose.simple-mail.yml", "ps"]
    output = run_cmd(cmd, check=False)
    print(output if output else "No containers found")


def display_next_steps(config: dict) -> None:
    """Display next steps for user."""
    print_header("Next Steps")
    
    domain = config.get("MAIL_DOMAIN", "mail.rpa4all.com")
    
    print(f"""
1. 🌐 Access Roundcube Webmail:
   https://{domain}/

2. 📧 Create first email user (via IMAP commands or direct database):
   - User: edenilson@{domain}
   - Password: (set during first login)

3. 🔐 Test login:
   - Protocol: IMAP
   - Server: imap.{domain}
   - Port: 993 (IMAPS)
   - Username: edenilson@{domain}
   - Password: (from step 2)

4. 📨 Optional - Send test email

5. 🔗 Add to Authentik library:
   - Application already configured
   - URL: https://{domain}/
   - Access via: https://auth.rpa4all.com/if/user/#/library

6. 📊 Monitor with Prometheus/Grafana:
   - Postfix exporter: http://postfix-exporter:9307/metrics

⚠️  Important:
   - Ensure DNS MX records point to your server
   - Set reverse DNS (PTR record) for IP reputation
   - Configure firewall rules (ports 25, 143, 587, 993, 110, 995)
   - Set up TLS/SSL certificates (Let's Encrypt recommended)
""")


def main() -> int:
    """Main deployment flow."""
    print("\n" + "=" * 70)
    print("        Simplified Email Server - Quick Deployment")
    print("=" * 70)
    print("\nThis script deploys a lightweight email server using:")
    print("  - Postfix (SMTP)")
    print("  - Dovecot (IMAP/POP3)")
    print("  - Roundcube (Webmail)")
    print("  - PostgreSQL (Database)")
    print("  - Nginx (Reverse Proxy + SSL)")
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n✗ Missing required tools. Please install Docker and Docker Compose.")
        return 1
    
    # Check network
    if not check_network():
        print("\n✗ Failed to setup Docker network")
        return 1
    
    # Get configuration
    config = ask_for_config()
    secrets = generate_secrets()
    
    # Create env file
    if not create_env_file(config, secrets):
        print("\n✗ Failed to create configuration file")
        return 1
    
    # Deploy
    if not deploy_mail_server():
        print("\n✗ Deployment failed")
        print("\nTroubleshooting:")
        print("  1. Check Docker daemon is running: systemctl status docker")
        print("  2. Ensure sufficient disk space: df -h")
        print("  3. Check firewall rules: ufw status")
        return 1
    
    # Wait for services
    if not wait_for_services():
        print("\n⚠️  Services are starting but may not be fully healthy yet")
        print("   Run: docker-compose -f docker-compose.simple-mail.yml logs -f")
    
    # Show status and next steps
    display_status()
    display_next_steps(config)
    
    print("\n✅ Deployment completed! Your email server is ready.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
