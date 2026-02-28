# Deploy Methods — Self-Healing Services

> **Objetivo**: Corrigir a **causa raiz** do incidente (scripts criados mas nunca instalados como serviços systemd) através de **automação de deployment**.
>
> Três opções estão disponíveis. Escolha baseado em seu caso de uso.

---

## 📊 Comparação de Métodos

| Aspecto | Bash Script | Ansible | GitHub Actions |
|---------|-------------|---------|----------------|
| **Complexidade** | Baixa | Média | Média |
| **Setup inicial** | Nenhum | `pip install ansible` | Configurar secrets |
| **Execução** | Uma vez | Uma vez (idempotent) | Automática |
| **Auditoria** | Logs em /tmp | Stdout + logs | GitHub Actions UI |
| **Rollback** | Manual | Ansible built-in | Revert commit + re-push |
| **Quando usar** | Quick fix local | Production/IaC | CI/CD contínuo |
| **Requer SSH acesso** | Sim | Sim | GitHub runner + SSH key |
| **Documentação** | Este documento | Este documento | `.github/workflows/` |
| **Custo** | Zero | Zero | Free (GitHub Actions) |

---

## 🔧 Método 1: Bash Script

### Quando usar
- Você está **desenvolvendo localmente** e quer testar rapidamente
- Você fez um script novo e quer validar na staging antes de deploy
- Você não tem Ansible instalado
- QUICK FIX: último minuto antes de push

### Pré-requisitos
```bash
# SSH access to homelab
ssh homelab@192.168.15.2 echo "OK"
# Should return: OK

# Scripts devem existir
ls tools/selfheal/*.sh
# Expected: ollama_frozen_monitor.sh, ollama_metrics_exporter.sh
```

### Execução
```bash
# A partir da raiz do projeto
chmod +x deploy_selfhealing_services.sh
./deploy_selfhealing_services.sh [homelab_user] [homelab_host]

# Exemples
./deploy_selfhealing_services.sh               # usa defaults (homelab, 192.168.15.2)
./deploy_selfhealing_services.sh homelab 192.168.15.2
./deploy_selfhealing_services.sh deploy-user 10.0.0.5
```

### O que faz
1. **Transfer**: SCP scripts → `/tmp/` no homelab
2. **Install**: `sudo mv` para `/usr/local/bin/` + `chmod +x`
3. **Systemd**: Create service files em `/etc/systemd/system/`
4. **Reload**: `systemctl daemon-reload`
5. **Enable**: `systemctl enable` para boot automático
6. **Start**: `systemctl start` para iniciar agora
7. **Validate**: Verifica `systemctl is-active` + logs

### Output esperado
```
✅ Conectividade OK
✅ ollama_frozen_monitor.sh transferido
✅ Instalado e executable
✅ Serviço criado
✅ Daemon recarregado
✅ Habilitado para boot
✅ Serviço iniciado
✅ ollama-frozen-monitor está active
✅ ollama-metrics-exporter está active

Log completo: /tmp/selfhealing_deploy_20260228_150245.log
Deployment completado com sucesso!
```

### Troubleshooting
```bash
# Ver logs completos
cat /tmp/selfhealing_deploy_*.log | tail -50

# Se falhar, debugar conectividade
ssh homelab@192.168.15.2 "ls -lh /usr/local/bin/ollama_*"
ssh homelab@192.168.15.2 "sudo systemctl status ollama-frozen-monitor"

# Re-run (é seguro tentar múltiplas vezes)
./deploy_selfhealing_services.sh homelab 192.168.15.2
```

---

## 📜 Método 2: Ansible Playbook (IaC)

### Quando usar
- Você quer **reproducible deployment** (aplicável múltiplas vezes)
- Você usa Ansible em seu infrastructure
- Você quer **idempotência** (safe to run again)
- Production environment
- Você quer documentação código (código IS documentação)

### Pré-requisitos
```bash
# Install Ansible
pip install ansible paramiko

# Verify
ansible --version
# Expected: ansible 2.10+ (any recent version works)

# Setup SSH key
ssh-keyscan -H 192.168.15.2 >> ~/.ssh/known_hosts

# Test connectivity
ansible all -i inventory_homelab.yml -m ping
# Expected: homelab | SUCCESS
```

### Configuração (Primeira vez apenas)

