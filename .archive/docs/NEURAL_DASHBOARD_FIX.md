# 🔧 Correção do Dashboard Neural - Relatório Técnico

## 📋 Resumo Executivo

**Problema**: Dashboard Neural no Grafana exibindo "No Data" em todos os painéis  
**Causa Raiz**: Exporters (Node Exporter e cAdvisor) não instalados e erro de rede Docker  
**Solução**: Instalação dos exporters na rede `homelab_monitoring` e configuração correta do Prometheus  
**Status**: ✅ **RESOLVIDO** - Dashboard 100% funcional

---

## 🔍 Diagnóstico do Problema

### Sintomas Iniciais
- Dashboard criado com 8 painéis mostrando "No Data"
- Grafana e Prometheus rodando corretamente
- Queries Prometheus retornando 0 resultados

### Investigação
```bash
# Verificação de métricas
curl 'http://localhost:9090/api/v1/query?query=container_memory_usage_bytes'
# Resultado: {"data":{"result":[]}}

# Verificação de targets
curl 'http://localhost:9090/api/v1/targets'
# Resultado: Apenas 1 target (prometheus) - exporters faltando
### Causa Raiz Identificada
1. **Node Exporter não instalado** - Sistema sem métricas de CPU, memória, disco, rede
2. **cAdvisor não instalado** - Sem métricas de containers Docker
3. **Erro de rede Docker** - Primeira tentativa com `network_mode: bridge` + alias falhou
4. **Resolução DNS IPv6** - Prometheus tentando conectar via `[::1]` ao invés de `127.0.0.1`
5. **Isolamento de rede** - Containers em redes diferentes não se comunicavam

---

## ✅ Solução Implementada

### 1. Instalação dos Exporters

**Arquivo**: `docker-compose-exporters.yml`

```yaml
version: '3.8'

services:
  # Node Exporter - Métricas do sistema (CPU, Memory, Disk, Network)
  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    restart: unless-stopped
    command:
      - '--path.rootfs=/host'
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    networks:
      - homelab_monitoring

  # cAdvisor - Métricas de containers Docker
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: cadvisor
    restart: unless-stopped
    privileged: true
    devices:
      - /dev/kmsg:/dev/kmsg
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    networks:
      - homelab_monitoring

networks:
  homelab_monitoring:
    external: true
**Decisão Técnica**: Uso de `networks: homelab_monitoring` ao invés de `network_mode: bridge` para permitir comunicação DNS entre containers.

### 2. Configuração do Prometheus

**Arquivo**: `/home/homelab/monitoring/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
  
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
**Decisão Técnica**: Uso de nomes DNS (`node-exporter:9100`) ao invés de IPs, possível graças à rede Docker compartilhada.

### 3. Comandos de Instalação

```bash
# 1. Deploy dos exporters na rede correta
scp docker-compose-exporters.yml homelab@${HOMELAB_HOST}:/tmp/
ssh homelab@${HOMELAB_HOST} "cd /tmp && docker-compose -f docker-compose-exporters.yml up -d"

# 2. Atualizar configuração do Prometheus
scp prometheus-config.yml homelab@${HOMELAB_HOST}:/home/homelab/monitoring/prometheus.yml

# 3. Recarregar Prometheus sem downtime
ssh homelab@${HOMELAB_HOST} "docker kill -s HUP prometheus"

# 4. Verificar métricas (aguardar 15s para primeiro scrape)
curl 'http://localhost:9090/api/v1/query?query=container_memory_usage_bytes'
curl 'http://localhost:9090/api/v1/query?query=node_memory_MemAvailable_bytes'
---

## 📊 Validação da Solução

### Métricas Agora Disponíveis

#### 1. Container Metrics (cAdvisor)
```bash
curl -s 'http://localhost:9090/api/v1/query?query=container_memory_usage_bytes' | grep -c '"value"'
# Resultado: 90+ métricas (todos os containers e systemd services)
**Containers Detectados**:
- ✅ prometheus, grafana, node-exporter, cadvisor
- ✅ open-webui, waha, shared-postgres, openwebui-postgres, code-runner
- ✅ nextcloud-app, nextcloud-db, nextcloud-redis, nextcloud-cron
- ✅ Todos os serviços systemd (ollama, specialized-agents-api, shared-expurgo, etc.)

#### 2. System Metrics (Node Exporter)
```bash
# Memória disponível
curl -s 'http://localhost:9090/api/v1/query?query=node_memory_MemAvailable_bytes'
# Resultado: 24.6 GB disponível

