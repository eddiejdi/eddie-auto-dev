# Lições Aprendidas — Sessão VPN Panamá + Wiki.js OIDC (2026-04-13)

> Registro de decisões técnicas, problemas encontrados e soluções para futuras referências.

---

## 1. VPN & Jurisdição — Five Eyes vs Fora de Five Eyes

### Problema
Proxy saindo por US (Five Eyes jurisdiction) = possível acesso compulsório NSA/GCHQ aos dados em trânsito.

### Solução
Migrar para Panamá (fora de Five Eyes/14 Eyes/Nine Eyes):
- **Escolha**: NordVPN NORDLYNX (WireGuard) → pa3.nordvpn.com (IP 185.239.149.21)
- **Benefício**: Proteção contra compulsão legal de vigilância
- **Validação**: `nordvpn status | grep Country` → Panama ✅

### Decisão Técnica
- **WireGuard vs OpenVPN**: WireGuard preferível (menor overhead, mais rápido, menor ataque surface)
- **NORDLYNX**: Variante NordVPN de WireGuard com on-demand activation
- **Killswitch**: nftables fwmark `0xe1f1` (mais confiável que iptables)
- **Auto-reconnect**: Habilitado para persistência após reboot

### Lição
✅ **Sempre considerar jurisdição de dados**, não apenas criptografia. Encriptação local não protege contra compulsão legal estrangeira.

---

## 2. Wiki.js OIDC — Do "issuer required" para Strategy OK

### Problema Inicial
Wiki.js não aceitava credenciais de OIDC. Erro: `"OpenIDConnectStrategy requires an issuer option"`.

### Causa
Variável `OIDC_ISSUER` faltava no `docker-compose.wikijs.yml`. Presente:
- OIDC_CLIENT_ID ✓
- OIDC_CLIENT_SECRET ✓
- Endpoints (token, userinfo) ✓

Faltante:
- **OIDC_ISSUER** ✗ (ponto de falha crítico)

### Solução
Adicionar no docker-compose:
```yaml
OIDC_ISSUER: http://authentik-server:9000
```

Restart container → logs mostram `Authentication Strategy Authentik SSO: [ OK ]` ✅

### Lição
✅ **OIDC_ISSUER é obrigatório**, mesmo que nem sempre documentado. Sem ele, o cliente OIDC não consegue validar tokens.

✅ **Ordem de variáveis OIDC importa**:
1. OIDC_ISSUER (validation root)
2. OIDC_CLIENT_ID + OIDC_CLIENT_SECRET (authentication)
3. Endpoints (token, userinfo, authorization) — opcional se issuer resolvê-los

---

## 3. Container Networking — Docker DNS vs IP Hardcoded

### Problema Potencial
Se hardcodearmos IP do container Authentik (ex: 172.18.0.5) em vez de usar hostname.

### Solução
Usar **hostname** `authentik-server:9000`:
- ✅ Docker DNS resolve dinamicamente
- ✅ container pode reiniciar com novo IP
- ✅ funciona em multi-host setup

### Lição
✅ **Sempre use hostnames em docker-compose**, nunca IPs hardcoded internos.

---

## 4. Validação Pós-Deploy — Logs vs Status Code

### Problema
`docker ps` mostra container `running`, mas pode estar em erro interno.

### Solução Adotada
Validação em 3 camadas:
```bash
# 1. Container status
docker inspect wikijs --format "{{.State.Status}}"

# 2. OIDC Strategy logs
docker logs wikijs | grep "Authentication Strategy Authentik SSO"

# 3. API health check (futuro)
curl http://127.0.0.1:3009/api/v1/auth/strategies | jq
```

### Lição
✅ **Status running não = funcional**. Sempre validar logs + health endpoints.

✅ **Grep específico em logs** identifica problemas antes de afetar usuários.

---

## 5. Git Hygiene — Commits Moleculares vs Monolíticos

### Decisão Tomada
3 commits separados:
1. `420c4779`: docs VPN Panamá (documentação)
2. `0b095d11`: config OIDC Docker (infraestrutura)
3. `19f885a7`: fix OIDC_ISSUER (bugfix)

vs. 1 commit monolítico.

### Razão
- ✅ Fácil revert se necessário
- ✅ CI/CD pode rodar em paralelo
- ✅ Code review granular
- ✅ histórico legível

### Lição
✅ **Commits moleculares > monolíticos** para rastreabilidade.

---

## 6. Documentation Consolidation

### Problema
Informação espalhada em:
- Markdown docs
- Docker compose vars
- Logs
- Memória de sessão

