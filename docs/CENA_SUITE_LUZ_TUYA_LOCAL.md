# Cena Suite — Botão do ventilador ↔ Lâmpada (Tuya Local)

Runbook da automação que espelha o **botão de lâmpada embutido no controlador
do ventilador da Suite** na **lâmpada real** (relé mini 1 canal), e o inverso.
Estado validado em **2026-07-27 / 2026-07-28**.

Documentos relacionados:

- [CENA_QUARTO_TUYA_LOCAL.md](CENA_QUARTO_TUYA_LOCAL.md) — ciclo fita/spot (também local)
- [SMARTLIFE_TUYA_INTEGRATION.md](SMARTLIFE_TUYA_INTEGRATION.md) — integração Smart Life/Tuya
- Self-heal de token: `tools/homelab/tuya_token_selfheal.py`
- Self-heal de `local_key`: `tools/homelab/tuya_local_key_selfheal.py`
- Reauth QR: `tools/homelab/tuya_reauth_via_authentik.py`

---

## Comportamento da cena (lógica de negócio)

Mesma lógica desde a criação (pedido do usuário: vincular botão do ventilador à lâmpada):

1. Usuário aciona o **botão de luz** no controle do ventilador da Suite  
   → a **lâmpada real** (relé mini) liga/desliga junto.
2. Se a lâmpada real muda de estado por outro meio  
   → o botão/indicador do controlador é espelhado (quando a entidade estiver disponível).

**Não alterar o comportamento** sem pedido explícito; só o *transporte* (cloud → LAN)
foi trocado para estabilidade.

---

## Sintoma (jul/2026)

- Botão da luz da Suite **às vezes funciona, às vezes não** (latência alta ou falha total).
- Cena do Quarto / Julia (ciclo fita/spot) **funcionava** de forma estável.

---

## Causa raiz

### Caminho antigo (quebrado / intermitente)

```
Botão físico do ventilador
    → entidade cloud light.quarto  (integração tuya)
    → automação HA
    → switch.mi_ni_minitong_duan_qi_1lu_4_interruptor_1  (cloud, Relé Mini Suite)
```

| Entidade (cloud) | Papel | Problema |
|---|---|---|
| `light.quarto` | Botão de lâmpada do ventilador | Frequentemente `unavailable` |
| `switch.mi_ni_minitong_duan_qi_1lu_4_interruptor_1` | Lâmpada real (relé mini) | Frequentemente `unavailable` |
| `fan.quarto` | Ventilador (cloud) | Idem |

**Fatores técnicos:**

1. **Sessão Tuya Sharing expirada** — refresh token morto com erro **1010** (`token is expired`).
2. Integração HA `tuya` em **`setup_error`**: *Authentication failed. Please re-authenticate*.
3. **0/N entidades cloud ativas** enquanto o bridge e o self-heal falhavam em loop (`sign invalid`).
4. Automações escutavam **só** entidades cloud; o dispositivo já falava LAN via `tuya_local`,
   mas o HA não usava esse caminho no gatilho → “hora sim, hora não”.
5. Quarto Julia/ciclo fita-spot já estava em **`tuya_local`** (LAN) → por isso não sofria o mesmo.

### Caminho atual (estável, LAN)

```
Botão físico do ventilador
    → light.luz_e_ventilador_suite_local   (tuya_local, 192.168.15.175)
    → automação HA
    → switch.rele_mini_suite_local         (tuya_local, 192.168.15.186)
```

Cloud permanece como *fallback opcional* nas actions (`continue_on_error: true`),
mas **não é necessário** para a cena funcionar.

---

## Dispositivos e entidades

### Tuya Local (produção da cena)

| Papel | Entidade HA | device_id | IP | Perfil `tuya_local` | Protocolo |
|---|---|---|---|---|---|
| Controlador vent. + botão luz | `light.luz_e_ventilador_suite_local` | `ebf17e68a06f66afef0l8i` | 192.168.15.175 | `dometek_ceiling_fan` | 3.5 |
| Ventilador (local) | `fan.luz_e_ventilador_suite_local_fan` | (mesmo device) | 192.168.15.175 | idem | 3.5 |
| Lâmpada real (relé mini) | `switch.rele_mini_suite_local` | `eb45ba088c576ec101hhlx` | 192.168.15.186 | `aubess_1gang_switch` | 3.4 |

