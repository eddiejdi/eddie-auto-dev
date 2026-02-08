# Homelab Recovery Kit

Ferramentas para restaurar acesso ao homelab quando SSH está indisponível.

## Métodos de recovery (em ordem de prioridade)

| # | Método | Requisito | Script |
|---|--------|-----------|--------|
| 1 | Wake-on-LAN | Servidor desligado, WoL habilitado na BIOS | `recover.sh --wol` |
| 2 | Agents API (via tunnel) | cloudflared rodando, API up | `recover.sh --api` |
| 3 | Open WebUI code exec | Open WebUI rodando | `recover.sh --webui` |
| 4 | Telegram Bot command | Telegram bot rodando | `recover.sh --telegram` |
| 5 | GitHub Actions runner | Self-hosted runner online | Dispatch workflow |
| 6 | USB Recovery | Acesso físico ao servidor | `usb_recovery.sh` |

## Quick start

```bash
# Diagnóstico completo
./recover.sh --diagnose

# Tentar tudo automaticamente
./recover.sh --auto

# Wake-on-LAN
./recover.sh --wol

# Executar comando via API tunnel
./recover.sh --api "sudo systemctl restart sshd"

# Monitorar até SSH voltar
./recover.sh --wait
```

## Configuração

Edite `config.env` com os dados do seu homelab. O script lê automaticamente.

## Prevenção

Para evitar perda de acesso SSH no futuro:
1. **Nunca** altere `/etc/ssh/sshd_config` remotamente sem `at` ou `cron` de rollback
2. Use `recover.sh --safeguard` para instalar cron de auto-restore do SSH
3. Mantenha o tunnel cloudflared como backup de acesso
4. Configure WoL na BIOS do servidor
