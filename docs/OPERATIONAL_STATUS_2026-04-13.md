# Status Operacional — 13 de abril de 2026

> Consolidação de todas as operações e configurações ativas em 2026-04-13.

---

## 1. VPN & Proxy — US → Panamá (Fora de Five Eyes)

### Status
- **Provider**: NordVPN NORDLYNX (WireGuard)
- **Servidor**: `pa3.nordvpn.com`
- **IP Público**: `185.239.149.21`
- **Jurisdição**: Panamá (fora de Five Eyes/14 Eyes/Nine Eyes)
- **Status**: Connected ✅
- **Killswitch**: Ativo via nftables (fwmark `0xe1f1`)
- **Auto-reconnect**: Habilitado (permanente)

### Justificativa
- **Anterior (US)**: Five Eyes jurisdiction (NSA/GCHQ acesso)
- **Atual (Panamá)**: Fora de alianças de vigilância internacional
- **Benefício**: Privacidade máxima, sem logs compulsórios

### Validação
```bash
# Verificar status
nordvpn status | grep -E "Status|Country"
# Output: Status: Connected, Country: Panama ✅

# Verificar IP público
curl -s https://api.myip.com | jq '.ip'
# Output: 185.239.149.21 (Panamá) ✅
```

### Documentação Técnica
- Arquivo: `docs/VPN_PANAMA_CONFIG_2026-04-12.md`
- Inclui: Policy routing, nftables rules, rollback procedure, comparação Five Eyes vs Panamá

---

## 2. Wiki.js + Authentik OIDC — Autenticação Centralizada

### Status
- **Container**: `wiki.js` (ghcr.io/requarks/wiki:2)
- **Status**: running ✅
- **Porta**: 3009 (interno), 3009:3009 (Docker)
- **Banco de dados**: PostgreSQL 15 (compartilhado com Authentik)
- **OIDC Provider**: Authentik (`http://authentik-server:9000`)

### Estratégias de Autenticação Ativas
```
✅ Strategy Local (fallback)
✅ Strategy Authentik SSO (OIDC)
```

### Configuração OIDC
| Parâmetro | Valor |
|-----------|-------|
| OIDC_ISSUER | `http://authentik-server:9000` |
| OIDC_CLIENT_ID | `wikijs-3cd3a4331641a2b7` |
| OIDC_TOKEN_ENDPOINT | `http://authentik-server:9000/application/o/token/` |
| OIDC_USERINFO_ENDPOINT | `http://authentik-server:9000/application/o/userinfo/` |
| OIDC_AUTHORIZATION_ENDPOINT | `http://authentik-server:9000/application/o/authorize/` |

### Validação
```bash
# Verificar container status
docker inspect wikijs --format "Status: {{.State.Status}}"
# Output: Status: running ✅

# Verificar OIDC Strategy ativa nos logs
docker logs wikijs 2>&1 | grep "Authentication Strategy Authentik SSO"
# Output: Authentication Strategy Authentik SSO: [ OK ] ✅

# Verificar 21 strategies carregadas
docker logs wikijs 2>&1 | grep "Loaded.*authentication strategies"
# Output: Loaded 21 authentication strategies: [ OK ] ✅
```

### Documentação Técnica
- Arquivo: `docker/docker-compose.wikijs.yml` (OIDC vars)
- Commits:
  - `0b095d11`: config: integração OIDC Authentik na Wiki.js
  - `19f885a7`: fix: adicionar OIDC_ISSUER para Authentik SSO na Wiki.js

---

## 3. iVentoy — Servidor PXE com ISO Fedora SoaS (Novo)

### Status
- **Serviço**: iVentoy (PXE boot server)
- **Localização**: `/opt/iventoy`
- **ISO Ativa**: Fedora SoaS (v4 com modo texto como default)
- **Status**: Recarregado em 2026-04-13 ✅

### Configuração
- **Default Boot Mode**: Modo TEXTO (terminal + login liveuser)
- **Alvo**: Netbook/Atom (baixo spec, preferência texto)
- **Repositório**: ISO mantida em iVentoy

