# GitHub Runner — Orange Pi Zero 2W

## Status Atual

✅ **Preparado para ativação**
- GitHub CLI: instalado (v2.95.0)
- Script de setup: `/home/orangepi/setup-gh-runner.sh`
- Diretório runner: `/opt/actions-runner` (pronto)
- Autenticação LDAP: ✅ Configurada
- SSH: ✅ Ativo (192.168.15.166)

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

**Exemplo real:**
```bash
./setup-gh-runner.sh ghp_abc123def456... orangepi-zero2w eddiejdi/eddie-auto-dev
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

## Usar o Runner em Workflows

Adicione ao arquivo `.github/workflows/seu-workflow.yml`:

```yaml
jobs:
  build:
    runs-on: orangepi-zero2w
    steps:
      - uses: actions/checkout@v4
      - name: Run on Orange Pi
        run: |
          echo "Rodando no Orange Pi Zero 2W"
          uname -m
          df -h
```

## Características

| Propriedade | Valor |
|------------|-------|
| **Hostname** | orangepizero2w |
| **IP** | 192.168.15.166 |
| **Arquitetura** | ARM64 (aarch64) |
| **CPU Cores** | 4 |
| **RAM** | 3.83 GB |
| **Disco** | 29 GB |
| **SO** | Debian 13 (Trixie) |
| **Labels** | `orangepi`, `arm64`, `edge-device` |

## Solução de Problemas

### O script falha ao baixar

Se houver problema de conectividade, o runner pode ser baixado localmente:

```bash
# Local (na máquina com VS Code)
wget https://github.com/actions/runner/releases/download/v2.123.0/actions-runner-linux-arm64-2.123.0.tar.gz

# Copiar para Orange Pi via SCP
scp actions-runner-linux-arm64-2.123.0.tar.gz orangepi@192.168.15.166:/tmp/

# No Orange Pi, colocar em /opt/actions-runner/
sudo cp /tmp/actions-runner-linux-arm64-2.123.0.tar.gz /opt/actions-runner/
```

### Runner não inicia

```bash
# Verificar erros
sudo journalctl -u actions-runner -n 50

# Reiniciar
sudo systemctl restart actions-runner

# Logs detalhados
sudo systemctl status actions-runner -l
```

### Remover/Reconfigurar

```bash
# Parar serviço
sudo systemctl stop actions-runner

# Desinstalar
cd /opt/actions-runner
sudo ./svc.sh uninstall

# Limpar diretório
sudo rm -rf /opt/actions-runner/*

# Reexecutar setup
cd ~
./setup-gh-runner.sh <TOKEN> orangepi-zero2w eddiejdi/eddie-auto-dev
```

## Referências

- [GitHub Actions - Self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- [GitHub Runner Releases](https://github.com/actions/runner/releases)
- [GitHub CLI Documentation](https://cli.github.com/manual)
