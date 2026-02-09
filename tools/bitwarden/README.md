# Bitwarden helpers

Objetivo: manter todas as secrets e parâmetros fora do repositório, no Bitwarden (CLI `bw` ou Web Vault).

Conteúdo:
- `migrate_to_bw.py` — script Python para exportar `.env` files para JSON formatado para importação (recomendado).
- `migrate_secrets_to_bw.sh` — script bash alternativo (requer CLI `bw` funcional).

## Opção 1: Importação Manual (Recomendada) 

Use este método para migrar localmente sem depender de CLI issues:

```bash
# 1. Exportar arquivo .env para JSON Bitwarden-compatible
python3 tools/bitwarden/export_env_to_bw.py ~/.secrets/.env.jira

# 2. Abra Bitwarden Web Vault (https://vault.bitwarden.com)
# 3. Vá em Settings → Import Data
# 4. Escolha 'Bitwarden (json)' e selecione .env_bitwarden.json
# 5. Clique Import
# 6. Após confirmar no Web Vault, remova o arquivo local:
rm ~/.secrets/.env.jira
```

## Opção 2: Migração via CLI (se bw create item funcionar)

Se o `bw create item` estiver funcionando em seu ambiente:

```bash
# 1. Desbloquear e exportar sessão
bw login seu_email@example.com
export BW_SESSION="$(bw unlock --raw)"

# 2. Usar script de migração
chmod +x tools/bitwarden/migrate_secrets_to_bw.sh
./tools/bitwarden/migrate_secrets_to_bw.sh --apply ~/.secrets/.env.jira

# 3. Remover arquivo após confirmar no web vault
rm ~/.secrets/.env.jira
```

## Instalação do Bitwarden CLI (opcional, para Opção 2)

```bash
curl -L "https://github.com/bitwarden/cli/releases/latest/download/bw-linux.zip" -o bw.zip
unzip bw.zip -d /usr/local/bin
chmod +x /usr/local/bin/bw
bw --version
```

## Notas de segurança

- Após importar, **remova o arquivo local** com as secrets: `rm ~/.secrets/.env.jira`
- Nunca comite arquivos com segredos no repositório.
- O arquivo `.env_bitwarden.json` também deve ser removido após importação: `rm .env_bitwarden.json`
- Atualizar pipelines/serviços para buscar valores do Bitwarden (ver próximos passos).

## Próximos passos

- [ ] GitHub Actions: integrar `bw` CLI no runner e buscar secrets dinamicamente
- [ ] Systemd services: adicionar `EnvironmentFile=` que executa `bw` para recuperar valores
- [ ] Pre-commit hook: bloquear commits com padrões de secrets (ex.: `AWS_SECRET`, `API_KEY=`)

