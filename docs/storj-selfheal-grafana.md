Documentação — Storj Self-Heal Fix & Grafana Self-Heal Monitor

Data: 2026-04-29

Resumo executivo
- Ambiente: Homelab 192.168.15.2 (usuário homelab, chave ~/.ssh/homelab_key).
- Objetivo: resolver loop de self-heal do Storj causado por probe TCP em topologia macvlan e criar um dashboard de self-heal no Grafana.

1) Situação inicial
- O exporter `storj_selfheal_exporter.py` declarou muitas falhas consecutivas (3057+) porque a checagem TCP (socket.create_connection) sempre falhava na topologia macvlan (SYN não recebia resposta localmente). Apesar disso os satélites confirmavam QUIC operando (quicStatus: OK).
- Métricas Prometheus (exemplo atual):
  - storj_node_health{name="storagenode"}
  - storj_node_api_up{name="storagenode"}
  - storj_node_quic_ok{name="storagenode"}
  - storj_node_port_open{name="storagenode"}
  - storj_node_address_drift{name="storagenode"}
  - storj_node_api_external_address_ok{name="storagenode"}
  - storj_node_last_ping_age_seconds{name="storagenode"}
  - storj_node_consecutive_failures{name="storagenode"}

2) Mudanças realizadas (resumo)
- storj_selfheal_exporter.py (repo: /home/homelab/myClaude/grafana/exporters/)
  - Commit referenciado: ae7625fc (patch aplicado em 2026-04-29).
  - Alteração principal: introdução de probe_port_accessible(node_quic_ok, last_ping_age, host, port) — se quicStatus == OK e last_ping_age <= 600s considera porta acessível (usa sinal dos satélites), evitando o falso negativo do probe TCP em macvlan. Fallback para probe TCP apenas quando API indisponível ou quic=Misconfigured.
  - Loop de checagem passou a chamar probe_port_accessible() em vez do probe_tcp_port() direto.

- storj-port-forward.service (systemd)
  - Arquivo: /etc/systemd/system/storj-port-forward.service (host).
  - Mudança: inserido MASQUERADE nas linhas ExecStart e ExecStop para garantir retorno de pacotes quando necessário. Exemplo de regra adicionada:

    iptables -t nat -C POSTROUTING -o storj-host0 -j MASQUERADE -m comment --comment storj-macvlan-forward 2>/dev/null || iptables -t nat -A POSTROUTING -o storj-host0 -j MASQUERADE -m comment --comment storj-macvlan-forward

  - E a regra de remoção equivalente no ExecStop (uso de -D POSTROUTING ... || true).

- Grafana provisioning / dashboard
  - Arquivo criado: /home/homelab/monitoring/grafana/provisioning/dashboards/storj-selfheal-monitor.json
  - UID: storj-selfheal-v1
  - Conteúdo: 14 panels (estatísticas de saúde, QUIC, porta, address drift, falhas consecutivas, last ping age, timeseries históricos de saúde/falhas/drift).
  - Prometheus datasource (provisionado): nome Prometheus, uid dfc0w4yioe4u8e, URL http://prometheus:9090 (ver /home/homelab/monitoring/grafana/provisioning/datasources/datasources.yml).
  - Mapeamento host→container: /home/homelab/monitoring/grafana/provisioning → container /etc/grafana/provisioning (detectado via docker inspect grafana).

3) Problema de provisioning encontrado e corrigido
- Erro: logs do Grafana mostraram "the same UID is used more than once" para btc-trading-monitor. Havia dois arquivos com o mesmo uid (cópias idênticas). Isso fazia com que o provisioner ficasse com permissões restritas e não salvasse dashboards novos.
- Ação: renomeado o arquivo duplicado btc_trading_monitor.json para btc_trading_monitor.json.bak_duplicate_20260429 (backup), removendo o conflito. Em seguida foi enviado SIGHUP para o container Grafana para forçar reload.
- Após a correção, o dashboard storj-selfheal-v1 foi carregado com sucesso e verificado via API local.

4) Comandos-chave e validação (executados durante o processo)
- Ver métricas do exporter (host):

```bash
curl -sf http://localhost:9212/metrics | grep -v '^#' | grep '^storj_'
```

