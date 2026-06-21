# Akash provider audit/certification request

## Status rapido
- Provider owner: `akash1m6usr35wjsdads7axwemwzp3gpjwpz2grhkrnf`
- Host URI: `https://provider.provider.189.27.196.49.nip.io:8443`
- Bids open: `0`
- Leases active: `0`
- Signed_by dominante no mercado aberto: `akash1365yvmc4s7awdyj3n2sav7xfx76adc6dnmlx63` (98 ocorrencias no snapshot)
- Self-sign audit txhash: `11423AB166065E54C592CDE1E2A5914282A038AD708D4930BCFD644795F1711A`

## Comentario pronto (PT-BR)
```md
Ola equipe,

Estou solicitando onboarding de auditoria/certificacao para meu provider Akash, pois o mercado aberto atual exige `requirements.signed_by` e meu provider permanece sem bids.

## Provider
- Owner: `akash1m6usr35wjsdads7axwemwzp3gpjwpz2grhkrnf`
- Host URI: `https://provider.provider.189.27.196.49.nip.io:8443`
- Atributos: `region=br-sudeste`, `host=homelab`, `tier=community`, `console/trials=true`, `vendor/nvidia/model/rtx2060=true`, `vendor/nvidia/model/gtx1050=true`

## Estado atual
- `bids open = 0`
- `leases active = 0`
- Signed_by dominante no mercado aberto (snapshot): `akash1365yvmc4s7awdyj3n2sav7xfx76adc6dnmlx63` (98 ocorrencias)

## Evidencia de readiness
- Self-sign no modulo audit realizado com sucesso:
  - Tx hash: `11423AB166065E54C592CDE1E2A5914282A038AD708D4930BCFD644795F1711A`

Peço orientacao/procedimento para vinculacao com auditor aceito no mercado e liberacao de bids para ordens com `signed_by`.

Obrigado.
```

## Comment ready (EN)
```md
Hello team,

I am requesting Akash provider audit/certification onboarding. The current open market mostly requires `requirements.signed_by`, and my provider remains with zero bids.

## Provider
- Owner: `akash1m6usr35wjsdads7axwemwzp3gpjwpz2grhkrnf`
- Host URI: `https://provider.provider.189.27.196.49.nip.io:8443`
- Attributes: `region=br-sudeste`, `host=homelab`, `tier=community`, `console/trials=true`, `vendor/nvidia/model/rtx2060=true`, `vendor/nvidia/model/gtx1050=true`

## Current state
- `open bids = 0`
- `active leases = 0`
- Dominant signed_by in open orders snapshot: `akash1365yvmc4s7awdyj3n2sav7xfx76adc6dnmlx63` (98 occurrences)

## Readiness evidence
- Self-sign on audit module completed successfully:
  - Tx hash: `11423AB166065E54C592CDE1E2A5914282A038AD708D4930BCFD644795F1711A`

Please share the exact onboarding flow to link with an accepted external auditor and unlock bidding for signed_by orders.

Thanks.
```

## Comandos de revalidacao (apos resposta do auditor)
```bash
KCFG=/mnt/disk4/akash-k3s/server/cred/admin.kubeconfig
NS=akash-services
POD=akash-provider-0
ADDR=akash1m6usr35wjsdads7axwemwzp3gpjwpz2grhkrnf
RPC=https://akash-rpc.publicnode.com:443

sudo kubectl --kubeconfig="$KCFG" -n "$NS" exec "$POD" -c provider -- \
  provider-services query market bid list --state open --provider "$ADDR" --node "$RPC" -o text

sudo kubectl --kubeconfig="$KCFG" -n "$NS" exec "$POD" -c provider -- \
  provider-services query market lease list --state active --provider "$ADDR" --node "$RPC" -o text
```