### Como Usar
1. Reiniciar netbook
2. Carregar Fedora SoaS via PXE
3. Default é modo texto (terminal + login `liveuser`)
4. GUI disponível se executar `startx`

### Validação
```bash
ssh homelab 'cd /opt/iventoy && sudo bash iventoy.sh status | tail -2'
# Output: iVentoy status operacional ✅
```

### Mudanças Recentes
- ISO v4 recarregada com modo texto como default
- Confirmação enviada via Telegram ao usuário
- Pronto para boot PXE imediato

---

## 4. Infraestrutura Suportante

### Serviços Críticos
| Serviço | Porta | Status | Notas |
|---------|-------|--------|-------|
| FastAPI | 8503 | Planejado | Orquestração agentes |
| Streamlit | 8502 | Variável | Dashboard |
| Ollama GPU0 | 11434 | Ativo | RTX 2060 |
| Ollama GPU1 | 11435 | Ativo | GTX 1050 |
| PostgreSQL | 5433 | Ativo | Trading + Wiki + Authentik |
| Authentik | 9000 | Ativo | OIDC provider |
| Wiki.js | 3009 | Ativo | Knowledge base |
| Prometheus | 9090 | Ativo | Métricas |
| Grafana | 3002 | Ativo | Dashboards |

### Redes
- **Bridge Docker**: 172.18.0.0/16 (containers internos)
- **VPN**: WireGuard NordVPN (internet saindo por Panamá)
- **Homelab**: 192.168.15.0/24 (LAN)

---

## 5. Repositório Git — Estado Sincronizado

### Branch Ativo
- **Branch**: `main`
- **HEAD**: commit `19f885a7`
- **Remote Origin**: Sincronizado ✅
- **Working Tree**: Clean (sem uncommitted changes)

### Últimos Commits
```
19f885a7 fix: adicionar OIDC_ISSUER para Authentik SSO na Wiki.js
0b095d11 config: integração OIDC Authentik na Wiki.js
420c4779 docs: VPN Panamá — configuração segura fora de Five Eyes
63b39650 fix(gpu): add guardrail to pause real_workload if GPU1 > 80% VRAM
0c55c6df docs: incident report 2026-04-11 trading recovery + prevenções
```

### Documentação Criada Nesta Sessão
- `docs/VPN_PANAMA_CONFIG_2026-04-12.md` (4.6 KB) — VPN Panamá justificativa + config
- `docs/OPERATIONAL_STATUS_2026-04-13.md` (este arquivo) — Snapshot operacional

---

## 6. Checklist de Validação

Na data de 2026-04-13, validar:

- [x] VPN conectada Panamá: `nordvpn status | grep Country` → Panama
- [x] Wiki.js running: `docker inspect wikijs → Status: running`
- [x] OIDC Strategy OK: `docker logs wikijs | grep "Authentik SSO" → [ OK ]`
- [x] iVentoy operacional: `iventoy.sh status`
- [x] Git sincronizado: `git status → working tree clean`
- [x] Documentação: VPN_PANAMA_CONFIG_2026-04-12.md presente

---

## 7. Próximos Passos (Planejado)

- [ ] Testar login Wiki.js com credenciais Authentik
- [ ] Validar fluxo OIDC end-to-end
- [ ] Documentar procedimento de onboarding via Authentik
- [ ] Integrar FastAPI com message bus
- [ ] Expandir ISO Fedora SoaS com ferramentas adicionais se necessário

---

## Referências

- **VPN**: [docs/VPN_PANAMA_CONFIG_2026-04-12.md](VPN_PANAMA_CONFIG_2026-04-12.md)
- **Wiki OIDC**: [docker/docker-compose.wikijs.yml](../docker/docker-compose.wikijs.yml)
- **iVentoy**: `/opt/iventoy` (homelab)
- **Git**: [commit 19f885a7](https://github.com/eddiejdi/eddie-auto-dev/commit/19f885a7)

---

**Gerado em**: 2026-04-13
**Ambiente**: Homelab 192.168.15.2 (Ubuntu 24.04 LTS)
**Status Geral**: ✅ Todos os sistemas operacionais