Config entries em  
`/home/homelab/homeassistant/config/.storage/core.config_entries`  
(domain `tuya_local`):

| Title | entry_id (prefixo) |
|---|---|
| Luz e Ventilador Suite (local) | `017X07J7…` |
| Relé Mini Suite (local) | `014B6A14…` (adicionada 2026-07-27) |

**Não documentar `local_key` em texto claro** (roda e self-heal). Chaves ficam só no storage do HA.

### Cloud (legado / fallback — frequentemente offline)

| Entidade | Device registry | Uso |
|---|---|---|
| `light.quarto` | Luz e Ventilador Suite | Fallback no trigger/action |
| `switch.mi_ni_minitong_duan_qi_1lu_4_interruptor_1` | Relé Mini Suite | Fallback no action |
| `fan.quarto` | Luz e Ventilador Suite | Não usa na cena de luz |

### Outros locais da Suite / “Quarto” (contexto)

| Papel | Entidade | IP |
|---|---|---|
| Interruptor principal (cena fita/spot) | `switch.luz_interruptor_quarto` | 192.168.15.106 |
| Fita LED Suite | `switch.luz_fita_quarto` | 192.168.15.191 |
| Spot | `switch.spot_quarto` | 192.168.15.149 |
| Closet | `switch.luz_closet_local` | 192.168.15.138 |

### Desacoplamento Closet ↔ Relé Mini Suite (2026-08-16)

**Motivo:** O usuário solicitou que somente o interruptor da suite controlasse o relé mini, removendo o vínculo com o closet.

**Automações desativadas** (`initial_state: false`):

| ID | Alias | Direção |
|---|---|---|
| `sync_closet_to_relay_on` | Sinc Luz Closet → Relé Mini Suite (Ligar) | Closet → Relay |
| `sync_closet_to_relay_off` | Sinc Luz Closet → Relé Mini Suite (Desligar) | Closet → Relay |
| `sync_relay_to_closet_on` | Sinc Relé Mini Suite → Luz Closet (Ligar) | Relay → Closet |
| `sync_relay_to_closet_off` | Sinc Relé Mini Suite → Luz Closet (Desligar) | Relay → Closet |

**Resultado:**

```
ANTES:
switch.luz_closet_local ←→ switch.rele_mini_suite_local ←→ light.luz_e_ventilador_suite_local

DEPOIS:
switch.luz_closet_local (isolado)
switch.rele_mini_suite_local ←→ light.luz_e_ventilador_suite_local (somente interruptor da suite controla)
```

**Procedimento:**
1. Backup: `automations.yaml.bak.20260816*`
2. Adicionado `initial_state: false` nas 4 automações
3. `docker restart homeassistant`

**Para reativar:** Remover `initial_state: false` ou definir como `true` nas 4 automações e reiniciar HA.

---

## Automações (HA)

Arquivo: `/home/homelab/homeassistant/config/automations.yaml`  
(container: `/config/automations.yaml`).

### 1. `suite_botao_ventilador_aciona_lampada`

- **Alias:** Suite — Botão do ventilador aciona a lâmpada  
- **Trigger:** state de  
  - `light.luz_e_ventilador_suite_local` (preferido)  
  - `light.quarto` (fallback cloud)  
- **Condição:** transição real `on`↔`off`; ignora `unavailable`/`unknown`  
- **Action:** `switch.turn_on` / `turn_off` em  
  - `switch.rele_mini_suite_local`  
  - `switch.mi_ni_…_4_interruptor_1` (fallback, `continue_on_error: true`)

### 2. `suite_lampada_sincroniza_botao_ventilador`

- **Alias:** Suite — Lâmpada sincroniza o botão do ventilador  
- **Trigger:** state de  
  - `switch.rele_mini_suite_local`  
  - `switch.mi_ni_…_4` (fallback)  
- **Action:** espelha em  
  - `light.luz_e_ventilador_suite_local`  
  - `light.quarto` (fallback)

Reload após edição:

```bash
# via API (token long-lived do HA)
curl -X POST -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" -d '{}' \
  http://127.0.0.1:8123/api/services/automation/reload
```

---

## O que foi feito em 2026-07-27/28 (cronologia)

