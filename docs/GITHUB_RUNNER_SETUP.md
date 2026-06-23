# GitHub Actions Runner — Orange Pi Zero 2W

## ✅ Status: ATIVO E ONLINE

**Runner registrado e operacional desde 2026-06-22 22:08:36 UTC-3**

- **Status**: `online` 🟢
- **Serviço systemd**: `actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w`
- **PID**: 11848 (Runner.Listener)
- **Versão**: v2.335.1 (ARM64/Linux)
- **Memória**: 34.8MB
- **Uptime**: contínuo (auto-reinicia em boot)

## Hardware & Ambiente

| Propriedade | Valor |
|------------|-------|
| **Hostname** | orangepizero2w |
| **IP (LAN)** | 192.168.15.166/24 |
| **IP (WAN)** | 79.127.164.75 |
| **Arquitetura** | ARM64 (aarch64) |
| **CPU** | Quad-core Cortex-A53/A72 |
| **CPU Cores** | 4 |
| **RAM** | 3.83 GB |
| **Disco** | 29 GB (SD card) |
| **SO** | Debian 13 (Trixie) |
| **Kernel** | 6.18.35-current-sunxi64 |
| **Armbian** | v26.8.0 rolling |
| **Temperature** | 50°C (normal) |

## Como Ativar o Runner

### 1. Gerar GitHub Personal Access Token

1. Acessar: https://github.com/settings/tokens/new
2. Nome: `orangepi-runner-token`
3. Escopos necessários:
   - ✅ `repo` (para repositórios)
   - ✅ `admin:org_hook` (para registrar runner)
4. Copiar o token (exemplo: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)

### 2. Conectar ao Orange Pi e Executar Setup

```bash
# Conectar direto (mesma rede local 192.168.15.x)
ssh orangepi@192.168.15.166
# Senha: rpa4all@2026

# Uma vez no Orange Pi:
cd ~
./setup-gh-runner.sh <SEU_GITHUB_TOKEN> orangepi-zero2w eddiejdi/eddie-auto-dev
```

### 3. Verificar Status

```bash
# Status do serviço
sudo systemctl status actions-runner

# Logs em tempo real
sudo journalctl -u actions-runner -f

# Verificar no GitHub
# https://github.com/eddiejdi/eddie-auto-dev/settings/actions/runners
```

## Configuração Aplicada (2026-06-22)

### Processo de Setup
1. ✅ Download runner v2.335.1 (ARM64): 133MB
2. ✅ Transferência via SCP para `/tmp/actions-runner-linux-arm64.tar.gz`
3. ✅ Extração em `/tmp/runner-extract`
4. ✅ Geração de runner token via `gh api` (AHX3H72RRUU2NUYUWDXNJXLKHHVHG)
5. ✅ Execução de `config.sh --unattended --replace`
6. ✅ Instalação de serviço systemd via `svc.sh install orangepi`
7. ✅ Ativação com `systemctl start` e `enable`

### Arquivos de Configuração
- **Config**: `/tmp/runner-extract/.runner`
- **Serviço**: `/etc/systemd/system/actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w.service`
- **Runner Home**: `/tmp/runner-extract` (durante sessão) ou `/opt/actions-runner` (produção)

### Labels Registrados
```json
{
  "self-hosted": "read-only (padrão GitHub)",
  "Linux": "read-only (detectado automaticamente)",
  "ARM64": "read-only (detectado automaticamente)",
  "orangepi": "custom",
  "arm64": "custom",
  "edge-device": "custom"
}
```

### Verificação da Saúde
```bash
# No Orange Pi
sshpass -p 'rpa4all@2026' ssh orangepi@192.168.15.166 << 'EOF'
SERVICE="actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w"
sudo systemctl status $SERVICE --no-pager
EOF
```

**Output esperado:**
```
● actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w.service - GitHub Actions Runner
  Loaded: loaded; enabled
  Active: active (running)
  Memory: 34.8M
```

---

## Usar o Runner em Workflows

### Exemplo Básico
Adicione ao arquivo `.github/workflows/seu-workflow.yml`:

```yaml
jobs:
  build-on-orangepi:
    runs-on: orangepi-zero2w
    steps:
      - uses: actions/checkout@v4
      - name: System Info
        run: |
          echo "Rodando no Orange Pi Zero 2W"
          uname -m
          df -h
          free -h
```

### Múltiplos Labels
```yaml
jobs:
  build:
    runs-on: [self-hosted, arm64, orangepi]
    steps:
      - uses: actions/checkout@v4
      - run: echo "Using multiple labels"
```

### Executar apenas em ARM64
```yaml
jobs:
  arm64-build:
    runs-on: [self-hosted, ARM64]
    steps:
      - uses: actions/checkout@v4
      - run: cargo build --target aarch64-unknown-linux-gnu
```

