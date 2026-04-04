#!/usr/bin/env python3
"""
Configura WPAD (Web Proxy Auto-Discovery) no homelab.

Ações:
  1. Cria arquivo wpad.dat (PAC - Proxy Auto-Config) em /opt/wpad/
  2. Configura Nginx para servir o PAC file em /:80/wpad.dat e /proxy.pac
  3. Adiciona registro DNS local no Pi-hole: wpad → 192.168.15.2
  4. Valida que WPAD está acessível

WPAD funciona assim:
  - Dispositivos fazem GET http://wpad/wpad.dat
  - O PAC file diz: use PROXY 192.168.15.2:3128 para todas as URLs
  - Isso acontece automaticamente no Windows, Android, iOS, macOS

Uso:
  sudo python3 scripts/setup_wpad.py          # configura tudo
  sudo python3 scripts/setup_wpad.py --check  # apenas valida
"""

import argparse
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

HOMELAB_IP = "192.168.15.2"
SQUID_PORT = 3128
WPAD_DIR = Path("/opt/wpad")
NGINX_CONF = Path("/etc/nginx/sites-available/wpad")
NGINX_ENABLED = Path("/etc/nginx/sites-enabled/wpad")
PIHOLE_CUSTOM_DNS = Path("/home/homelab/pihole/etc-pihole/custom.list")

PAC_CONTENT = f"""\
// Proxy Auto-Config (PAC) para rede homelab
// Gerado automaticamente por scripts/setup_wpad.py
// Pi-hole: {HOMELAB_IP}:53
// Proxy: {HOMELAB_IP}:{SQUID_PORT}
function FindProxyForURL(url, host) {{
    // Acesso direto à rede local (sem proxy)
    if (isInNet(host, "192.168.0.0", "255.255.0.0"))   return "DIRECT";
    if (isInNet(host, "10.0.0.0",   "255.0.0.0"))      return "DIRECT";
    if (isInNet(host, "172.16.0.0", "255.240.0.0"))    return "DIRECT";
    if (isInNet(host, "127.0.0.0",  "255.0.0.0"))      return "DIRECT";

    // Acesso direto ao homelab
    if (host == "{HOMELAB_IP}")                          return "DIRECT";
    if (host == "homelab")                              return "DIRECT";

    // Todo o resto via Squid proxy
    return "PROXY {HOMELAB_IP}:{SQUID_PORT}; DIRECT";
}}
"""

NGINX_WPAD_CONF = f"""\
# WPAD (Web Proxy Auto-Discovery) — homelab
server {{
    listen 80;
    server_name wpad wpad.local wpad.lan;

    location / {{
        root {WPAD_DIR};
        default_type application/x-ns-proxy-autoconfig;
        add_header Content-Type "application/x-ns-proxy-autoconfig";
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }}

    # Servir como wpad.dat (padrão WPAD)
    location = /wpad.dat {{
        root {WPAD_DIR};
        default_type application/x-ns-proxy-autoconfig;
    }}

    # Alias proxy.pac
    location = /proxy.pac {{
        alias {WPAD_DIR}/wpad.dat;
        default_type application/x-ns-proxy-autoconfig;
    }}
}}
"""