1. **Diagnóstico** — Julia/Quarto em LAN; Suite ainda em cloud; token 1010; `setup_error`.
2. **Reauth QR** — gerados em `artifacts/tuya_reauth_qr_*.png` / `tuya_reauth_qr_LATEST.png`;
   usuário escaneou no Smart Life; `login_result` OK; token gravado em:
   - `.storage/core.config_entries` (entry domain `tuya`)
   - `/var/lib/pandaplus-bridge/tuya_tokens_runtime.json`
3. **Limitação** — token **válido no SDK** `tuya_sharing` (Manager listou 29 devices),
   mas a integração nativa `tuya` do HA **continuou em `setup_error`** em vários reloads.
   Por isso a cena foi estabilizada em **local**, não em cloud.
4. **Relé mini local**
   - `local_key` obtida via Sharing API com o token fresco
   - IP descoberto por probe tinytuya na LAN: **192.168.15.186**
   - Config entry `tuya_local` título **Relé Mini Suite (local)**
   - Entidade: `switch.rele_mini_suite_local`
5. **Automações** reescritas para preferir entidades locais (mesma lógica).
6. **Teste E2E (API HA)**
   - `switch.rele_mini_suite_local` on/off OK  
   - `light.luz_e_ventilador_suite_local` on → mini on  
   - light off → mini off  
   - `last_triggered` da automação atualizado  

Backups gerados no host (não versionar secrets):

- `core.config_entries.tuya-reauth-*.bak`
- `core.config_entries.pre-mini-local-*.bak`
- `automations.yaml.bak-suite-local*`

---

## Inventário `tuya_local` no homelab (referência)

| Title | device_id | host | type | proto |
|---|---|---|---|---|
| Smart IR NovaDigital | ebf9cf282b8d78ddd8t7ql | 192.168.15.135 | basic_ir_remote | 3.5 |
| Luz Interruptor Quarto | ebd0a5540ab0b8225ddwug | 192.168.15.106 | somgom_single_switch | 3.4 |
| Luz Fita Quarto | eb75dc2918c27818b9zcue | 192.168.15.191 | aubess_1gang_switch | 3.4 |
| Spot Quarto | eb48a5c11d046286292ask | 192.168.15.149 | aubess_1gang_switch | 3.4 |
| Ventilador e Luz Escritório (local) | ebbc9f4aaf16cce3a4wj26 | 192.168.15.105 | novadigital_ceiling_fanlight | 3.5 |
| Tomada Escritório Monitor (local) | eb68c44516c0e08e5777cw | 192.168.15.126 | quad_powerstrip_usb | 3.5 |
| Luz e Ventilador Suite (local) | ebf17e68a06f66afef0l8i | 192.168.15.175 | dometek_ceiling_fan | 3.5 |
| Luz Closet (local) | eb23d2bba4414e469eyj8e | 192.168.15.138 | somgom_single_switch | 3.4 |
| **Relé Mini Suite (local)** | **eb45ba088c576ec101hhlx** | **192.168.15.186** | **aubess_1gang_switch** | **3.4** |

---

## Operação / recuperação

### Validar cena Suite (rápido)

```bash
HA=http://127.0.0.1:8123
# estados
for e in light.luz_e_ventilador_suite_local switch.rele_mini_suite_local \
         automation.suite_botao_do_ventilador_aciona_a_lampada; do
  curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA/api/states/$e" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['entity_id'], d['state'])"
done

# toggle controlado (API)
curl -s -X POST -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_id":"light.luz_e_ventilador_suite_local"}' \
  $HA/api/services/light/turn_on
# esperar ~2s e checar switch.rele_mini_suite_local == on
```

Teste físico: botão de luz no controle do ventilador da Suite → lâmpada do cômodo.

### Se `switch.rele_mini_suite_local` ficar `unavailable`

1. Confirmar host alcançável: `ping 192.168.15.186`
2. Rodar self-heal de local_key (minis rotacionam chave):
   ```bash
   systemctl start tuya-local-key-selfheal.service
   journalctl -u tuya-local-key-selfheal.service -n 50 --no-pager
   ```
3. Se o token Sharing estiver morto (1010), **reauth QR** (abaixo) e reexecutar self-heal.
4. Probe manual (no container HA):
   ```python
   import tinytuya
   # device_id, host, local_key do storage; version 3.4
   d = tinytuya.Device(device_id, host, local_key)
   d.set_version(3.4)
   print(d.status())  # espera dps com '1'
   ```

