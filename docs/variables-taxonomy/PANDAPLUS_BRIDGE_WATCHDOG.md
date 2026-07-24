# PandaPlus Bridge — Watchdog da sessão Tuya

Serviço: `pandaplus-telegram-bridge.service` — módulo
`tools/pandaplus_bridge/bridge.py`, instalado no homelab (192.168.15.2).

O `_tuya_supervisor_loop` faz retry interno infinito quando a sessão Tuya
falha (ex.: `sign invalid`), o que nunca deixa o processo terminar — logo
`Restart=on-failure` do systemd nunca dispara e o bridge pode ficar preso em
loop por horas sem alertar ninguém (incidentes 2026-07-22 e 2026-07-23,
ver `feedback_tuya_signinvalid_manual_selfheal` e
`project_ha_quarto_scene_tuya_chain_20260722` na memória do agente).

O watchdog abaixo faz o processo encerrar com falha (exit != 0) quando a
sessão Tuya passa tempo demais indisponível, para o systemd reiniciar de
verdade (o que também reexecuta o `ExecStartPre` que recopia
`core.config_entries` fresco do container do HA). Métricas de saúde são
exportadas via textfile collector para permitir alerta no Grafana antes que
o watchdog precise agir.

| Variável | Default | Propósito |
|---|---|---|
| `PANDAPLUS_BRIDGE_TUYA_MAX_UNHEALTHY_SECONDS` | `600` | Tempo máximo (s) que a sessão Tuya pode ficar sem sucesso (connect/session_check) antes do processo encerrar com falha para o systemd reiniciar. |
| `PANDAPLUS_BRIDGE_PROM_FILE` | `/var/lib/prometheus/node-exporter/pandaplus_bridge.prom` | Saída textfile collector com `pandaplus_bridge_tuya_session_healthy`, `pandaplus_bridge_tuya_last_success_timestamp` e `pandaplus_bridge_tuya_consecutive_failures`. |
