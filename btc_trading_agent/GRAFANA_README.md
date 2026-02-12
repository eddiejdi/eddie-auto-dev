# AutoCoinBot Grafana Dashboard

Dashboard completo do Grafana para monitoramento em tempo real do agente de trading AutoCoinBot.

## 📊 Recursos do Dashboard

### Métricas Principais
- **Preço BTC Atual**: Preço em tempo real do Bitcoin
- **PnL Total**: Lucro/Prejuízo acumulado
- **Win Rate**: Taxa de sucesso das operações
- **Total de Trades**: Número total de negociações executadas

### Gráficos de Performance
- **Preço BTC (Tempo Real)**: Gráfico de linha com o preço do Bitcoin
- **PnL Acumulado**: Evolução do lucro ao longo do tempo
- **Trades por Hora**: Barras mostrando compras e vendas
- **Indicadores Técnicos**: RSI, Momentum, Volatilidade

### Análise de Decisões
- **Distribuição de Decisões**: Gráfico de pizza com BUY/SELL/HOLD
- **RSI Gauge**: Indicador visual do RSI (0-100)
- **Últimas Operações**: Tabela com os últimos trades

### Status do Sistema
- **Status do Agente**: Ativo/Inativo
- **Modo de Operação**: DRY RUN ou LIVE
- **Última Atividade**: Tempo desde a última operação
- **Episodes Treinados**: Quantidade de treinamento do modelo

## 🚀 Instalação

### Opção 1: Instalação Automática (Recomendado)

```bash
cd btc_trading_agent
chmod +x setup_grafana.sh
./setup_grafana.sh
```

O script irá:
1. Instalar Prometheus (se necessário)
2. Instalar Grafana (se necessário)
3. Configurar data sources
4. Criar serviços systemd
5. Importar o dashboard automaticamente

### Opção 2: Instalação Manual

#### 1. Instalar Prometheus

```bash
# Download
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xzf prometheus-2.40.0.linux-amd64.tar.gz
sudo cp prometheus-2.40.0.linux-amd64/prometheus /usr/local/bin/
sudo mkdir -p /etc/prometheus /var/lib/prometheus
```

#### 2. Configurar Prometheus

Criar `/etc/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: 'autocoinbot'
    static_configs:
      - targets: ['localhost:9090']
```

#### 3. Instalar Grafana

```bash
sudo apt-get install -y apt-transport-https software-properties-common
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt-get update
sudo apt-get install -y grafana

# Iniciar Grafana
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

#### 4. Iniciar Exporter de Métricas

```bash
cd btc_trading_agent
python3 prometheus_exporter.py &
```

#### 5. Importar Dashboard

1. Acesse Grafana: `http://localhost:3000` (admin/admin)
2. Vá em **Configuration** → **Data Sources**
3. Adicione Prometheus: `http://localhost:9091`
4. Vá em **Dashboards** → **Import**
5. Faça upload de `grafana_dashboard.json`

## 📈 Usando o Dashboard

### Acesso
```
URL:      http://localhost:3001
Username: admin
Password: admin
```

### Navegação
1. **Home** → **Dashboards** → **Trading**
2. Selecione: **🤖 AutoCoinBot - Trading Dashboard**

### Refresh Rate
- Configurado para atualizar a cada **5 segundos**
- Pode ser alterado no canto superior direito

### Time Range
- Padrão: **Últimas 6 horas**
- Ajuste conforme necessário (1h, 24h, 7d, etc)

## 🔧 Configuração

### Portas Padrão
- **Grafana**: 3001
- **Prometheus**: 9091
- **Exporter**: 9090

### Alterar Portas

Editar `setup_grafana.sh`:
```bash
PROMETHEUS_PORT=9091
EXPORTER_PORT=9090
GRAFANA_PORT=3001
```

### Métricas Customizadas

Editar `prometheus_exporter.py` para adicionar novas métricas:

```python
# Exemplo: adicionar nova métrica
output.append("# HELP minha_metrica Descrição da métrica")
output.append("# TYPE minha_metrica gauge")
output.append(f'minha_metrica {valor}')
```

## 🛠️ Troubleshooting

### Exporter não está rodando

```bash
# Verificar status
sudo systemctl status autocoinbot-exporter

# Ver logs
sudo journalctl -u autocoinbot-exporter -f

# Reiniciar
sudo systemctl restart autocoinbot-exporter
```

### Prometheus não coleta métricas

```bash
# Verificar targets
curl http://localhost:9091/targets

# Testar exporter diretamente
curl http://localhost:9090/metrics
```

### Dashboard vazio

1. Verificar se exporter está rodando
2. Verificar se Prometheus coleta dados (Targets devem estar UP)
3. Verificar data source no Grafana
4. Testar query diretamente no Prometheus

### Grafana não inicia

```bash
# Ver logs
sudo journalctl -u grafana-server -f

# Verificar se porta está livre
sudo netstat -tupln | grep 3001

# Reiniciar
sudo systemctl restart grafana-server
```

## 📊 Queries Prometheus

### Exemplos de queries úteis:

**Taxa de decisões BUY**:
```promql
increase(btc_trading_decisions_total{action="BUY"}[1h])
```

**PnL médio por hora**:
```promql
avg_over_time(btc_trading_total_pnl[1h])
```

**Win rate móvel (últimas 24h)**:
```promql
btc_trading_win_rate * 100
```

**Volatilidade normalizada**:
```promql
btc_trading_volatility * 100
```

## 🔐 Segurança

### Produção
1. **Alterar senha do Grafana**:
   - Login → Profile → Change Password

2. **Restringir acesso**:
   ```bash
   # Grafana apenas localhost
   sudo sed -i 's/;http_addr =/http_addr = 127.0.0.1/' /etc/grafana/grafana.ini
   
   # Usar proxy reverso (nginx/caddy)
   ```

3. **Autenticação**:
   - Habilitar HTTPS
   - Configurar OAuth/LDAP se necessário

## 📝 Manutenção

### Backup do Dashboard
```bash
# Exportar dashboard
curl -u admin:admin http://localhost:3001/api/dashboards/uid/autocoinbot-trading > backup.json
```

### Restaurar Dashboard
1. Grafana → Dashboards → Import
2. Upload do arquivo `backup.json`

### Limpar dados do Prometheus
```bash
# Limpar dados antigos (cuidado!)
sudo systemctl stop autocoinbot-prometheus
sudo rm -rf /var/lib/prometheus/*
sudo systemctl start autocoinbot-prometheus
```

## 🎨 Customização

### Cores do Dashboard
1. Editar `grafana_dashboard.json`
2. Modificar seção `fieldConfig.defaults.color`
3. Reimportar dashboard

### Adicionar Painéis
1. Dashboard → Add Panel
2. Configurar query Prometheus
3. Salvar
4. Export JSON → substituir `grafana_dashboard.json`

## 📚 Recursos

- [Grafana Docs](https://grafana.com/docs/)
- [Prometheus Docs](https://prometheus.io/docs/)
- [PromQL Cheatsheet](https://promlabs.com/promql-cheat-sheet/)

## 🆘 Suporte

Em caso de problemas:
1. Verificar logs de todos os serviços
2. Testar endpoints individualmente
3. Consultar documentação oficial
4. Abrir issue no repositório

---

**Criado para**: AutoCoinBot  
**Versão**: 1.0.0  
**Data**: Fevereiro 2026