def _check_root() -> None:
    """Verifica se está rodando como root (necessário para configurar nginx/pihole)."""
    if os.geteuid() != 0:
        log.error("Execute como root: sudo python3 %s", __file__)
        sys.exit(1)


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Executa comando e loga resultado."""
    log.debug("$ %s", " ".join(cmd))
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        log.error("Falha: %s\nstderr: %s", " ".join(cmd), result.stderr[:200])
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result


def setup_wpad_dir() -> None:
    """Cria diretório e arquivo PAC."""
    WPAD_DIR.mkdir(parents=True, exist_ok=True)
    pac_file = WPAD_DIR / "wpad.dat"
    pac_file.write_text(PAC_CONTENT, encoding="utf-8")
    pac_file.chmod(0o644)
    log.info("PAC file criado: %s", pac_file)
    log.info("Conteúdo:\n%s", PAC_CONTENT)


def setup_nginx() -> None:
    """Configura Nginx para servir WPAD."""
    NGINX_CONF.write_text(NGINX_WPAD_CONF, encoding="utf-8")
    log.info("Nginx conf criada: %s", NGINX_CONF)

    # Habilitar site
    if not NGINX_ENABLED.exists():
        NGINX_ENABLED.symlink_to(NGINX_CONF)
        log.info("Site habilitado: %s", NGINX_ENABLED)

    # Testar e recarregar nginx
    _run(["nginx", "-t"])
    _run(["systemctl", "reload", "nginx"])
    log.info("Nginx recarregado ✓")


def setup_pihole_dns() -> None:
    """Adiciona entrada DNS no Pi-hole: wpad → 192.168.15.2."""
    entry = f"{HOMELAB_IP} wpad\n{HOMELAB_IP} wpad.local\n"

    current = ""
    if PIHOLE_CUSTOM_DNS.exists():
        current = PIHOLE_CUSTOM_DNS.read_text()

    if HOMELAB_IP in current and "wpad" in current:
        log.info("DNS wpad já configurado no Pi-hole")
        return

    # Remover entradas antigas de wpad
    lines = [l for l in current.splitlines() if "wpad" not in l.lower()]
    lines.append(f"{HOMELAB_IP} wpad")
    lines.append(f"{HOMELAB_IP} wpad.local")
    lines.append(f"{HOMELAB_IP} wpad.lan")

    PIHOLE_CUSTOM_DNS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("DNS wpad adicionado: %s → %s", "wpad", HOMELAB_IP)

    # Reiniciar FTL para aplicar DNS
    try:
        result = _run(["docker", "exec", "pihole", "pihole", "restartdns"], check=False)
        if result.returncode == 0:
            log.info("Pi-hole DNS reiniciado ✓")
        else:
            # Alternativa: recarregar via API
            log.warning("pihole restartdns falhou, tentando SIGHUP FTL")
            _run(["docker", "exec", "pihole", "killall", "-HUP", "pihole-FTL"], check=False)
            log.info("FTL recarregado via SIGHUP ✓")
    except Exception as exc:
        log.warning("Não foi possível reiniciar Pi-hole FTL: %s", exc)


def validate_wpad(host: str = HOMELAB_IP) -> bool:
    """Valida que WPAD está acessível via HTTP."""
    urls = [
        f"http://{host}/wpad.dat",
        f"http://{host}/proxy.pac",
        f"http://wpad/wpad.dat",
    ]
    all_ok = True
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                content = resp.read().decode(errors="replace")
                if "FindProxyForURL" in content:
                    log.info("WPAD OK: %s ✓", url)
                else:
                    log.warning("WPAD acessível mas PAC inválido: %s", url)
                    all_ok = False
        except Exception as exc:
            log.warning("WPAD inacessível: %s → %s", url, exc)
            if "wpad.dat" in url and host == HOMELAB_IP:
                all_ok = False
    return all_ok


def main() -> int:
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Configura WPAD/PAC para distribuição automática de proxy"
    )
    parser.add_argument("--check", action="store_true", help="Apenas valida WPAD, sem configurar")
    args = parser.parse_args()

    if args.check:
        ok = validate_wpad()
        return 0 if ok else 1

    _check_root()

    log.info("=== Configurando WPAD no homelab (%s) ===", HOMELAB_IP)

    # 1. Criar PAC file
    setup_wpad_dir()

    # 2. Configurar Nginx
    try:
        setup_nginx()
    except subprocess.CalledProcessError as exc:
        log.error("Falha ao configurar Nginx: %s", exc)
        return 1

    # 3. Configurar DNS no Pi-hole
    setup_pihole_dns()

    # 4. Validar
    ok = validate_wpad()
    if ok:
        log.info("=== WPAD configurado com sucesso! ===")
        log.info("Dispositivos na rede devem detectar o proxy automaticamente.")
        log.info("URL do PAC: http://%s/wpad.dat", HOMELAB_IP)
        log.info("Proxy: %s:%d", HOMELAB_IP, SQUID_PORT)
    else:
        log.warning("WPAD configurado mas validação incompleta — verifique Nginx")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
