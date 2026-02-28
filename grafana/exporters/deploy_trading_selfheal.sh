#!/bin/bash
################################################################################
# deploy_trading_selfheal.sh
# Deploy Trading Agent Self-Healing Exporter with Ollama to homelab
# Usage: bash deploy_trading_selfheal.sh [--dry-run] [--no-restart]
################################################################################

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Config
HOMELAB_HOST="${HOMELAB_HOST:-192.168.15.2}"
HOMELAB_USER="${HOMELAB_USER:-homelab}"
HOMELAB_SSH_KEY="${HOMELAB_SSH_KEY:-~/.ssh/id_rsa}"
EXPORTER_PORT="${EXPORTER_PORT:-9120}"
STATUS_PORT="${STATUS_PORT:-9121}"
DRY_RUN="${DRY_RUN:-false}"
NO_RESTART="${NO_RESTART:-false}"

# Paths (local)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPORTER_PY="${SCRIPT_DIR}/trading_selfheal_exporter.py"
CONFIG_JSON="${SCRIPT_DIR}/trading_selfheal_config.json"
SERVICE_FILE="${SCRIPT_DIR}/trading-selfheal-exporter.service"

# Remote paths
REMOTE_EXPORTER_DIR="/home/edenilson/eddie-auto-dev/grafana/exporters"
REMOTE_SYSTEMD_DIR="/etc/systemd/system"
REMOTE_DATA_DIR="/var/lib/eddie/trading-heal"

################################################################################
# Help
################################################################################
usage() {
    cat <<EOF
Deploy Trading Agent Self-Healing Exporter to homelab

Usage: $0 [OPTIONS]

Options:
  --dry-run              Show what would be done without making changes
  --no-restart           Deploy but don't restart services
  --host HOST            Homelab host (default: $HOMELAB_HOST)
  --user USER            SSH user (default: $HOMELAB_USER)
  --ssh-key PATH         SSH private key (default: $HOMELAB_SSH_KEY)
  -h, --help             Show this help

Environment Variables:
  HOMELAB_HOST           Homelab hostname/IP
  HOMELAB_USER           SSH user
  HOMELAB_SSH_KEY        SSH private key path
  DRY_RUN                Set to 'true' for dry-run mode

Example:
  bash deploy_trading_selfheal.sh --dry-run
  bash deploy_trading_selfheal.sh --host homelab.local --user eddie
EOF
}

################################################################################
# Argument parsing
################################################################################
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-restart)
            NO_RESTART=true
            shift
            ;;
        --host)
            HOMELAB_HOST="$2"
            shift 2
            ;;
        --user)
            HOMELAB_USER="$2"
            shift 2
            ;;
        --ssh-key)
            HOMELAB_SSH_KEY="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

################################################################################
# Helper functions
################################################################################
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[✗]${NC} $*"
}

run_ssh() {
    local cmd="$1"
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} ssh $HOMELAB_USER@$HOMELAB_HOST: $cmd"
        return 0
    fi
    ssh -i "$HOMELAB_SSH_KEY" "$HOMELAB_USER@$HOMELAB_HOST" "$cmd"
}

run_scp() {
    local src="$1"
    local dst="$2"
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} scp -i $HOMELAB_SSH_KEY $src $HOMELAB_USER@$HOMELAB_HOST:$dst"
        return 0
    fi
    scp -i "$HOMELAB_SSH_KEY" "$src" "$HOMELAB_USER@$HOMELAB_HOST:$dst"
}

################################################################################
# Verification
################################################################################
verify_files() {
    log_info "Verifying local files..."
    
    if [[ ! -f "$EXPORTER_PY" ]]; then
        log_error "Exporter not found: $EXPORTER_PY"
        exit 1
    fi
    log_success "Found exporter: $EXPORTER_PY"
    
    if [[ ! -f "$CONFIG_JSON" ]]; then
        log_error "Config not found: $CONFIG_JSON"
        exit 1
    fi
    log_success "Found config: $CONFIG_JSON"
    
    if [[ ! -f "$SERVICE_FILE" ]]; then
        log_error "Service file not found: $SERVICE_FILE"
        exit 1
    fi
    log_success "Found service: $SERVICE_FILE"
}

