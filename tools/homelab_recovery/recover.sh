#!/usr/bin/env bash
set -euo pipefail
#
# Homelab Recovery Script — restaura acesso ao servidor sem depender de SSH
#
# Uso:
#   ./recover.sh --diagnose        Diagnóstico completo
#   ./recover.sh --auto            Tenta todos os métodos automaticamente
#   ./recover.sh --wol             Envia Wake-on-LAN
#   ./recover.sh --api "cmd"       Executa comando via Agents API (tunnel)
#   ./recover.sh --webui "cmd"     Executa comando via Open WebUI code runner
#   ./recover.sh --telegram "cmd"  Envia comando via Telegram bot
#   ./recover.sh --wait            Monitora até SSH voltar
#   ./recover.sh --safeguard       Instala cron de auto-restore SSH (via API)
#   ./recover.sh --fix-ssh         Tenta restaurar SSH via todos os canais
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.env" 2>/dev/null || true

# Defaults (fallbacks se config.env não existir)
: "${HOMELAB_HOST:=192.168.15.2}"
: "${HOMELAB_USER:=homelab}"
: "${HOMELAB_MAC:=d0:94:66:bb:c4:f6}"
: "${HOMELAB_SSH_PORT:=22}"
: "${HOMELAB_API_PORT:=8503}"
: "${HOMELAB_WEBUI_PORT:=3000}"
: "${TUNNEL_API_URL:=https://api.rpa4all.com}"
: "${TUNNEL_WEBUI_URL:=https://openwebui.rpa4all.com}"
: "${WOL_WAIT_SECONDS:=60}"
: "${SSH_CONNECT_TIMEOUT:=10}"
: "${PING_TIMEOUT:=3}"
: "${MAX_RETRIES:=10}"
: "${RETRY_INTERVAL:=15}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; }

# ─── Checks ────────────────────────────────────────────────

check_ping() {
    ping -c 1 -W "$PING_TIMEOUT" "$HOMELAB_HOST" &>/dev/null
}

check_ssh() {
    ssh -o ConnectTimeout="$SSH_CONNECT_TIMEOUT" \
        -o BatchMode=yes \
        -o StrictHostKeyChecking=no \
        "${HOMELAB_USER}@${HOMELAB_HOST}" -p "$HOMELAB_SSH_PORT" \
        'echo SSH_OK' 2>/dev/null | grep -q SSH_OK
}

check_ssh_port() {
    timeout "$SSH_CONNECT_TIMEOUT" bash -c "echo >/dev/tcp/${HOMELAB_HOST}/${HOMELAB_SSH_PORT}" 2>/dev/null
}

check_api_direct() {
    curl -sS --max-time 5 "http://${HOMELAB_HOST}:${HOMELAB_API_PORT}/health" &>/dev/null
}

check_api_tunnel() {
    local resp
    resp=$(curl -sS --max-time 10 "${TUNNEL_API_URL}/agents-api/health" 2>/dev/null) || return 1
    echo "$resp" | grep -qiE 'ok|healthy|status' 2>/dev/null
}

check_webui_tunnel() {
    local code
    code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "$TUNNEL_WEBUI_URL" 2>/dev/null) || return 1
    [[ "$code" =~ ^(200|301|302)$ ]]
}

check_webui_direct() {
    curl -sS --max-time 5 "http://${HOMELAB_HOST}:${HOMELAB_WEBUI_PORT}" &>/dev/null
}

# ─── Actions ───────────────────────────────────────────────

do_wol() {
    log "Enviando Wake-on-LAN para MAC $HOMELAB_MAC..."
    if command -v wakeonlan &>/dev/null; then
        wakeonlan "$HOMELAB_MAC"
    elif command -v etherwake &>/dev/null; then
        sudo etherwake "$HOMELAB_MAC"
    else
        # Fallback: enviar magic packet via Python
        python3 -c "
import socket, struct
mac = '$HOMELAB_MAC'.replace(':','').replace('-','')
data = b'\\xff'*6 + bytes.fromhex(mac)*16
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
s.sendto(data, ('255.255.255.255', 9))
s.close()
print('Magic packet sent via Python')
"
    fi
    ok "Magic packet enviado"
    log "Aguardando ${WOL_WAIT_SECONDS}s para boot..."
    sleep "$WOL_WAIT_SECONDS"
}