- Ver status API do exporter (host):

```bash
curl -sf http://localhost:9213/status | jq .
```

- Visualizar dashboards provisionados no host (pasta):

```bash
ls -lh /home/homelab/monitoring/grafana/provisioning/dashboards/
```

- Forçar reload do Grafana (host):

```bash
docker kill --signal=SIGHUP grafana
```

- Validar via API Grafana (host, porta mapeada para 3002):

```bash
curl -sf http://127.0.0.1:3002/api/dashboards/uid/storj-selfheal-v1 | jq .
```

- Remover duplicata (exemplo usado):

```bash
mv /home/homelab/monitoring/grafana/provisioning/dashboards/btc_trading_monitor.json \
   /home/homelab/monitoring/grafana/provisioning/dashboards/btc_trading_monitor.json.bak_duplicate_20260429
```

5) Como reverter (passos rápidos)
- Reverter dashboard criado:

```bash
ssh -i ~/.ssh/homelab_key homelab@192.168.15.2 \
  'rm -f /home/homelab/monitoring/grafana/provisioning/dashboards/storj-selfheal-monitor.json && \
   docker kill --signal=SIGHUP grafana'
```

- Reverter MASQUERADE no storj-port-forward.service: restaurar a cópia original do serviço (se houver backup) ou remover as linhas iptables adicionadas e systemctl daemon-reload:

```bash
sudo sed -n '1,200p' /etc/systemd/system/storj-port-forward.service
# editar para remover as instruções iptables adicionadas
sudo systemctl daemon-reload
sudo systemctl restart storj-port-forward.service
```

- Reverter alteração no exporter (git):

```bash
ssh -i ~/.ssh/homelab_key homelab@192.168.15.2
cd /home/homelab/myClaude
git show --name-only ae7625fc  # inspeciona commit aplicado
git revert ae7625fc           # ou git checkout <arquivo>@{1}
```

6) Logs e evidências (trechos relevantes)
- Grafana provisioning detectou o problema de UID duplicado:

```
logger=provisioning.dashboard t=... level=warn msg="the same UID is used more than once" orgId=1 uid=btc-trading-monitor
logger=provisioning.dashboard t=... level=warn msg="dashboards provisioning provider has no database write permissions because of duplicates"
```

- Após correção e SIGHUP, dashboard storj-selfheal-v1 respondeu via API local (porta mapeada 3002).

7) Localizações importantes
- Exporter (host): /home/homelab/myClaude/grafana/exporters/storj_selfheal_exporter.py (commit ae7625fc)
- Service (host): /etc/systemd/system/storj-port-forward.service
- Dashboards (host provision dir): /home/homelab/monitoring/grafana/provisioning/dashboards/
- Dashboard criado: /home/homelab/monitoring/grafana/provisioning/dashboards/storj-selfheal-monitor.json (uid storj-selfheal-v1)
- Grafana container provisioning path: /etc/grafana/provisioning (container)
- Grafana data volume: /mnt/disk1/docker/volumes/grafana_data/_data → container /var/lib/grafana (informação do docker inspect).

8) Recomendações / próximos passos
- Adicionar testes unitários/mocks para storj_selfheal_exporter.py (cobertura mínima sugerida para código novo).
- Adicionar um pequeno script de deploy para dashboards que valide unicidade de uid antes de copiar para a pasta de provisioning (evita regressões por arquivos .bak deixados com mesmos uid).
- Considerar regra de alerta no Prometheus/Grafana para storj_node_consecutive_failures > 2 para notificar antes de auto-heal.

9) Observações de segurança e operacional
- Não commitar secrets. Qualquer credencial usada localmente (ex: GF_SECURITY_ADMIN_PASSWORD) deve permanecer em vault/secret_store.
- As alterações foram feitas no host 192.168.15.2 — reveja mudanças em systemctl e iptables em janelas de manutenção apropriadas.

---
Arquivo gerado neste repositório: docs/storj-selfheal-grafana.md

Se quiser, eu posso: criar um commit com este arquivo; abrir um PR; ou aplicar testes unitários para o exporter (deseja que eu faça algum desses?).
