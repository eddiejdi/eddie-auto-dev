# Claude Code — Correção de Proxy (2026-04-26)

## Problema

A extensão Claude Code (Anthropic) falhava com os erros:

```
API Error: Unable to connect to API (ConnectionRefused)
API Error: Unable to connect to API (FailedToOpenSocket)
```

## Causa Raiz

O VS Code tem `http.proxy` configurado globalmente para o proxy do homelab:

```json
"http.proxy": "http://192.168.15.2:3128"
```

O domínio `api.anthropic.com` **não estava** na lista `http.noProxy`, então toda requisição do Claude Code era roteada pelo proxy Squid do homelab (`192.168.15.2:3128`). Quando o proxy ou o homelab ficam instáveis, a conexão falha.

## Evidência

```bash
curl -sv https://api.anthropic.com/v1/messages
# * Connected to 192.168.15.2 (192.168.15.2) port 3128  ← passando pelo proxy
```

Conexão direta (sem proxy) funciona:

```bash
curl --noproxy 'api.anthropic.com' https://api.anthropic.com/v1/messages
# HTTP 401 em 0.3s  ← chega na Anthropic (401 = sem API key, esperado)
```

## Correção Aplicada

Arquivo: `~/.config/Code/User/settings.json`

Adicionados ao `http.noProxy`:

```json
"http.noProxy": [
    "localhost",
    "127.0.0.1",
    "::1",
    "wpad",
    "wpad.lan",
    "*.cloudflare.com",
    "*.cloudflareaccess.com",
    "*.cloudflaretunnel.net",
    "cloudflare.com",
    "ssh.rpa4all.com",
    "*.rpa4all.com",
    "api.anthropic.com",
    "*.anthropic.com",
    "statsig.anthropic.com",
    "sentry.io",
    "*.sentry.io"
]
```

## Ativação

Recarregar o VS Code após a alteração:

```
Ctrl+Shift+P → Developer: Reload Window
```

## Observações

- A autenticação OAuth do Claude Code (`~/.claude/.credentials.json`) estava válida com plano Pro — não era problema de credencial.
- O `settings.json` do Claude Code (`~/.claude/settings.json`) continha apenas permissões de ferramentas, sem configuração de endpoint.
- Não há `ANTHROPIC_BASE_URL` configurada, portanto o Claude Code usa `api.anthropic.com` por padrão.
