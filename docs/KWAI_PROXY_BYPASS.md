# Kwai Browser — Isolamento no Servidor + Bypass de Proxy/VPN

## Contexto

O agente Kwai (`scripts/kwai/`) precisa fazer scraping autenticado de saldo e tarefas de visualização.  
O domínio `kwai.com` está sendo bloqueado/redirecionado para `127.0.0.1` na workstation local (provavelmente por VPN corporativa ou proxy).

**Decisão arquitetural:** o navegador automatizado (`kwai-browser`) roda **exclusivamente no servidor homelab (192.168.15.2)**, sem acesso direto da workstation.  
O container usa `network_mode: bridge` e variáveis `no_proxy` para garantir rota direta até `kwai.com`.

## Exceção de Proxy no Servidor Homelab

Adicione os domínios Kwai na lista de bypass (`no_proxy`) do sistema no **servidor homelab**:

### Opção 1 — Variáveis de ambiente (recomendada para docker)

```bash
# /etc/environment ou /etc/default/docker (ou ~/.bashrc do usuário homelab)
export no_proxy=kwai.com,.kwai.com,m-wallet.kwai.com,m-creative.kwai.com,localhost,127.0.0.1,192.168.15.0/24
export NO_PROXY=$no_proxy
```

### Opção 2 — Docker daemon (para todos os containers)

Edite `/etc/docker/daemon.json`:

```json
{
  "dns": ["8.8.8.8", "1.1.1.1"],
  "dns-opts": ["ndots:0"],
  "dns-search": []
}
```

Reinicie o daemon:
```bash
sudo systemctl restart docker
```

### Opção 3 — Proxy explícito (ex.: Squid, tinyproxy, corporate proxy)

No arquivo de configuração do proxy no homelab (`/etc/squid/squid.conf`, `/etc/tinyproxy/tinyproxy.conf`, etc.):

```
acl kwai dstdomain .kwai.com
acl kwai dstdomain m-wallet.kwai.com
acl kwai dstdomain m-creative.kwai.com

always_direct allow kwai
```

Ou no tinyproxy:
```
FilterDefaultDeny No
ConnectPort 443
ConnectPort 80
```

## Deploy

```bash
# No servidor homelab (192.168.15.2)
./scripts/deploy_kwai_browser.sh
```

O script:
1. Cria senha aleatória para o container
2. Testa conectividade direta com `kwai.com` (bypass proxy)
3. Sobe o container via docker-compose
4. Exibe instruções de acesso via SSH tunnel

## Acesso ao Navegador

**Nunca acesse diretamente da workstation.** Use sempre túnel SSH:

```bash
ssh -L 3016:127.0.0.1:3016 homelab@192.168.15.2
# Depois no browser local: https://localhost:3016/
```

Faça login manual no Kwai (`edenilson.adm@gmail.com`) dentro do container.

## Confirmação de Sucesso

Após login manual, o scraper deve conseguir extrair o saldo automaticamente:

```bash
python scripts/kwai/kwai_scrape_balance.py --virtual-display
```

O arquivo `~/.local/share/kwai-viewer/balance.json` passará a ter `source: "scrape"`.

## Reversão

Se precisar voltar ao modo local (não recomendado):

```bash
docker compose -p kwai-browser -f docker/docker-compose.kwai-browser.yml down
# Remova a exceção de proxy
```

---

**Data:** 2026-07-15  
**Autor:** Eddie Auto-Dev (Grok)  
**Motivo:** Bypass de VPN/proxy que redireciona kwai.com → 127.0.0.1