### Solução
Criar `OPERATIONAL_STATUS_2026-04-13.md`:
- **Snapshot único** de tudo operacional
- **Tabelas de validação** (status check)
- **Referências cruzadas** para docs específicas
- **Versioned** em Git

### Lição
✅ **Consolidar status operacional periodicamente** (semanal/mensal).

✅ **Máximo 200 linhas** para facilitar leitura rápida.

---

## 7. Deployment Pattern — SSH + SCP + Restart

### Padrão Usado
```bash
scp local_file homelab:/tmp/
ssh homelab 'cp /tmp/file /production/path && docker-compose restart service'
```

### Benefício
- SCP = cópia segura
- /tmp = staging area (fácil revert)
- Restart = validação automática

### Alternativa Não Usada (Melhor para Futuro)
```bash
git pull origin main  # no homelab
```
Conforme: sempre fazer deploy via Git, não via SCP ad-hoc.

### Lição
✅ **Futuro**: Usar GitOps para deploy (git pull em vez de SCP).

---

## 8. Telegram Notifications — Confirmação de Mudanças

### Padrão Usado
Após deploy, enviar mensagem Telegram:
```bash
curl -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d "chat_id=${CHAT_ID}" \
  -d "text=✅ ISO v4 PRONTA!%0A..." > /dev/null
```

### Benefício
- ✅ Feedback imediato ao usuário
- ✅ Timestamp de quando deploy completou
- ✅ Fácil para automação

### Lição
✅ **Telegram como primeiro notificador de mudanças críticas**.

---

## 9. iVentoy PXE Boot — Modo Texto como Default

### Decisão
Fedora SoaS v4 com **modo TEXTO como default** (não GUI):
- Alvo: Netbook/Atom (low spec)
- Economia: RAM + CPU
- Fallback: `startx` para GUI se necessário

### Validação
Confirmação enviada via Telegram: "✅ ISO v4 PRONTA!"

### Lição
✅ **Adaptar defaults ao hardware target** (GUI vs TEXTO).

---

## 10. Working Tree Cleanup — Sempre Finalizar com Git Clean

### Regra Seguida
Após todo trabalho: `git status` deve estar limpo (sem untracked files).

```bash
# Verificar
git status

# Limpar se necessário
git restore .
git clean -fd
```

### Benefício
- ✅ Repositório limpo para próximos agentes
- ✅ Sem artefatos acidentais commitados
- ✅ Difícil misturar trabalho antigo com novo

### Lição
✅ **Regra obrigatória**: `working tree clean` antes de signal de completude.

---

## 11. OIDC Strategy Fallback — Local Auth Still Available

### Decisão
Manter **ambas** estratégias ativas:
- Authentik SSO (OIDC) — PRIMARY
- Local Auth — FALLBACK

```logs
✅ Strategy Local: [ OK ]
✅ Strategy Authentik SSO: [ OK ]
```

### Razão
- Recovery se Authentik cair
- Onboarding admin (criar primeiro usuário Authentik)
- Teste sem dependência externa

### Lição
✅ **Sempre deixar fallback local** em sistemas SSO.

---

## 12. Performance — NordVPN NORDLYNX Latência

### Observação
WireGuard (NORDLYNX) mais rápido que OpenVPN:
- Overhead menor
- Menos context switches
- Melhor para proxy

### Validação Futura
```bash
# Comparar latência
ping -c 4 8.8.8.8  # via NordVPN
curl -w '%{time_total}\n' -o /dev/null https://api.myip.com
```

### Lição
✅ **WireGuard preferível para latência crítica** (trading, APIs).

---

## 13. Multi-Container Orchestration — Serial vs Parallel Restart

### Decisão
Restart **serial** (um por vez):
```bash
docker-compose up -d authentik
sleep 5
docker-compose up -d wikijs
```

vs. parallel (`docker-compose up -d`).

### Razão
- Evitar race condition (wikijs tenta conectar antes de Authentik pronto)
- Logs mais legíveis
- Recovery fácil se um falhar

### Lição
✅ **Para dependências críticas, restart serial com delay**.

---

## Referências

| Documento | Propósito |
|-----------|-----------|
| `docs/VPN_PANAMA_CONFIG_2026-04-12.md` | Detalhes técnicos VPN |
| `docs/OPERATIONAL_STATUS_2026-04-13.md` | Snapshot operacional |
| `docker/docker-compose.wikijs.yml` | Configuração OIDC |
| `.github/copilot-instructions.md` | Padrões globais |
| Este arquivo | Lições aprendidas |

---

**Aplicável a**: Futuras migrações VPN, integrações OIDC, deployments container
**Responsável**: Agent dev_local
**Data**: 2026-04-13
