# Incidente — Luz Suite intermitente (Tuya cloud)

| Campo | Valor |
|-------|--------|
| Data | 2026-07-27 → 2026-07-28 |
| Severidade | Média (conforto / automação residencial) |
| Área | Suite (Home Assistant + Tuya) |
| Status | **Resolvido** (caminho local) |
| Runbook | [CENA_SUITE_LUZ_TUYA_LOCAL.md](../CENA_SUITE_LUZ_TUYA_LOCAL.md) |

## Sintoma

Botão de luz do controlador de ventilador da Suite ligava a lâmpada real
**só intermitentemente** (ou com latência alta). Cenas do Quarto (fita/spot)
permaneciam estáveis.

## Causa

Automações usavam exclusivamente entidades da integração cloud `tuya`:

- `light.quarto`
- `switch.mi_ni_minitong_duan_qi_1lu_4_interruptor_1`

Sessão Tuya Sharing com refresh morto (**1010**), HA entry em `setup_error`,
0 entidades cloud ativas. Dispositivos já respondiam em LAN via `tuya_local`
(controlador Suite), mas o gatilho da automação não usava essas entidades.

## Correção

1. Reauth QR Smart Life (token Sharing renovado; útil para self-heal de keys).
2. Extração de `local_key` do relé mini (`eb45ba088c576ec101hhlx`).
3. Descoberta IP LAN `192.168.15.186` (probe tinytuya).
4. Entry `tuya_local` **Relé Mini Suite (local)** → `switch.rele_mini_suite_local`.
5. Automações Suite reapontadas para:
   - gatilho: `light.luz_e_ventilador_suite_local`
   - lâmpada: `switch.rele_mini_suite_local`
6. Validação E2E via API HA (on/off sincronizado).

## Prevenção

- Preferir `tuya_local` em novas cenas de iluminação.
- Manter timers de self-heal de token e `local_key`.
- Não depender da entry cloud `tuya` para o caminho feliz das cenas críticas.