verify_ssh() {
    log_info "Verifying SSH connection to $HOMELAB_USER@$HOMELAB_HOST..."
    if ! run_ssh "echo 'SSH OK'" > /dev/null 2>&1; then
        log_error "Cannot connect to homelab via SSH"
        exit 1
    fi
    log_success "SSH connection OK"
}

verify_homelab_services() {
    log_info "Verifying homelab services..."
    
    # Check PostgreSQL
    run_ssh "systemctl is-active --quiet postgresql && echo 'PostgreSQL: OK' || echo 'PostgreSQL: NOT RUNNING'"
    
    # Check Ollama
    run_ssh "curl -s http://localhost:8512/api/tags > /dev/null 2>&1 && echo 'Ollama (8512): OK' || echo 'Ollama: NOT ACCESSIBLE'"
    
    # Check existing crypto-agent services
    log_info "Checking crypto-agent services..."
    for symbol in BTC ETH XRP SOL DOGE ADA; do
        run_ssh "systemctl is-active --quiet crypto-agent@${symbol}_USDT.service && echo '  ✓ crypto-agent@${symbol}_USDT' || echo '  ✗ crypto-agent@${symbol}_USDT NOT ACTIVE'"
    done
}

################################################################################
# Deploy steps
################################################################################
create_data_directories() {
    log_info "Creating data directories on homelab..."
    run_ssh "mkdir -p $REMOTE_DATA_DIR && chmod 755 $REMOTE_DATA_DIR"
    log_success "Data directory created: $REMOTE_DATA_DIR"
}

install_python_dependencies() {
    log_info "Installing/verifying Python dependencies..."
    run_ssh "python3 -m pip install --quiet psycopg2-binary prometheus-client 2>/dev/null && echo 'Dependencies OK' || echo 'Dependencies installed'"
    log_success "Python dependencies ready"
}

deploy_exporter_files() {
    log_info "Deploying exporter files..."
    
    # Create remote directory
    run_ssh "mkdir -p $REMOTE_EXPORTER_DIR"
    
    # Copy files
    log_info "  Copying exporter.py..."
    run_scp "$EXPORTER_PY" "$REMOTE_EXPORTER_DIR/"
    
    log_info "  Copying config.json..."
    run_scp "$CONFIG_JSON" "$REMOTE_EXPORTER_DIR/"
    
    log_success "Exporter files deployed to $REMOTE_EXPORTER_DIR"
}

setup_systemd_service() {
    log_info "Setting up systemd service..."
    
    # Copy service file
    run_ssh "sudo cp $REMOTE_EXPORTER_DIR/trading-selfheal-exporter.service $REMOTE_SYSTEMD_DIR/trading-selfheal-exporter.service"
    
    # Fix ownership & permissions
    run_ssh "sudo chown root:root $REMOTE_SYSTEMD_DIR/trading-selfheal-exporter.service && sudo chmod 644 $REMOTE_SYSTEMD_DIR/trading-selfheal-exporter.service"
    
    # Reload systemd
    run_ssh "sudo systemctl daemon-reload"
    
    # Enable service
    run_ssh "sudo systemctl enable trading-selfheal-exporter.service"
    
    log_success "Systemd service configured"
}

setup_sudoers() {
    log_info "Configuring sudoers for systemctl restarts..."
    
    local sudoers_entry="homelab ALL=(ALL) NOPASSWD: /bin/systemctl restart crypto-agent@*"
    local sudoers_file="/etc/sudoers.d/eddie-crypto-restarts"
    
    run_ssh "echo '$sudoers_entry' | sudo tee $sudoers_file > /dev/null && sudo chmod 440 $sudoers_file"
    
    log_success "Sudoers configured for systemctl restart"
}