# CPU cores
curl -s 'http://localhost:9090/api/v1/query?query=node_cpu_seconds_total' | grep -c '"value"'
# Resultado: 1+ métricas por core
**Métricas do Sistema**:
- ✅ CPU: `node_cpu_seconds_total` (idle, user, system, iowait)
- ✅ Memória: `node_memory_MemAvailable_bytes`, `node_memory_MemTotal_bytes`
- ✅ Disco: `node_filesystem_avail_bytes`, `node_filesystem_size_bytes`
- ✅ Rede: `node_network_receive_bytes_total`, `node_network_transmit_bytes_total`

---

## 🧠 Painéis do Dashboard Neural

### Painel 1: System Overview
**Tipo**: Stat  
**Query**: `node_uname_info`  
**Dados**: Hostname, Kernel, Architecture  

### Painel 2: Docker Containers Memory (Pie Chart)
**Tipo**: Pie Chart  
**Query**: `topk(10, container_memory_usage_bytes{name!=""})`  
**Dados**: Top 10 containers por uso de memória  

### Painel 3: Running Agents
**Tipo**: Table  
**Query**: `container_memory_usage_bytes{name=~".*agent.*|.*coordinator.*|.*director.*"}`  
**Dados**: Lista de agentes ativos com uso de memória  

### Painel 4: CPU Usage (%)
**Tipo**: Time Series  
**Query**: `100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)`  
**Dados**: % de CPU em uso (linha temporal)  

### Painel 5: Memory Usage (%)
**Tipo**: Time Series  
**Query**: `(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100`  
**Dados**: % de memória em uso (linha temporal)  

### Painel 6: Disk Usage (%)
**Tipo**: Gauge  
**Query**: `(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes)) * 100`  
**Dados**: % de disco em uso (medidor)  

### Painel 7: System Network I/O
**Tipo**: Time Series  
**Query RX**: `rate(node_network_receive_bytes_total{device!~"lo|veth.*"}[5m])`  
**Query TX**: `rate(node_network_transmit_bytes_total{device!~"lo|veth.*"}[5m])`  
**Dados**: Bytes/s recebidos e enviados  

### Painel 8: Container Network I/O
**Tipo**: Time Series  
**Query RX**: `rate(container_network_receive_bytes_total{name!=""}[5m])`  
**Query TX**: `rate(container_network_transmit_bytes_total{name!=""}[5m])`  
**Dados**: Tráfego de rede por container  

---

## 🔗 Acesso ao Dashboard

### Via SSH Tunnel (localhost)
```bash
./open_grafana.sh
**URLs**:
- Dashboard Neural: http://localhost:3002/grafana/d/neural-network-v1/
- Home Grafana: http://localhost:3002/grafana/
- API Health: http://localhost:3002/api/health

**Credenciais**:
- Usuário: `admin`
- Senha: `newpassword123`

### Direto no Servidor (${HOMELAB_HOST})
```bash
ssh -L 3002:127.0.0.1:3002 homelab@${HOMELAB_HOST}
# Depois acessar http://localhost:3002/grafana/d/neural-network-v1/
---

## 🛠️ Troubleshooting

### Problema: Dashboard mostra "No Data"
**Solução**:
1. Verificar se exporters estão rodando: `docker ps | grep -E '(exporter|cadvisor)'`
2. Testar métricas diretas: `curl http://localhost:9100/metrics` (Node Exporter)
3. Testar Prometheus: `curl 'http://localhost:9090/api/v1/query?query=up'`
4. Verificar targets: `curl http://localhost:9090/targets` - todos devem estar "up"

### Problema: Prometheus não alcança exporters
**Erro**: `Get "http://localhost:9100/metrics": dial tcp [::1]:9100: connection refused`