**Arquivo: `inventory_homelab.yml`** (já incluído no repo)
```yaml
all:
  children:
    homelab:
      hosts:
        homelab:
          ansible_host: 192.168.15.2
          ansible_user: homelab
          ansible_ssh_private_key_file: ~/.ssh/id_rsa
```

Se seu setup for diferente, customize:
```bash
# Copy e editar
cp inventory_homelab.yml inventory_custom.yml
nano inventory_custom.yml

# Customizar:
#   ansible_host: seu IP do homelab
#   ansible_user: seu SSH user
#   ansible_ssh_private_key_file: path to your key
```

### Execução
```bash
# Default (192.168.15.2 / homelab user)
ansible-playbook -i inventory_homelab.yml deploy_selfhealing.yml

# Com inventory custom
ansible-playbook -i inventory_custom.yml deploy_selfhealing.yml

# Com extra vars (override)
ansible-playbook -i inventory_homelab.yml deploy_selfhealing.yml \
  --extra-vars "homelab_user=deploy homelab_host=10.0.0.5"

# Verbose (mais logs)
ansible-playbook -i inventory_homelab.yml deploy_selfhealing.yml -vv

# Dry-run (check mode, não faz mudanças)
ansible-playbook -i inventory_homelab.yml deploy_selfhealing.yml --check
```

### O que faz (mesmo do Bash, mas com garantias)
1. **Check Ollama**: Garante que Ollama está running (prerequisite)
2. **Copy scripts**: SCP com permissões corretas
3. **Create services**: Usa template Jinja2 (menos propenso a erro)
4. **Systemd reload**: Atom operation
5. **Enable + Start**: Idempotent (seguro rodar múltiplas vezes)
6. **Cleanup**: Remove old metric files
7. **Validate**: Verifica status, logs, metrics export

### Idempotência — Por que é importante
```bash
# Primeira execução
ansible-playbook -i inventory_homelab.yml deploy_selfhealing.yml
# → Instala scripts, cria services, inicia

# Segunda execução (minutos depois)
ansible-playbook -i inventory_homelab.yml deploy_selfhealing.yml
# → Atualiza scripts (se mudaram), reloads systemd, reinicia services
# → Nenhum erro, resultado idêntico

# Terceira execução (dias depois, em emergency)
ansible-playbook -i inventory_homelab.yml deploy_selfhealing.yml
# → Funciona normalmente, sem surpresas
```

### Output esperado
```
PLAY [Deploy Self-Healing Services to Homelab] ****
TASK [==== PHASE 1: Pre-deployment Checks ====] ***
TASK [Check SSH connectivity] *** ok: [homelab]
TASK [Verify Ollama service exists] *** ok: [homelab]
TASK [==== PHASE 2: Transfer Scripts ====] ***
TASK [Copy selfhealing scripts] *** changed: [homelab] => (item=...)
TASK [==== PHASE 3: Create Systemd Services ====] ***
...

PLAY RECAP *****
homelab : ok=25 changed=4 unreachable=0 failed=0

✅ Self-Healing Services Deployment Complete
```

### Troubleshooting
```bash
# SSH auth failing?
ansible all -i inventory_homelab.yml -m ping -vvv

# Script not found?
ssh homelab@192.168.15.2 "ls tools/selfheal/"

# Service not created?
ssh homelab@192.168.15.2 "ls /etc/systemd/system/ollama-*.service"

# Re-run with debugging
ansible-playbook -i inventory_homelab.yml deploy_selfhealing.yml -vvv
```

---

## 🚀 Método 3: GitHub Actions (CI/CD)

### Quando usar
- Você quer **completely automated deployment** (no human intervention)
- Você fez mudança em `tools/selfheal/` e quer auto-deploy ao push
- Você quer **auditoria completa** (git history = operação history)
- Você quer **notificações** (Slack, Telegram, etc.)
- Você quer **compliance** (só merge se CI passou)

### Pré-requisitos

**1. SSH Key Setup**
```bash
# Gerar chave SSH (ou usar existente)
ssh-keygen -t ed25519 -f ~/.ssh/homelab_deploy -N ""

# Copy public key ao homelab
ssh-copy-id -i ~/.ssh/homelab_deploy homelab@192.168.15.2

# Copy private key (NUNCA COMMITTAR!) ao GitHub Secrets
cat ~/.ssh/homelab_deploy
# → Copy entire content
```

**2. GitHub Secrets Setup**
1. Go to: GitHub repo → Settings → Secrets and variables → Actions
2. Create new secret `HOMELAB_SSH_KEY`
   - Name: `HOMELAB_SSH_KEY`
   - Value: Paste private key (from above)
   - Click "Add secret"
