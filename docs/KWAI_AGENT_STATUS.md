# Status do Agente Kwai (kawaii) — 2026-07-15

## Resumo Executivo

**Problema original:** O agente Kwai sempre mostrava saldo = 0 (exceto valor manual de R$ 15,75).

**Causa raiz:** 
1. DNS/VPN redirecionava `kwai.com` → `127.0.0.1` (bloqueio)
2. Nenhum perfil Chromium tinha cookies de sessão Kwai
3. Container `kwai-browser` nunca foi implantado no servidor

**Solução aplicada:**
- Arquitetura de **isolamento no servidor homelab (192.168.15.2)**
- Bypass de proxy/VPN configurado no container (`no_proxy`)
- Script de deploy atualizado com verificação de conectividade
- Documentação completa de configuração de bypass

---

## Estado Atual

| Componente | Status | Detalhes |
|------------|--------|----------|
| **Saldo atual** | ✅ R$ 15,75 BRL | `source: "env"` (manual) |
| **Perfil Chromium local** | ✅ Existe | `~/.local/share/kwai-viewer/chrome-profile` |
| **Cookies Kwai** | ❌ Ausentes | Nenhum perfil autenticado |
| **Container kwai-browser** | ❌ Não implantado | Diretório `/home/homelab/docker/kwai-browser` não existe |
| **Testes unitários** | ✅ 25/25 passando | Todos os módulos Kwai validados |
| **Configuração homelab.env** | ✅ Atualizada | Aponta para perfil do container |

---

## O que Foi Modificado

### 1. `docker/docker-compose.kwai-browser.yml`
- Adicionado `no_proxy` explícito para domínios Kwai
- Comentários explicando isolamento no servidor
- `network_mode: bridge` mantido

### 2. `scripts/deploy_kwai_browser.sh`
- Verificação de conectividade direta antes do deploy
- Mensagens de instrução claras sobre bypass
- Reforço de execução exclusiva no servidor

### 3. `config/kwai-viewer.homelab.env`
- `KWAI_CHROME_PROFILE_DIR` aponta para o container
- `KWAI_COOKIE_SOURCE` aponta para o container

### 4. `scripts/kwai/kwai_browser.py`
- Adicionado `--proxy-bypass-list` para domínios Kwai

### 5. Documentação Nova
- `docs/KWAI_PROXY_BYPASS.md` — Guia completo de bypass e deploy
- `docs/KWAI_AGENT_STATUS.md` — Este arquivo

---

## Próximos Passos (para Funcionamento Perfeito)

### Fase 1 — Deploy no Servidor (obrigatório)

No servidor `homelab@192.168.15.2`:

```bash
# 1. Configurar bypass de proxy (escolha uma opção)
echo 'export no_proxy=kwai.com,.kwai.com,m-wallet.kwai.com,m-creative.kwai.com' >> ~/.bashrc
source ~/.bashrc

# 2. Deploy do container
cd /home/homelab/myClaude
./scripts/deploy_kwai_browser.sh

# 3. Acessar via túnel SSH (de qualquer workstation)
ssh -L 3016:127.0.0.1:3016 homelab@192.168.15.2
# Abrir: https://localhost:3016/
```

### Fase 2 — Login Manual

Dentro do navegador do container (`https://localhost:3016/`):

1. Acessar `https://www.kwai.com/discover`
2. Fazer login/cadastro com `edenilson.adm@gmail.com`
3. Navegar até a carteira (`/main/transfer`) e confirmar que o saldo aparece
4. Fechar o navegador (cookies ficam salvos no volume Docker)

### Fase 3 — Validação do Scraper

No servidor homelab:

```bash
# Testar extração de saldo
python /home/homelab/myClaude/scripts/kwai/kwai_scrape_balance.py --virtual-display

# Verificar resultado
cat ~/.local/share/kwai-viewer/balance.json
# Esperado: "source": "scrape", "balance": <valor_real>
```

### Fase 4 — Ativar Automação Contínua (opcional)

```bash
# Copiar env para o local esperado pelo systemd
sudo mkdir -p /etc/eddie
sudo cp /home/homelab/myClaude/config/kwai-viewer.homelab.env /etc/eddie/kwai-viewer.env

# Habilitar timer do kwai-viewer (se existir)
sudo systemctl enable --now kwai-viewer.timer
```

---

## Comandos Úteis

```bash
# Verificar saldo atual
cat ~/.local/share/kwai-viewer/balance.json

# Ver histórico
cat ~/.local/share/kwai-viewer/balance-history.csv

# Debug do scraper (com interface)
python scripts/kwai/kwai_scrape_balance.py --headed

# Ver logs do container (no servidor)
docker logs -f kwai-browser

# Parar container
docker compose -p kwai-browser -f docker/docker-compose.kwai-browser.yml down
```

---

## Arquitetura Final

```
┌─────────────────────────────────────────────────────────────┐
│                    WORKSTATION LOCAL                        │
│  (VPN ativa → kwai.com redirecionado para 127.0.0.1)       │
│                                                             │
│  Acesso via SSH tunnel:                                     │
│    ssh -L 3016:127.0.0.1:3016 homelab@192.168.15.2         │
│    → https://localhost:3016/                                │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                │ SSH Tunnel (criptografado)
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                  SERVIDOR HOMELAB (192.168.15.2)            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  kwai-browser (container Docker)                     │   │
│  │  - Chromium isolado                                  │   │
│  │  - no_proxy=*.kwai.com (bypass VPN/proxy)           │   │
│  │  - Login manual → cookies salvos em /config         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  kwai-viewer (Python + Selenium)                     │   │
│  │  - Usa cookies do container                         │   │
│  │  - Extrai saldo automaticamente                     │   │
│  │  - Salva em balance.json (source: "scrape")         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

**Status:** Aguardando deploy no servidor homelab para completar o ciclo.  
**Testes:** 100% passando.  
**Documentação:** Completa.