# 2026-08-02 — Tuya: auth caiu no HA por timer monotônico do self-heal morto após reboot

**Severidade:** alta (0/82 entidades Tuya ativas; integração em `setup_error`)  
**Domínio:** integração Tuya no Home Assistant / systemd / homelab  
**Status:** corrigido e validado (82/82 entidades ativas; timer recuperado)

---

## Sintoma

- Integração Tuya (`edenilson.adm@gmail.com`, entry `01KTFKZCWXYD0TD70516RXDMZG`) em `setup_error` no HA.
- **0/82 entidades** ativas; alertas de auth falhando.
- `tuya-token-renewer` (timer 30 min) só monitorava/alertava e **não** renovava — quem renova é o `tuya-token-selfheal`.
- Log: `Config entry 'edenilson.adm@gmail.com' for tuya integration could not authenticate: Authentication failed`.

---

## Diagnóstico

### Causa raiz

1. O `tuya-token-selfheal.timer` usava **`OnBootSec=2min` + `OnUnitActiveSec=5min`** (agendamento **monotônico**).
2. Após reboot do host em 2026-08-01 17:20, o systemd perdeu o próximo disparo: `NextElapse=infinity` e o timer **nunca mais rodou**.
3. Sem renovação e com token de vida curta (~2h), a sessão Tuya expirou e a integração caiu.
4. Agravante: há **dois timers Tuya** — `tuya-token-renewer` (90min, `OnBootSec`+`OnUnitActiveSec`, **mesmo padrão monotônico**) e `tuya-token-selfheal` (5min). Os dois podiam morrer em reboot; o que de fato morreu foi o self-heal.

### Confirmação

- `systemctl list-timers tuya-token-selfheal` mostrava `NEXT=` vazio e `NextElapse=infinity` após o reboot.
- Tokens (HA `/config/.storage/core.config_entries` e bridge `/var/lib/pandaplus-bridge/tuya_tokens_runtime.json`) ambos expirados.
- Prova de que QR não nasce expirado: token gerado via `tuya_sharing.LoginControl` num QR **ligado**, e o server polling retornava `E0020003 Login failed, please scan and try again!` enquanto aguardava scan.

---

## Mitigação (código)

| Área | Mudança |
|------|---------|
| Timer `tuya-token-selfheal` | `OnCalendar=*:00/5` + `RandomizedDelaySec=10` (relógio real, não monotônico) |
| `Persistent=true` | mantido (pega ciclos perdidos) |
| Redeploys | workflow `deploy-tuya-token-selfheal` cobre `systemd/tuya-token-selfheal.timer` |

Arquivos principais:

- `systemd/tuya-token-selfheal.timer`
- `systemd/tuya-token-renewer.timer` (mesmo padrão; não alterado nesta correção)
- `tools/homelab/tuya_token_selfheal.py`

Feedback: token novo foi injetado na entry do HA (`/config/.storage/core.config_entries`), atualizado também no runtime do bridge (`/var/lib/pandaplus-bridge/tuya_tokens_runtime.json`), e o entry foi recarregado via API. O selfheal assumiu o loop com `hot apply` (serviço `tuya_token_inject.apply`) a partir do runtime novo.

---

## Prova de saúde restaurada

| Campo | Valor |
|-------|--------|
| Reinício runtime | 2026-08-02T12:17:36 (hot apply, `t=1785683709141`) |
| Entidades | **82/82 ativas** (`Heal OK (hot)`) |
| Config entry | `loaded` |
| Próximo disparo timer | `OnCalendar=*:00/5` verificado (NEXT agendado) |

---

## Lições

1. **Timers críticos com `OnBootSec`/`OnUnitActiveSec` morrem em reboot** — para serviços que mantêm sessão (tokens, tunnel, watchdog) a reserva de wall-clock (`OnCalendar`) + `Persistent=true` é mais robusta.
2. **Um mesmo padrão em dois arquivos**: consertar um dos timers sem atacá-lo do outro (renewer D escopia o mesmo bug — falta corrigir).
3. **QR Tuya não "nasce" expirado**: janela de 5 min começa ao gerar; erro E_* no cron/polling é só "aguardando scan".
4. **Reauth manual: token novo na entrada + runtime + reload do entry; o selfheal assume loop após.**

---

## Follow-ups (pendentes)

- [ ] Corrigir `systemd/tuya-token-renewer.timer` (mesmo `OnBootSec`+`OnUnitActiveSec` monotônico) para `OnCalendar=` + `Persistent=true`.
- [ ] Guard anti-regressão: teste CI que **falha** se `tuya-token-selfheal.timer` (e `-renewer`) reintroduzir `OnBootSec`/`OnUnitActiveSec`.
- [ ] Adicionar o guard no workflow `deploy-tuya-token-selfheal.yml` para não regredir em deploy.