3. (Optional) Create `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` para notificações

**3. Branch Protection (RECOMENDADO)**
1. Go to: Settings → Branches → Branch protection rules
2. Add rule for `main`:
   - ✅ Require deployments to succeed before merging
   - ✅ Require status checks to pass before merging
   - ✅ Select `deploy-selfhealing` workflow
   - Click "Create"

### Execução

**Automático (recomendado)**
```
1. Fazer mudança em tools/selfheal/
2. git add tools/selfheal/
3. git commit -m "feat(selfheal): add new monitoring script"
4. git push origin main
5. ⚡ GitHub Actions automaticamente:
   - Valida scripts
   - Instala via Ansible
   - Verifica systemctl status
   - Notifica Telegram (se configurado)
```

**Manual (trigger via UI)**
1. Go to: GitHub repo → Actions
2. Selecionar workflow: "Deploy Self-Healing Services to Homelab"
3. Click "Run workflow"
4. Inputs:
   - homelab_host: 192.168.15.2 (ou seu IP)
   - homelab_user: homelab (ou seu user)
5. Click "Run workflow"

**Manual (trigger via CLI)**
```bash
# Requer GitHub CLI
gh workflow run deploy-selfhealing.yml \
  -f homelab_host=192.168.15.2 \
  -f homelab_user=homelab
```

### O que faz
1. **Checkout**: Clona repo no GitHub runner
2. **SSH Setup**: Configura chave SSH privada
3. **Ansible**: Executa playbook de deployment
4. **Validation**: Verifica systemctl status
5. **Report**: Gera relatório em artifacts
6. **Notify**: Envia notificações (Telegram, Slack, etc.)

### Verificar status
```bash
# Ver workflow run no GitHub
https://github.com/eddiejdi/eddie-auto-dev/actions

# Ou via CLI
gh run list --workflow=deploy-selfhealing.yml

# Ver logs de uma run específica
gh run view <run-id> --log
```

### Troubleshooting
```bash
# SSH key não funciona?
# 1. Verify: ssh -i ~/.ssh/homelab_deploy homelab@192.168.15.2
# 2. Check GitHub Secrets: copiar key inteira (sem quebras)
# 3. Re-upload ao GitHub Secrets

# Script ainda não é encontrado?
# 1. Check: tools/selfheal/ tem os .sh files?
# 2. Check: Commited to git (git log tools/selfheal/)?
# 3. Re-run workflow

# Workflow nunca foi triggered?
# 1. Check branch protection: main is protected?
# 2. Check: `.github/workflows/deploy-selfhealing.yml` existe?
# 3. Manual trigger via UI (sem esperar push)
```

---

## 🎯 Recomendação Final

### Development (Sua máquina local)
```bash
# Fazer mudança no script
nano tools/selfheal/ollama_frozen_monitor.sh

# Teste rápido antes de push
./deploy_selfhealing_services.sh homelab 192.168.15.2

# Se OK:
git add tools/selfheal/
git commit -m "feat(selfheal): melhorias no monitoramento"
git push origin main
# → GitHub Actions automático faz deploy
```

### CI/CD Pipeline (Recomendado)
```
Local push → GitHub branch protection (require CI) → 
Workflow executa (Ansible deploy) →
Status checks pass → Merge allowed →
Notificação Telegram ✅
```

### Production Repeat Deploy (Emergency fix)
```bash
# Caso de congelamento recorrente, need quick re-deploy
ansible-playbook -i inventory_homelab.yml deploy_selfhealing.yml \
  --extra-vars "ansible_become=yes"

# Ou:
./deploy_selfhealing_services.sh homelab 192.168.15.2
```

---

## 📋 Checklist: Qual Método Usar

- [ ] **Bash Script** se:
  - Está desenvolvendo localmente
  - Quer testar rápido
  - Não tem Ansible
  - One-off quick fix

- [ ] **Ansible** se:
  - Tem multiple deployments planeadas
  - Quer IaC documentado
  - Quer idempotência
  - Quer integração com Ansible Tower/AWX

- [ ] **GitHub Actions** se:
  - Quer sistema completamente automatizado
  - Quer branch protection + CI/CD
  - Quer auditoria completa
  - Quer notificações automáticas
  - Recomendado para PRODUCTION

---

Última atualização: 2026-02-28 18:30 UTC
