# Akash Provider Audit Playbook - 2026-05-30

## Objetivo
Destravar bids/leases no provider Akash quando o bloqueio principal e requisito `signed_by` em ordens abertas.

## Resumo executivo
- Provider on-chain esta configurado e saudavel.
- Inventory de GPU esta exposto no cluster (`gpu=2`).
- Provider faz self-sign no modulo audit com sucesso.
- Mesmo assim, bids permanecem em zero porque quase todas as ordens abertas exigem auditor externo especifico via `signed_by`.

## Estado atual validado
Data da validacao: 2026-05-30

### Provider on-chain
- owner: `akash1m6usr35wjsdads7axwemwzp3gpjwpz2grhkrnf`
- host_uri: `https://provider.provider.189.27.196.49.nip.io:8443`
- attributes:
  - `region=br-sudeste`
  - `host=homelab`
  - `tier=community`
  - `console/trials=true`
  - `vendor/nvidia/model/rtx2060=true`
  - `vendor/nvidia/model/gtx1050=true`

### Audit on-chain (self-sign)
- owner: `akash1m6usr35wjsdads7axwemwzp3gpjwpz2grhkrnf`
- auditor: `akash1m6usr35wjsdads7axwemwzp3gpjwpz2grhkrnf`
- tx hash da assinatura de atributos audit:
  - `11423AB166065E54C592CDE1E2A5914282A038AD708D4930BCFD644795F1711A`

### Mercado aberto (snapshot)
- bids open: `0`
- leases active: `0`
- signed_by dominante nas ordens abertas:
  - `98x akash1365yvmc4s7awdyj3n2sav7xfx76adc6dnmlx63`

## Diagnostico
O bloqueio principal nao e mais rede, host_uri, TLS ou GPU baseline.
O bloqueio atual e compatibilidade com politica de auditoria do mercado:

1. A maioria das ordens `akash` exige `requirements.signed_by.all_of`.
2. O provider tem self-sign no modulo audit, mas isso nao satisfaz o auditor externo exigido.
3. Sem vinculo/assinatura por auditor aceito, o bidengine continua declinando ordens com `incompatible attributes for resources requirements`.

## Evidencias tecnicas (comandos)
Assumindo acesso no host homelab e k3s kubeconfig:

```bash
KCFG=/mnt/disk4/akash-k3s/server/cred/admin.kubeconfig
NS=akash-services
POD=akash-provider-0
ADDR=akash1m6usr35wjsdads7axwemwzp3gpjwpz2grhkrnf
RPC=https://akash-rpc.publicnode.com:443

# Provider atual
sudo kubectl --kubeconfig="$KCFG" -n "$NS" exec "$POD" -c provider -- \
  provider-services query provider get "$ADDR" --node "$RPC" -o json

# Audit self-sign atual
sudo kubectl --kubeconfig="$KCFG" -n "$NS" exec "$POD" -c provider -- \
  provider-services query audit get "$ADDR" "$ADDR" --node "$RPC" -o json

# Bids e leases
sudo kubectl --kubeconfig="$KCFG" -n "$NS" exec "$POD" -c provider -- \
  provider-services query market bid list --state open --provider "$ADDR" --node "$RPC" -o text

sudo kubectl --kubeconfig="$KCFG" -n "$NS" exec "$POD" -c provider -- \
  provider-services query market lease list --state active --provider "$ADDR" --node "$RPC" -o text

# Signed_by mais frequente no mercado aberto
sudo kubectl --kubeconfig="$KCFG" -n "$NS" exec "$POD" -c provider -- sh -lc '
provider-services query market order list --state open --node "$0" -o json | \
  jq -r ".orders[]?.spec.requirements.signed_by.all_of[]?" | \
  sort | uniq -c | sort -nr | head -10
' "$RPC"
```

## Checklist de desbloqueio
- [x] Host URI publico correto no provider
- [x] Endpoint TLS 8443 funcional
- [x] GPU visivel no k8s (`nvidia.com/gpu`)
- [x] Atributos essenciais publicados
- [x] Self-sign em `tx audit attr create`
- [ ] Vinculo/assinatura por auditor externo aceito nas ordens `signed_by`
- [ ] Revalidar bids e leases apos onboarding com auditor

## Texto pronto para issue (PT-BR)
Titulo sugerido:
`Request for Akash provider audit/certification to satisfy signed_by market orders`

Corpo sugerido:

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

## Text ready for issue comment (EN)
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

## Proximo passo operacional
Assim que houver retorno do auditor/equipe:
1. Executar o procedimento indicado por eles para vinculacao do auditor externo.
2. Revalidar `bid list` e `lease list` por 30-60 minutos.
3. Se abrir lease, monitorar saldo AKT e revalidar sweep diario.
