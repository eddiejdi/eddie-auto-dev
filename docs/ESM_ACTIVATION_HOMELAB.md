# Ativação ESM (Ubuntu Pro) — Homelab

**Data:** 2026-02-23  
**Servidor:** `homelab@192.168.15.2`  
**SO:** Ubuntu 24.04.3 LTS  
**Status:** ✅ **ATIVADO** — Ubuntu Pro free personal subscription  
**Conta:** `edenilson.adm@gmail.com`

---

## Resultado da ativação

| Verificação | Resultado |
|---|---|
| Conectividade SSH | ✅ OK |
| Versão do SO | Ubuntu 24.04.3 LTS |
| `pro` CLI instalado | ✅ Sim (nativo no 24.04) |
| `sudo pro attach <token>` | ✅ Sucesso |
| ESM-apps | ✅ **enabled** |
| ESM-infra | ✅ **enabled** |
| Livepatch | ✅ **enabled** |
| Token no Secrets Agent | ✅ Armazenado (`eddie/ubuntu_pro_token`) |
| Subscrição | Ubuntu Pro - free personal subscription |

## Saída do `pro status` (após ativação — 2026-02-23)

```
SERVICE          ENTITLED  STATUS       DESCRIPTION
anbox-cloud      yes       disabled     Scalable Android in the cloud
esm-apps         yes       enabled      Expanded Security Maintenance for Applications
esm-infra        yes       enabled      Expanded Security Maintenance for Infrastructure
fips-updates     yes       disabled     FIPS compliant crypto packages with stable security updates
landscape        yes       disabled     Management and administration tool for Ubuntu
livepatch        yes       enabled      Canonical Livepatch service
realtime-kernel* yes       disabled     Ubuntu kernel with PREEMPT_RT patches integrated
usg              yes       disabled     Security compliance and audit tools

     Account: edenilson.adm@gmail.com
Subscription: Ubuntu Pro - free personal subscription
```

## Detalhes de segurança

- **Token armazenado no Secrets Agent** como `eddie/ubuntu_pro_token` (porta 8088 no homelab)
- Para recuperar: `curl -H "X-API-KEY: <key>" http://localhost:8088/secrets/eddie/ubuntu_pro_token`
- **Nunca** expor o token em logs ou repositório público

## Automação disponível

O script `scripts/enable_esm_homelab.sh` está pronto para uso futuro (re-attach, novos hosts):

```bash
export HOMELAB_HOST=192.168.15.2
export HOMELAB_USER=homelab
export SUBSCRIPTION_SECRET_NAME=eddie/ubuntu_pro_token
./scripts/enable_esm_homelab.sh
```

Documentação complementar: `scripts/README-enable_esm.md`

## Próximos passos

- [x] Criar conta Ubuntu One e obter token
- [x] Executar `sudo pro attach <TOKEN>` no homelab
- [x] Armazenar token no Secrets Agent
- [x] Confirmar `esm-apps: enabled` e `esm-infra: enabled`
- [ ] Rodar `sudo apt update && sudo apt upgrade` para aplicar patches ESM
- [ ] (Opcional) Habilitar serviços adicionais: `landscape`, `usg`, `realtime-kernel`
