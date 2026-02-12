# Operações e Runbook

## Checklist de preparação de ambiente
- Garantir `tools/simple_vault/passphrase` presente e válido.
- Inserir chaves obrigatórias no cofre: `eddie/telegram_bot_token`, `eddie/telegram_chat_id`, `openwebui/api_key`, `eddie/tunnel_api_token`.
- Verificar serviços locais: OpenWebUI container, Ollama (se usado), e Agent API (uvicorn).

## Procedimentos comuns
- Atualizar segredos no cofre:
  - Local: `tools/simple_vault/add_secret.sh <name>` (cole valor e encerre).
  - CI: adicionar `OPENWEBUI_API_KEY` / `TELEGRAM_BOT_TOKEN` nos repo secrets para pipelines.
- Aplicar envs systemd para que serviços leiam `SIMPLE_VAULT_PASSPHRASE_FILE`: `tools/simple_vault/apply_systemd_envs.sh`.

## Diagnóstico rápido
- Logs: `journalctl -u specialized-agents-api.service` e `docker logs <open-webui>`.
- Testes de endpoint OpenWebUI: `scripts/test_openwebui_target.sh <host>`.

---

## Cloudflare Tunnel — Operações (atualizado 2026-02-12)

### Usuários e Permissões

| Usuário | UID | Função | Sudo | Grupos |
|---------|-----|--------|------|--------|
| `homelab` | 1000 | Operador geral | **Restrito** (apenas monitoramento cloudflared) | homelab adm lp cdrom dip plugdev lxd docker libvirt lpadmin scanner vboxusers |
| `_rpa4all` | 1001 | Execução cloudflared | Nenhum | _rpa4all |

### Comandos sudo permitidos para `homelab`
```bash
# Verificar status dos tunnels
sudo journalctl -u cloudflared-rpa4all.service --no-pager
sudo systemctl status cloudflared-rpa4all.service
sudo systemctl status resolved-check.timer
sudo less /var/log/cloudflared.log
```

### Verificação de Endpoints (runbook)
```bash
# Validar todos os endpoints de uma vez
for url in \
  "https://www.rpa4all.com" \
  "https://rpa4all.com" \
  "https://openwebui.rpa4all.com" \
  "https://ide.rpa4all.com" \
  "https://grafana.rpa4all.com" \
  "https://homelab.rpa4all.com/health" \
  "https://api.rpa4all.com/agents-api/" \
  "https://api.rpa4all.com/code-runner/"; do
  CODE=$(curl -sI --max-time 8 -o /dev/null -w "%{http_code}" "$url")
  printf "%-42s %s\n" "$url" "$CODE"
done
```

**Códigos esperados:** 200 (sites), 401 (Grafana login), 404 (API raiz sem handler), 405 (code-runner POST only).

### Recovery de Acesso (lockout sudo)
Se `homelab` perder acesso sudo:
1. SSH como `homelab@192.168.15.2`
2. Usar Docker (homelab está no grupo `docker`):
   ```bash
   docker run --rm -v /etc/sudoers.d:/s alpine sh -c "
   cat > /s/homelab-limited <<'EOF'
   Cmnd_Alias CLOUDFLARE_CMDS = /usr/bin/journalctl -u cloudflared*, /usr/bin/systemctl status cloudflared*
   homelab ALL=(root) NOPASSWD: NOEXEC: CLOUDFLARE_CMDS
   EOF
   chmod 0440 /s/homelab-limited"
   ```
3. Validar: `docker run --rm -v /:/host ubuntu:22.04 chroot /host visudo -cf /etc/sudoers.d/homelab-limited`

### Recovery de Servidor Offline
- **MAC WoL:** `d0:94:66:bb:c4:f6`
- **Comando:** `wakeonlan d0:94:66:bb:c4:f6`
- **Prioridade de métodos:** WoL → API tunnel → Open WebUI → Telegram → GitHub Actions → USB

### DNS — Troubleshooting
```bash
# Testar resolução DNS
resolvectl query protocol-v2.argotunnel.com
dig +short protocol-v2.argotunnel.com @8.8.8.8

# Verificar timer de health-check
systemctl status resolved-check.timer

# Forçar restart do resolver
sudo systemctl restart systemd-resolved
```