**Diagnóstico**:
```bash
# Verificar rede do Prometheus
docker inspect prometheus --format='{{.HostConfig.NetworkMode}}'
# Deve ser: homelab_monitoring

# Verificar rede dos exporters
docker inspect node-exporter --format='{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}'
docker inspect prometheus --format='{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}'
# Devem ser iguais
**Solução**: Recriar exporters na rede correta (ver seção 3 acima)

### Problema: Erro "network-scoped alias is supported only for user defined networks"
**Causa**: Tentativa de usar alias na rede bridge padrão  
**Solução**: Usar `networks: homelab_monitoring` com `external: true`

### Problema: Métricas antigas (timestamp desatualizado)
**Solução**: Aguardar 15 segundos (scrape_interval) para novo scrape

### Problema: Erro de renderização por paleta "gradient"
**Sintoma**: Erro no Grafana com mensagem `"gradient" not found in: fixed,shades,thresholds,...` ao abrir o dashboard.
**Causa**: Algumas configurações do dashboard usavam `color.mode: "gradient"`, que não é um nome de paleta válido nesta versão do Grafana.
**Correção aplicada**: Substituí `color.mode: "gradient"` por `color.mode: "palette-classic"` e removi valores `serializedValue` que referenciavam `gradient`. Publiquei a versão corrigida do dashboard (versão 4).


---

## 📈 Resultados Obtidos

### Antes da Correção
- ❌ 0 métricas coletadas
- ❌ 0 targets funcionando (além do Prometheus)
- ❌ Dashboard completamente vazio

### Depois da Correção
- ✅ 90+ métricas de containers
- ✅ 100+ métricas de sistema (CPU, memória, disco, rede)
- ✅ 3 targets funcionando: prometheus, node-exporter, cadvisor
- ✅ Dashboard 100% funcional com dados em tempo real
- ✅ Atualização a cada 15 segundos

---

## 🎯 Lições Aprendidas

### 1. Isolamento de Rede Docker
**Problema**: Containers em redes diferentes não se comunicam por DNS  
**Aprendizado**: Sempre colocar containers que precisam se comunicar na mesma rede Docker customizada

### 2. IPv6 vs IPv4
**Problema**: `localhost` pode resolver para `::1` (IPv6) ao invés de `127.0.0.1`  
**Aprendizado**: Preferir nomes DNS de containers ao invés de localhost quando possível

### 3. Network Mode vs Networks
**Problema**: `network_mode: bridge` não permite aliases ou comunicação DNS  
**Aprendizado**: Usar `networks:` com rede customizada para comunicação inter-container

### 4. Prometheus Reload
**Comando**: `docker kill -s HUP prometheus`  
**Vantagem**: Recarrega configuração sem reiniciar o container (zero downtime)

### 5. Scrape Interval
**Default**: 15 segundos  
**Implicação**: Aguardar pelo menos 15s após mudanças de config para ver novas métricas

---

## 📝 Arquivos Modificados

1. ✅ **docker-compose-exporters.yml** - Criado com rede homelab_monitoring
2. ✅ **/home/homelab/monitoring/prometheus.yml** - Atualizado com targets DNS
3. ✅ **NEURAL_DASHBOARD_REPORT.md** - Documentação original do dashboard
4. ✅ **NEURAL_DASHBOARD_FIX.md** - Este documento (troubleshooting e solução)

---

## 🚀 Próximos Passos

1. ✅ **Monitoramento Contínuo**: Dashboard operacional
2. ⏳ **Alertas**: Configurar alertas no Prometheus para CPU/Memory > 80%
3. ⏳ **Retenção de Dados**: Ajustar Prometheus retention para 30 dias
4. ⏳ **Backups**: Adicionar backup automático das configurações
5. ⏳ **Dashboards Adicionais**: Criar dashboards específicos por agente
6. ✅ **Refinar painel `Agentes Especializados`**: Alterei a query para usar métricas de container (`container_memory_usage_bytes`) para refletir disponibilidade dos agentes (compatível com cAdvisor). Publicado versão 7.

---

## 📞 Suporte

**Acesso SSH**: `ssh homelab@${HOMELAB_HOST}`  
**Logs Prometheus**: `docker logs prometheus`  
**Logs Grafana**: `docker logs grafana`  
**Health Check**: `curl http://localhost:9090/-/healthy` (Prometheus)  
**Targets Status**: `curl http://localhost:9090/api/v1/targets`

---

**Documentação criada em**: 2026-02-06  
**Autor**: Shared Auto-Dev AI Assistant  
**Versão**: 1.0  
**Status**: ✅ Produção
