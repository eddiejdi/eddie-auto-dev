# Cena Quarto — Ciclo Fita/Spot pelo Interruptor (Tuya Local)

Runbook da automação de cena do quarto e da migração dos três dispositivos
(Interruptor, Spot, Fita) para controle local via `tuya_local`. Estado
validado em 2026-07-21.

## Contexto / pedido original

Objetivo: uma cena onde o clique físico no interruptor de 1 canal do
quarto controla um ciclo de 3 estados:

1. Tudo desligado → clique → liga Fita + Spot
2. Clique → desliga só o Spot (Fita continua ligada)
3. Clique → desliga a Fita também (volta ao estado 1)

O interruptor funciona apenas como gatilho (não tem carga própria na cena;
seu próprio relé é ignorado, só usamos a mudança de estado dele).

## Investigação e causas encontradas

Durante a implementação, a tentativa de reautenticar a integração Tuya
nativa (cloud, `tuya`) no Home Assistant mostrou um aviso de cobrança
(trial do Tuya IoT Cloud Development expirado). A causa raiz real **não
era falta de plano pago**:

1. **`pandaplus-telegram-bridge.service` travado** — o processo Python que
   mantém viva a sessão Tuya gratuita (via conta pessoal Smart Life,
   `tuya_sharing` SDK) e alimenta o self-heal de token
   (`tuya-token-selfheal.timer`) estava travado desde 15:41 sem logar
   nada. Sem token novo para injetar, a sessão do HA expirou e a UI
   empurrou o usuário para o fluxo de reauth, onde a Tuya exibe o aviso de
   cobrança do IoT Core Trial. **Fix**: `systemctl restart
   pandaplus-telegram-bridge.service`. Resolveu a sincronia de 73
   entidades da casa sem precisar reautenticar nem pagar nada.

2. **Comandos de escrita (`switch.turn_on`/`turn_off`) falhando com
   `network error: 2001`** para o Interruptor especificamente, mesmo com
   token válido — permissão de controle dessincronizada entre o device e
   o projeto cloud da integração. Leituras funcionavam, escritas não.

3. **`local_key` desatualizada / dispositivo trocado de `device_id`** —
   ao investigar controle local (Tuya Local, gratuito, sem depender da
   nuvem), descobrimos que os IDs e chaves cacheados estavam obsoletos
   (semanas). Re-parear cada dispositivo no app Smart Life (remover +
   parear do zero com senha Wi-Fi) gera um novo `device_id` e uma
   `local_key` válida.

4. **Vínculo/linkage nativo da Tuya no app** — o Spot tinha uma automação
   de "linkage" configurada direto no Smart Life, fora do Home Assistant,
   causando reconexões e mudanças de estado espúrias (sem contexto de
   automação/usuário no HA). Removida pelo usuário no app.

5. **Rotação periódica de `local_key`** — mesmo sem re-pareamento físico,
   os módulos "mini" Tuya (categoria `tdq`) renegociam a `local_key` a
   cada nova sessão com a nuvem, como recurso de segurança. A integração
   `tuya_local` não acompanha isso sozinha (não suporta reconfigure via
   UI) e a entidade fica `unavailable` até alguém atualizar a chave
   manualmente. **Fix definitivo**: self-heal automático (ver abaixo).

6. **"Bounce" do relé físico do interruptor** — uma única batida física
   gera várias mudanças de estado em menos de 1 segundo (contact bounce
   sem debounce de hardware), fazendo a automação (que disparava em
   qualquer mudança de estado) avançar 2-3 passos do ciclo por um único
   clique real. **Fix**: gatilhos com `for: 00:00:00.5` (só dispara
   quando o novo estado fica estável por meio segundo).

## Dispositivos migrados para Tuya Local

| Papel | Entidade HA | device_id Tuya (na doc, pode rotacionar) | IP local |
|---|---|---|---|
| Interruptor (gatilho) | `switch.luz_interruptor_quarto` | ver `.storage/core.config_entries` | 192.168.15.106 |
| Spot | `switch.spot_quarto` | idem | 192.168.15.149 |
| Fita | `switch.luz_fita_quarto` | idem | 192.168.15.191 |

Perfil de dispositivo usado no `tuya_local`: `somgom_single_switch`
(interruptor) e `aubess_1gang_switch` (spot e fita) — ambos com DPS
`switch_1` como estado principal.

Método de extração de `local_key` sem custo (reaproveitando a sessão já
autenticada do `pandaplus-telegram-bridge`, sem precisar do Tuya IoT
Cloud Platform pago):

