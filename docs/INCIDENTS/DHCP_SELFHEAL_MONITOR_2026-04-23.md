# DHCP Selfheal + Painel Dedicado

Data: 2026-04-23
Escopo: recuperação de DHCP no homelab, automação de autocura, observabilidade dedicada no Grafana e validação ponta a ponta.

## 1) Resumo executivo

O incidente de conectividade na LAN foi causado por regras nftables que deixavam tráfego DHCP ser descartado antes de alcançar o dnsmasq.

Foi implementado:

- correção da ordem das regras DHCP no nftables
- serviço de autocura contínua para DHCP
- exportação de métricas Prometheus via textfile collector
- dashboard dedicado no Grafana
- validação operacional no backend e no frontend web

Estado final validado:

- dhcp-selfheal.service: enabled + active
- métricas-chave em verde: dhcp_service_up=1, dhcp_socket_bound=1, dhcp_nftables_rules_ok=1, dhcp_responding=1
- dashboard disponível e carregando sem erro de datasource

## 2) Causa raiz

Sintoma observado:

- clientes enviando DHCPDISCOVER sem receber DHCPOFFER
- dnsmasq ativo, socket UDP:67 aberto, porém sem respostas

Causa raiz confirmada:

- na chain ip mangle PREROUTING existia regra catch-all DROP para iifname eth-onboard antes das regras de ACCEPT para DHCP (UDP 67/68)
- pacotes DHCP com origem 0.0.0.0 não casavam com ACLs anteriores e eram descartados

## 3) Correção imediata aplicada

Ajuste de regra em runtime para inserir ACCEPT de DHCP antes do DROP.

Regras efetivas colocadas antes do DROP:

- iifname eth-onboard udp dport 67 accept
- iifname eth-onboard udp sport 67 accept
- ip saddr 0.0.0.0 iifname eth-onboard accept

Após correção:

- retorno de DHCPOFFER e DHCPACK observado em logs do dnsmasq
- clientes voltaram a obter IP normalmente

## 4) Entregáveis criados

### 4.1 Selfheal DHCP

Arquivo: [scripts/dhcp_selfheal](scripts/dhcp_selfheal)

Funções principais:

- verifica serviço homelab-lan-dhcp.service
- verifica binding UDP:67 do dnsmasq
- valida posicionamento de regras DHCP antes do DROP no nftables
- detecta travamento por ausência de DHCPOFFER com DISCOVER recente
- executa autocura:
  - correção nftables via /usr/local/bin/fix-dhcp-nftables.sh
  - restart do serviço DHCP com rate limit (MAX_RESTARTS_HOUR)
- escreve métricas em /var/lib/prometheus/node-exporter/dhcp_selfheal.prom

Métricas exportadas:

- dhcp_service_up
- dhcp_socket_bound
- dhcp_nftables_rules_ok
- dhcp_responding
- dhcp_leases_active
- dhcp_pool_size
- dhcp_pool_usage_ratio
- dhcp_last_offer_age_seconds
- dhcp_selfheal_restarts_total
- dhcp_selfheal_nftables_fixes_total
- dhcp_selfheal_last_check_timestamp

### 4.2 Unit systemd

Arquivo: [systemd/dhcp-selfheal.service](systemd/dhcp-selfheal.service)

Configuração:

- ExecStart: /usr/local/bin/dhcp_selfheal
- Restart: on-failure
- RestartSec: 15
- Ambiente padrão:
  - CHECK_INTERVAL=30
  - DHCP_SERVICE=homelab-lan-dhcp.service
  - DHCP_RANGE_START=192.168.15.60
  - DHCP_RANGE_END=192.168.15.200
  - MAX_STUCK_SECONDS=300
  - MAX_RESTARTS_HOUR=5

### 4.3 Dashboard Grafana dedicado

Arquivo: [grafana_dashboards/dhcp-selfheal-monitor.json](grafana_dashboards/dhcp-selfheal-monitor.json)

UID do dashboard:

- dhcp-selfheal-monitor

Datasource Prometheus configurado no JSON:

- type: prometheus
- uid: dfc0w4yioe4u8e

URL do dashboard:

- https://grafana.rpa4all.com/d/dhcp-selfheal-monitor/dhcp-selfheal-monitor?orgId=1&from=now-6h&to=now&timezone=browser&refresh=30s

Painéis principais:

- Status Atual: Serviço DHCP, DHCP Respondendo, nftables DHCP Rules, Socket UDP:67, Restarts, Correções nftables
- Pool DHCP & Leases: gauge de uso do pool, séries de leases/pool, idade do último DHCPOFFER
- Histórico & Saúde: séries de estado e ações de autocura por janela

## 5) Deploy executado no homelab

Artefatos instalados:

- /usr/local/bin/dhcp_selfheal
- /etc/systemd/system/dhcp-selfheal.service
- /home/homelab/monitoring/grafana/provisioning/dashboards/dhcp-selfheal-monitor.json

Ativação:

- systemctl daemon-reload
- systemctl enable dhcp-selfheal.service
- systemctl start dhcp-selfheal.service

## 6) Validações realizadas

### 6.1 Backend/serviço

- systemctl is-enabled dhcp-selfheal.service -> enabled
- systemctl is-active dhcp-selfheal.service -> active

### 6.2 Métricas exportadas (snapshot)

Valores confirmados durante validação:

- dhcp_service_up 1
- dhcp_socket_bound 1
- dhcp_nftables_rules_ok 1
- dhcp_responding 1
- dhcp_leases_active 13
- dhcp_pool_size 141
- dhcp_pool_usage_ratio 0.0922
- dhcp_selfheal_restarts_total 0
- dhcp_selfheal_nftables_fixes_total 0

### 6.3 Grafana API

Consulta local de dashboard por UID:

- título: DHCP Selfheal Monitor
- uid: dhcp-selfheal-monitor
- url: /d/dhcp-selfheal-monitor/dhcp-selfheal-monitor

### 6.4 Frontend web (URL real)

Validação no navegador da URL pública:

- dashboard carregou corretamente
- cards com dados (sem No data)
- erro de datasource resolvido

Checagem automatizada em browser:

- noData = 0
- noDs = 0

## 7) Observações operacionais

- o incidente original foi agravado por ordenação de regras nftables; a autocura agora mitiga esse cenário automaticamente
- o script fix-dhcp-nftables.sh é dependência crítica do selfheal
- limite de restarts por hora evita loop agressivo de recuperação

## 8) Comandos úteis de operação

Status rápido:

- systemctl status dhcp-selfheal.service --no-pager
- journalctl -u dhcp-selfheal.service -n 100 --no-pager
- cat /var/lib/prometheus/node-exporter/dhcp_selfheal.prom

Validação DHCP em tempo real:

- journalctl -u homelab-lan-dhcp.service -f --no-pager
- tcpdump -ni eth-onboard -e -vv "udp and (port 67 or 68)"

## 9) Arquivos de referência

- [scripts/dhcp_selfheal](scripts/dhcp_selfheal)
- [systemd/dhcp-selfheal.service](systemd/dhcp-selfheal.service)
- [grafana_dashboards/dhcp-selfheal-monitor.json](grafana_dashboards/dhcp-selfheal-monitor.json)