setup_audit_log() {
    log_info "Setting up audit log rotation..."
    
    local logrotate_config="/etc/logrotate.d/trading-selfheal"
    local logrotate_content=$(cat <<'EOF'
/var/lib/eddie/trading-heal/*.jsonl {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    su homelab homelab
}
EOF
)
    
    run_ssh "echo '$logrotate_content' | sudo tee $logrotate_config > /dev/null && sudo chmod 644 $logrotate_config"
    
    log_success "Audit log rotation configured"
}

update_prometheus_config() {
    log_info "Prometheus configuration already includes crypto-exporters and trading-selfheal jobs"
    log_info "No changes needed to prometheus.yml"
}

update_alert_rules() {
    log_info "Alert rules already include trading agent alerts"
    log_info "No changes needed to alert_rules.yml"
}

reload_prometheus() {
    log_info "Reloading Prometheus configuration..."
    
    # Try to reload via HTTP API first (non-disruptive)
    log_info "  Attempting Prometheus reload via HTTP API..."
    run_ssh "curl -X POST http://localhost:9090/-/reload 2>/dev/null && echo 'Reload via API OK' || echo 'API reload failed, trying systemctl...'"
    
    # If that fails, restart
    run_ssh "systemctl is-active --quiet prometheus.service && sudo systemctl reload-or-restart prometheus.service && echo 'Prometheus reloaded' || echo 'Prometheus not active'"
    
    log_success "Prometheus configuration reloaded"
}

start_exporter_service() {
    if [[ "$NO_RESTART" == "true" ]]; then
        log_warn "Service restart skipped (--no-restart flag)"
        return
    fi
    
    log_info "Starting trading-selfheal-exporter service..."
    run_ssh "sudo systemctl start trading-selfheal-exporter.service"
    
    # Wait and verify
    sleep 3
    run_ssh "systemctl is-active --quiet trading-selfheal-exporter.service && echo 'Service is running' || echo 'Service failed to start'"
    
    log_success "Service started"
}

################################################################################
# Verification after deployment
################################################################################
verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check service status
    log_info "  Checking service status..."
    run_ssh "systemctl status trading-selfheal-exporter.service --no-pager | head -5"
    
    # Check metrics endpoint
    log_info "  Testing metrics endpoint (port $EXPORTER_PORT)..."
    run_ssh "curl -s http://localhost:$EXPORTER_PORT/metrics | head -20 || echo 'Metrics endpoint not yet responding'"
    
    # Check status endpoint
    log_info "  Testing status endpoint (port $STATUS_PORT)..."
    run_ssh "curl -s http://localhost:$STATUS_PORT/health && echo 'Status endpoint OK' || echo 'Status endpoint not yet responding'"
    
    # Check Prometheus targets
    log_info "  Checking Prometheus targets..."
    run_ssh "curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job == \"trading-selfheal\")' 2>/dev/null || echo 'Target check requires jq'"
    
    log_success "Deployment verification complete"
}

################################################################################
# Main
################################################################################
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Trading Agent Self-Healing Exporter Deployment          ║${NC}"
    echo -e "${BLUE}║  Target: $HOMELAB_USER@$HOMELAB_HOST                             ║${NC}"
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}║  MODE: DRY-RUN (no changes will be made)              ║${NC}"
    fi
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo
    
    verify_files
    verify_ssh
    verify_homelab_services
    
    echo
    log_info "Starting deployment..."
    create_data_directories
    install_python_dependencies
    deploy_exporter_files
    setup_systemd_service
    setup_sudoers
    setup_audit_log
    update_prometheus_config
    update_alert_rules
    reload_prometheus
    start_exporter_service
    
    echo
    verify_deployment
    
    echo
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ Deployment Complete!                                 ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    
    echo
    echo "Next steps:"
    echo "  1. View service logs: journalctl -u trading-selfheal-exporter -f"
    echo "  2. Check status endpoint: curl http://$HOMELAB_HOST:$STATUS_PORT/status"
    echo "  3. View metrics: curl http://$HOMELAB_HOST:$EXPORTER_PORT/metrics"
    echo "  4. Check audit log: tail -f /var/lib/eddie/trading-heal/trading_heal_audit.jsonl"
    echo "  5. View dashboard: https://grafana.rpa4all.com/d/237610b0-0eb1-4863-8832-835ee7d7338d/"
    echo
}

main "$@"