```python
from tuya_sharing.customerapi import SharingTokenListener
from tuya_sharing.manager import Manager
import json, uuid

token_info = json.load(open("/var/lib/pandaplus-bridge/tuya_tokens_runtime.json"))

class NoopListener(SharingTokenListener):
    def update_token(self, token_info):
        pass

manager = Manager(
    "HA_3y9q4ak7g4ephrvke",  # TUYA_CLIENT_ID público do HA core
    "Ba0osdh",               # user_code (config entry tuya -> data.user_code)
    "readonly-" + uuid.uuid4().hex[:16],
    "https://apigw.tuyaus.com",
    token_info,
    NoopListener(),
)
manager.update_device_cache()
dev = manager.device_map.get("<device_id>")
print(dev.local_key, dev.ip, dev.online)
```

IP local real: usar `tinytuya.deviceScan()` ou `arp-scan`/`ip neigh` pelo
MAC do dispositivo — o campo `ip` retornado pela API cloud é o IP
**público** da casa (WAN), não o IP local do device.

## Automação da cena

Arquivo: `automations.yaml` do Home Assistant (`homeassistant` container,
`/config/automations.yaml`), id `cena_quarto_ciclo_interruptor`.

```yaml
- id: cena_quarto_ciclo_interruptor
  alias: Cena Quarto — Ciclo Fita/Spot pelo Interruptor
  triggers:
  - platform: state
    entity_id: switch.luz_interruptor_quarto
    to: 'on'
    for: '00:00:00.5'
  - platform: state
    entity_id: switch.luz_interruptor_quarto
    to: 'off'
    for: '00:00:00.5'
  conditions: []
  actions:
  - choose:
    - conditions:
      - condition: state
        entity_id: switch.spot_quarto
        state: 'off'
      - condition: state
        entity_id: switch.luz_fita_quarto
        state: 'off'
      sequence:
      - action: switch.turn_on
        target:
          entity_id: switch.spot_quarto
      - action: switch.turn_on
        target:
          entity_id: switch.luz_fita_quarto
      - delay: 00:00:01
      - action: switch.turn_on
        target:
          entity_id: switch.spot_quarto
      - action: switch.turn_on
        target:
          entity_id: switch.luz_fita_quarto
    - conditions:
      - condition: state
        entity_id: switch.spot_quarto
        state: 'on'
      sequence:
      - action: switch.turn_off
        target:
          entity_id: switch.spot_quarto
      - delay: 00:00:01
      - action: switch.turn_off
        target:
          entity_id: switch.spot_quarto
    default:
    - action: switch.turn_off
      target:
        entity_id: switch.luz_fita_quarto
    - delay: 00:00:01
    - action: switch.turn_off
      target:
        entity_id: switch.luz_fita_quarto
  mode: single
```

Notas de design:

- O estado (fita+spot ligados/desligados) **é a própria memória do
  ciclo** — não precisa de `counter`/`input_number` auxiliar.
- Cada ação de `turn_on`/`turn_off` é enviada **duas vezes** (com 1s de
  delay) para tolerar falhas intermitentes de escrita local observadas
  nos módulos "mini" Tuya — idempotente e inofensivo se a primeira já
  tiver funcionado.
- O gatilho usa `for: 00:00:00.5` em vez de "qualquer mudança de estado"
  para filtrar o bounce do relé físico (ver causa #6 acima).

## Self-heal de `local_key` (tuya-local-key-selfheal)

Novo serviço, mesmo padrão do `tuya-token-selfheal` já existente:

- Script: `tools/homelab/tuya_local_key_selfheal.py` →
  `/usr/local/bin/tuya_local_key_selfheal.py` no homelab
- Systemd: `systemd/tuya-local-key-selfheal.{service,timer}` →
  `/etc/systemd/system/` no homelab, timer a cada 15 min
  (`OnUnitActiveSec=15min`, `OnBootSec=2min`)

Fluxo:

1. Consulta a nuvem Tuya (via sessão do `pandaplus-telegram-bridge`, sem
   custo) para os 3 `device_id` monitorados.
2. Compara com a `local_key` gravada em cada config entry `tuya_local`
   (`core.config_entries` no storage do HA).
3. Se divergente, atualiza o storage e recarrega a entry via
   `POST /api/config/config_entries/entry/{id}/reload`.
4. Aguarda 20s e verifica se a entidade voltou a ficar disponível. Se
   `reload` sozinho não bastar (conexão TCP presa mesmo com a chave
   certa — observado em produção), escala automaticamente para
   `homeassistant.restart` via API — sem precisar reiniciar o container
   Docker.

Mapeamento `entry_id -> device_id` e `entry_id -> entidade de checagem`
está hardcoded no topo do script (`MONITORED` / `CHECK_ENTITY`) — precisa
ser atualizado manualmente se algum dos 3 dispositivos for re-pareado de
novo (o que gera um `device_id` novo).

Requer um token de longa duração do Home Assistant em
`/var/lib/tuya-local-selfheal/ha_token` (permissão 600).

## Validação

Ciclo completo testado fisicamente com sucesso em 2026-07-21 após:
correção do bridge travado, migração dos 3 dispositivos para local,
remoção do linkage nativo da Tuya, self-heal de `local_key` instalado, e
debounce de 500ms no gatilho do interruptor.