---

## Monitoramento

### Logs do Runner

**Em tempo real:**
```bash
sshpass -p 'rpa4all@2026' ssh orangepi@192.168.15.166 \
  'sudo journalctl -u actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w -f'
```

**Últimas 50 linhas:**
```bash
sshpass -p 'rpa4all@2026' ssh orangepi@192.168.15.166 \
  'sudo journalctl -u actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w -n 50'
```

### Monitoramento de Recursos

```bash
# SSH para Orange Pi
sshpass -p 'rpa4all@2026' ssh orangepi@192.168.15.166

# CPU e Memória
htop

# Status de disco
df -h /

# Temperatura
cat /sys/class/thermal/thermal_zone0/temp
```

### Verificação via API GitHub

**Listar todos os runners:**
```bash
gh api repos/eddiejdi/eddie-auto-dev/actions/runners
```

**Ver status do runner específico:**
```bash
gh api repos/eddiejdi/eddie-auto-dev/actions/runners \
  --jq '.runners[] | select(.name=="orangepi-zero2w")'
```

**Ver jobs executados:**
```bash
gh run list eddiejdi/eddie-auto-dev --limit 10
```

---

## Solução de Problemas

### Runner não aparece online

**Verificar serviço:**
```bash
sshpass -p 'rpa4all@2026' ssh orangepi@192.168.15.166 \
  'sudo systemctl status actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w'
```

**Reiniciar serviço:**
```bash
sshpass -p 'rpa4all@2026' ssh orangepi@192.168.15.166 << 'EOF'
SERVICE="actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w"
sudo systemctl restart $SERVICE
sleep 3
sudo systemctl status $SERVICE --no-pager
EOF
```

### Verificar logs de erro

```bash
sshpass -p 'rpa4all@2026' ssh orangepi@192.168.15.166 << 'EOF'
SERVICE="actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w"
echo "=== Últimos erros ==="
sudo journalctl -u $SERVICE -p err -n 20
echo ""
echo "=== Últimas atividades ==="
sudo journalctl -u $SERVICE -n 30
EOF
```

### Runner sai de linha frequentemente

**Possíveis causas:**
1. Problema de conectividade de rede
2. Recurso de memória insuficiente
3. Timeout de conexão com GitHub

**Verificação:**
```bash
# Conectividade
sshpass -p 'rpa4all@2026' ssh orangepi@192.168.15.166 \
  'ping -c 4 api.github.com'

# Memória disponível
sshpass -p 'rpa4all@2026' ssh orangepi@192.168.15.166 \
  'free -h'

# Verificar firewall
sshpass -p 'rpa4all@2026' ssh orangepi@192.168.15.166 \
  'sudo ufw status'
```

### Remover/Reconfigurar Runner

**Se necessário desregistrar e reconfigurar:**

```bash
sshpass -p 'rpa4all@2026' ssh orangepi@192.168.15.166 << 'EOF'
SERVICE="actions.runner.eddiejdi-eddie-auto-dev.orangepi-zero2w"

# Parar serviço
sudo systemctl stop $SERVICE

# Desinstalar
cd /tmp/runner-extract
sudo ./svc.sh uninstall

# Remover configuração
rm -f .runner
rm -rf _work _diag

# Reexecutar config.sh com novo token
# (gerar token: gh api repos/eddiejdi/eddie-auto-dev/actions/runners/registration-token --method POST)
EOF
```

---

## Autenticação & Segurança

### Credenciais

| Item | Local | Segurança |
|------|-------|----------|
| SSH user | `orangepi` | Senha: `rpa4all@2026` |
| Runner token | Generated (ephemeral) | Expira após 1 hora |
| LDAP | Authentik @ 192.168.15.2 | Via SSSD/nslcd |

### Firewall
- SSH (22): Aberto para LAN (192.168.15.0/24)
- HTTPS (443): Necessário para GitHub API
- Bidirecional para GitHub (api.github.com:443)

---

## Referências

- [GitHub Actions - Self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- [GitHub Runner Releases](https://github.com/actions/runner/releases)
- [GitHub CLI Documentation](https://cli.github.com/manual)
- [Armbian - Orange Pi Zero 2W](https://www.armbian.com/orange-pi-zero-2w/)
- [GitHub Runner API](https://docs.github.com/en/rest/actions/self-hosted-runners)

---

## Links Úteis

- **GitHub Runners UI**: https://github.com/eddiejdi/eddie-auto-dev/settings/actions/runners
- **Repository**: https://github.com/eddiejdi/eddie-auto-dev
- **Workflows**: https://github.com/eddiejdi/eddie-auto-dev/actions

---

**Last Updated**: 2026-06-22 22:08:36 UTC-3  
**Status**: ✅ Operacional