exec_via_api() {
    local cmd="$1"
    log "Executando via Agents API tunnel: $cmd"
    local resp
    resp=$(curl -sS --max-time 30 \
        -X POST "${TUNNEL_API_URL}/agents-api/execute" \
        -H 'Content-Type: application/json' \
        -d "{\"command\": \"$cmd\", \"language\": \"bash\"}" 2>&1)
    if [ $? -eq 0 ]; then
        ok "Resposta da API:"
        echo "$resp"
        return 0
    fi
    # Tentar endpoint alternativo (code-runner)
    resp=$(curl -sS --max-time 30 \
        -X POST "${TUNNEL_API_URL}/code-runner/execute" \
        -H 'Content-Type: application/json' \
        -d "{\"code\": \"$cmd\", \"language\": \"bash\"}" 2>&1)
    if [ $? -eq 0 ]; then
        ok "Resposta do Code Runner:"
        echo "$resp"
        return 0
    fi
    fail "Falha ao executar via API"
    return 1
}

exec_via_telegram() {
    local cmd="$1"
    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
        # Tentar buscar do Bitwarden
        if command -v bw &>/dev/null; then
            log "Buscando credenciais Telegram do Bitwarden..."
            local item
            item=$(bw list items --search "Telegram" 2>/dev/null | python3 -c "
import sys, json
items = json.load(sys.stdin)
for i in items:
    if 'telegram' in i.get('name','').lower():
        print(json.dumps(i))
        break
" 2>/dev/null) || true
            if [ -n "$item" ]; then
                TELEGRAM_BOT_TOKEN=$(echo "$item" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('login',{}).get('password',''))" 2>/dev/null)
                TELEGRAM_CHAT_ID=$(echo "$item" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for f in d.get('fields',[]):
    if 'chat' in f.get('name','').lower():
        print(f.get('value',''))
        break
" 2>/dev/null)
            fi
        fi
    fi

    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
        fail "Telegram credentials não disponíveis"
        return 1
    fi

    log "Enviando comando via Telegram: $cmd"
    curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=/exec $cmd" \
        --max-time 10 &>/dev/null
    ok "Comando enviado ao Telegram bot"
}

# ─── Diagnose ─────────────────────────────────────────────

do_diagnose() {
    echo "═══════════════════════════════════════════"
    echo "  Homelab Recovery - Diagnóstico Completo"
    echo "  Host: $HOMELAB_HOST  MAC: $HOMELAB_MAC"
    echo "═══════════════════════════════════════════"
    echo ""

    echo -n "  Ping .................. "
    if check_ping; then ok "UP"; else fail "DOWN"; fi

    echo -n "  SSH porta $HOMELAB_SSH_PORT .......... "
    if check_ssh_port; then ok "OPEN"; else fail "CLOSED/FILTERED"; fi

    echo -n "  SSH login ............. "
    if check_ssh; then ok "OK"; else fail "FALHOU"; fi

    echo -n "  API direta :$HOMELAB_API_PORT ...... "
    if check_api_direct; then ok "OK"; else fail "DOWN"; fi

    echo -n "  API tunnel ............ "
    if check_api_tunnel; then ok "OK"; else fail "DOWN"; fi

    echo -n "  WebUI direta :$HOMELAB_WEBUI_PORT ... "
    if check_webui_direct; then ok "OK"; else fail "DOWN"; fi

    echo -n "  WebUI tunnel .......... "
    if check_webui_tunnel; then ok "OK"; else fail "DOWN"; fi

    echo -n "  ARP entry ............. "
    arp -n 2>/dev/null | grep -q "$HOMELAB_HOST" && ok "PRESENTE" || warn "AUSENTE"

    echo ""
    echo "═══════════════════════════════════════════"

    # Sugestão baseada no diagnóstico
    if check_ping; then
        if check_ssh_port; then
            if ! check_ssh; then
                warn "SSH porta aberta mas login falha → possível problema de autenticação/config"
                echo "  Tente: ./recover.sh --fix-ssh"
            fi
        else
            warn "Server UP mas SSH porta fechada → sshd pode ter crashado"
            if check_api_tunnel || check_api_direct; then
                echo "  API disponível! Tente: ./recover.sh --api 'sudo systemctl restart sshd'"
            else
                echo "  Nenhum canal remoto disponível. Acesso físico necessário."
                echo "  Ou tente: ./recover.sh --telegram 'sudo systemctl restart sshd'"
            fi
        fi
    else
        warn "Server completamente offline"
        echo "  Tente: ./recover.sh --wol"
        echo "  Se WoL não funcionar: acesso físico (power button)"
    fi
}

# ─── Fix SSH ──────────────────────────────────────────────

do_fix_ssh() {
    log "Tentando restaurar SSH via todos os canais disponíveis..."

    local SSH_FIX_CMD="sudo systemctl restart sshd || sudo systemctl restart ssh || sudo service ssh restart"

    # Método 1: via API tunnel
    if check_api_tunnel; then
        log "Canal encontrado: API tunnel"
        exec_via_api "$SSH_FIX_CMD" && {
            sleep 5
            if check_ssh; then ok "SSH restaurado via API tunnel!"; return 0; fi
        }
    fi

    # Método 2: via API direta
    if check_api_direct; then
        log "Canal encontrado: API direta"
        exec_via_api "$SSH_FIX_CMD" && {
            sleep 5
            if check_ssh; then ok "SSH restaurado via API direta!"; return 0; fi
        }
    fi

    # Método 3: via Telegram
    log "Tentando via Telegram..."
    exec_via_telegram "$SSH_FIX_CMD" 2>/dev/null && {
        log "Comando enviado. Aguardando 15s..."
        sleep 15
        if check_ssh; then ok "SSH restaurado via Telegram!"; return 0; fi
    }

    # Método 4: WoL + wait
    if ! check_ping; then
        log "Server offline. Tentando Wake-on-LAN..."
        do_wol
        if check_ping; then
            log "Server respondeu ao ping. Aguardando SSH..."
            do_wait
            return $?
        fi
    fi

    fail "Todos os métodos falharam. É necessário acesso físico ao servidor."
    echo ""
    echo "Instruções para recovery físico:"
    echo "  1. Conecte teclado e monitor ao servidor"
    echo "  2. Se desligado, ligue-o no botão power"
    echo "  3. Faça login como: $HOMELAB_USER"
    echo "  4. Execute: sudo systemctl restart sshd"
    echo "  5. Verifique: sudo systemctl status sshd"
    echo "  6. Se sshd não existe: sudo apt install openssh-server"
    echo "  7. Verifique firewall: sudo ufw status"
    echo "     Se bloqueado: sudo ufw allow $HOMELAB_SSH_PORT/tcp"
    return 1
}

# ─── Wait ─────────────────────────────────────────────────

do_wait() {
    log "Monitorando até SSH voltar (max ${MAX_RETRIES} tentativas, intervalo ${RETRY_INTERVAL}s)..."
    for i in $(seq 1 "$MAX_RETRIES"); do
        echo -n "  [$i/$MAX_RETRIES] "
        if check_ping; then
            echo -n "ping=OK "
            if check_ssh_port; then
                echo -n "port=OPEN "
                if check_ssh; then
                    echo ""
                    ok "SSH restaurado!"
                    return 0
                else
                    echo "login=FAIL"
                fi
            else
                echo "port=CLOSED"
            fi
        else
            echo "ping=FAIL"
        fi
        sleep "$RETRY_INTERVAL"
    done
    fail "Timeout após $((MAX_RETRIES * RETRY_INTERVAL))s"
    return 1
}

# ─── Safeguard ────────────────────────────────────────────

do_safeguard() {
    log "Instalando safeguard no homelab (cron que garante SSH ativo)..."

    local SAFEGUARD_SCRIPT='#!/bin/bash
# Auto-recovery: garante que sshd está rodando
# Instalado por homelab_recovery/recover.sh
if ! systemctl is-active --quiet sshd && ! systemctl is-active --quiet ssh; then
    systemctl start sshd 2>/dev/null || systemctl start ssh 2>/dev/null
    logger "homelab-safeguard: SSH service was down, restarted"
fi
# Garante que a porta 22 está aberta no firewall
if command -v ufw &>/dev/null && ufw status | grep -q "active"; then
    ufw allow 22/tcp 2>/dev/null
fi
'

    local CRON_LINE="* * * * * /usr/local/bin/homelab-ssh-safeguard.sh"

    if check_ssh; then
        log "SSH disponível, instalando via SSH direto..."
        echo "$SAFEGUARD_SCRIPT" | ssh "${HOMELAB_USER}@${HOMELAB_HOST}" \
            'sudo tee /usr/local/bin/homelab-ssh-safeguard.sh > /dev/null && sudo chmod +x /usr/local/bin/homelab-ssh-safeguard.sh'
        ssh "${HOMELAB_USER}@${HOMELAB_HOST}" \
            "(sudo crontab -l 2>/dev/null | grep -v homelab-ssh-safeguard; echo '$CRON_LINE') | sudo crontab -"
        ok "Safeguard instalado via SSH"
    elif check_api_tunnel || check_api_direct; then
        log "Instalando via API..."
        local encoded_script
        encoded_script=$(echo "$SAFEGUARD_SCRIPT" | base64 -w0)
        exec_via_api "echo '$encoded_script' | base64 -d | sudo tee /usr/local/bin/homelab-ssh-safeguard.sh > /dev/null && sudo chmod +x /usr/local/bin/homelab-ssh-safeguard.sh && (sudo crontab -l 2>/dev/null | grep -v homelab-ssh-safeguard; echo '${CRON_LINE}') | sudo crontab -"
        ok "Safeguard instalado via API"
    else
        fail "Nenhum canal disponível para instalar safeguard"
        return 1
    fi
}

# ─── Auto ─────────────────────────────────────────────────

do_auto() {
    log "Modo automático — tentando todos os métodos de recovery..."
    echo ""

    # 1. Diagnóstico rápido
    do_diagnose
    echo ""

    # 2. Se SSH já funciona, pronto
    if check_ssh; then
        ok "SSH já está funcionando! Nada a fazer."
        return 0
    fi

    # 3. Se offline, WoL
    if ! check_ping; then
        log "Servidor offline. Tentando WoL..."
        do_wol
        if ! check_ping; then
            fail "WoL falhou. Tentando mais uma vez..."
            do_wol
        fi
    fi

    # 4. Tentar fix-ssh
    if check_ping; then
        do_fix_ssh
        return $?
    fi

    fail "Servidor continua inacessível. Acesso físico necessário."
    return 1
}

# ─── Main ─────────────────────────────────────────────────

case "${1:-}" in
    --diagnose|-d)
        do_diagnose
        ;;
    --wol|-w)
        do_wol
        # Após WoL, testar
        if check_ping; then ok "Servidor respondendo ao ping!"
        else warn "Sem resposta após WoL"; fi
        ;;
    --api|-a)
        shift
        exec_via_api "${1:?Uso: recover.sh --api 'comando'}"
        ;;
    --webui)
        shift
        log "WebUI exec não implementado diretamente. Use --api."
        ;;
    --telegram|-t)
        shift
        exec_via_telegram "${1:?Uso: recover.sh --telegram 'comando'}"
        ;;
    --wait)
        do_wait
        ;;
    --fix-ssh|-f)
        do_fix_ssh
        ;;
    --safeguard|-s)
        do_safeguard
        ;;
    --auto)
        do_auto
        ;;
    *)
        echo "Uso: $0 <opção>"
        echo ""
        echo "Opções:"
        echo "  --diagnose, -d       Diagnóstico completo de conectividade"
        echo "  --auto               Tenta todos os métodos automaticamente"
        echo "  --wol, -w            Envia Wake-on-LAN"
        echo "  --api, -a 'cmd'      Executa comando via Agents API (tunnel)"
        echo "  --telegram, -t 'cmd' Envia comando via Telegram bot"
        echo "  --wait               Monitora até SSH voltar"
        echo "  --fix-ssh, -f        Tenta restaurar SSH por todos os canais"
        echo "  --safeguard, -s      Instala cron de auto-restore do SSH"
        echo ""
        echo "Exemplos:"
        echo "  $0 --diagnose"
        echo "  $0 --auto"
        echo "  $0 --api 'sudo systemctl restart sshd'"
        echo "  $0 --wol"
        exit 1
        ;;
esac