### Reauth QR (sessão Sharing / cloud)

Quando `tuya-token-selfheal` logar `1010 token is expired` e o bridge cair em `sign invalid`:

1. Gerar QR (HA container + `LoginControl().qr_code`) — payload  
   `tuyaSmart--qrLogin?token=<qrcode>`  
   Artefatos: `artifacts/tuya_reauth_qr_LATEST.png`
2. Usuário escaneia no **Smart Life** (conta da casa) → Meu → Scan.
3. Poll: `LoginControl().login_result(token, client_id, user_code)`.
4. Gravar `token_info` + `terminal_id` + `endpoint` + `user_code` na config entry `tuya`.
5. Espelhar `token_info` em `/var/lib/pandaplus-bridge/tuya_tokens_runtime.json`.
6. `docker restart homeassistant` e `systemctl restart pandaplus-telegram-bridge`.
7. Validar SDK:
   ```python
   # Manager(...).update_device_cache() deve listar dezenas de devices
   ```
8. Se a UI HA ainda mostrar `setup_error` na entry cloud, **não bloqueia** as cenas já em `tuya_local`.  
   A cloud continua útil para self-heal de `local_key` e dispositivos ainda não migrados.

Script de apoio: `tools/homelab/tuya_reauth_via_authentik.py`  
Client ID público HA Tuya: `HA_3y9q4ak7g4ephrvke`  
User code atual da conta (não secret de sessão): `Ba0osdh` (pode mudar se recriar pairing).

Incidente completo (timers failed + 1010 + QR + `docker_restart`):  
[docs/INCIDENTS/2026-08-05_TUYA_TIMERS_FAILED_REFRESH_1010_AND_REAUTH.md](INCIDENTS/2026-08-05_TUYA_TIMERS_FAILED_REFRESH_1010_AND_REAUTH.md).

### Serviços systemd relevantes

| Unit | Função |
|---|---|
| `tuya-token-selfheal.timer` | Injeta/renova token Sharing no HA |
| `tuya-local-key-selfheal.timer` | Atualiza `local_key` das entries `tuya_local` |
| `ha-tuya-mq-watchdog.timer` | Watchdog MQTT/sessão |
| `pandaplus-telegram-bridge.service` | Mantém sessão / eventos Tuya (PandaPlus) |
| `ha-grafana-sync.service` | Sync HA → PG (também expõe `HA_TOKEN` no Environment) |

---

## Lições aprendidas

1. **Cenas críticas devem ser 100% `tuya_local` (LAN).** Cloud Tuya Sharing é frágil (token 2h, 1010, sign invalid).
2. **“Hora funciona hora não”** quase sempre = gatilho/action em entidade cloud `unavailable` enquanto o device local está online.
3. **Token fresco no storage ≠ integração HA `tuya` loaded.** Validar com SDK `Manager.update_device_cache()` e com estados de entidades, não só com o arquivo de token.
4. **Minis (`tdq` / 1ch)** rotacionam `local_key`; self-heal é obrigatório após reauth.
5. **Descoberta de IP:** `device.ip` da API cloud costuma ser **WAN**; usar `tinytuya.deviceScan()` + probe com `local_key` na subnet `192.168.15.0/24`.
6. **Não commitar** tokens, `local_key`, QR de sessão nem dumps de `core.config_entries` com secrets.

---

## Checklist de saúde (Suite luz)

- [ ] `light.luz_e_ventilador_suite_local` ∈ {on, off} (não unavailable)
- [ ] `switch.rele_mini_suite_local` ∈ {on, off}
- [ ] Automação `suite_botao_ventilador_aciona_lampada` = on
- [ ] Toggle light local → mini acompanha em &lt; 2s
- [ ] Botão físico do ventilador → mesma reação
- [ ] (Opcional) token Sharing remaining &gt; 30 min para self-heal de keys
- [ ] Closet `switch.luz_closet_local` **desacoplado** do relé mini (4 automações com `initial_state: false`)

---

## Contato operacional

- HA: `http://192.168.15.2:8123` (LAN), container `homeassistant`, config em  
  `/home/homelab/homeassistant/config/`
- Área HA: `suite` (Suite)
- Conta Smart Life usada no pairing: a mesma da entry `tuya` no HA (título = e-mail da conta)
