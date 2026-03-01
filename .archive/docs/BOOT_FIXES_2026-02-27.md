# Correções de Boot do Servidor Homelab - 27 de Fevereiro de 2026

## Resumo das Correções Implementadas

### 1. **Serviços Desnecessários Desabilitados** ✅

Removidos serviços que aumentavam desnecessariamente o tempo de boot:

- **snapd.service** (-44 segundos)
- **snapd.socket** (dependência)
- **smbd.service** (-12 segundos - Samba)
- **nmbd.service** (-39 segundos - NetBIOS)

**Impacto**: Redução de ~95 segundos no tempo de boot

```bash
sudo systemctl disable snapd.service snapd.socket
sudo systemctl disable smbd.service nmbd.service
```

---

### 2. **Timeout do fwupd Reduzido** ✅

O serviço `fwupd` (Firmware Update Daemon) estava passando 25 segundos esperando respostas que nunca vinham.

**Novo timeout**: 10 segundos (em `/etc/systemd/system/fwupd.service.d/timeout.conf`)

```
[Service]
TimeoutStartSec=10s
```

**Impacto**: Redução de ~15 segundos

---

### 3. **Scripts de Espera Postgres** ✅

Criados dois scripts utilitários para aguardar o Postgres estar pronto:

#### `/usr/local/bin/wait_postgres.sh`
Aguarda conexão TCP ao Postgres (máx 30 segundos)
- Host: `172.17.0.2:5432` (container Docker)
- Usado como `ExecStartPre` em serviços que dependem do BD

#### `/usr/local/bin/start_eddie_postgres.sh`
Gerencia o ciclo de vida do container eddie-postgres:
- Inicia/cria o container se necessário
- Aguarda Postgres responder
- Garante que o banco está pronto antes de retornar

---

### 4. **Dependências de Serviços Corrigidas** ✅

Adicionadas dependências apropriadas para garantir ordem correta de inicialização:

#### **crypto-agent@.service.d/deps.conf**
```
[Unit]
After=docker.service eddie-postgres.service
Wants=eddie-postgres.service

[Service]
ExecStartPre=/usr/local/bin/wait_postgres.sh
```

Aplica-se a:
- `crypto-agent@BTC_USDT.service`
- `crypto-agent@ETH_USDT.service`
- `crypto-agent@XRP_USDT.service`
- `crypto-agent@SOL_USDT.service`
- `crypto-agent@DOGE_USDT.service`
- `crypto-agent@ADA_USDT.service`

#### **btc-trading-agent.service.d/deps.conf**
```
[Unit]
After=docker.service eddie-postgres.service

[Service]
ExecStartPre=/usr/local/bin/wait_postgres.sh
Restart=always
RestartSec=30
```

#### **autocoinbot-exporter.service.d/deps.conf**
Mesma configuração que btc-trading-agent

**Benefício**: Evita falhas de conexão ao BD durante o boot

---

### 5. **ha-grafana-sync Otimizado** ✅

Arquivo: `/etc/systemd/system/ha-grafana-sync.service.d/boot.conf`

```
[Unit]
After=network-online.target docker.service
Wants=docker.service

[Service]
Type=simple
TimeoutStartSec=120s
RemainAfterExit=no
```

**Impacto**: Deixa serviço não-crítico no boot; desbloqueado após alguns segundos

---

### 6. **python-training.service Reconfigured** ✅

Arquivo: `/etc/systemd/system/python-training.service.d/boot.conf`

Mudanças:
- Timeout reduzido de 21600s (6 horas) para 3600s (1 hora)
- Configurado para executar após boot completar (`After=multi-user.target`)
- Não impede conclusão do boot se falhar

```
[Unit]
After=multi-user.target ollama.service

[Service]
TimeoutStartSec=3600
```

**Impacto**: Boot pode completar em ~10min em vez de esperar treinamento de 6 horas

---

### 7. **Novo Serviço eddie-postgres** ✅

Criado `/etc/systemd/system/eddie-postgres.service`:

- **Type**: oneshot
- **ExecStart**: `/usr/local/bin/start_eddie_postgres.sh`
- **RemainAfterExit**: yes
- **WantedBy**: multi-user.target

Garante que o container Postgres está pronto cedo no boot, antes de outros serviços tentarem se conectar.

---

## Problemas Identificados (Boot Anterior)

### Raiz da Causa: Boot Anterior Lento (1h11min)

Sequência de erros durante boot anterior (02:23-02:25 UTC):

1. **PostgreSQL indisponível** durante startup
   - Crypto-agents falhavam: `connection to server at "172.17.0.2", port 5432 failed: Connection refused`
   - Serviços tentavam reconectar indefinidamente

2. **Timeout em fwupd**
   - `dbus-daemon: Failed to activate service 'org.freedesktop.fwupd': timed out (service_start_timeout=25000ms)`

3. **Cascata de falhas**
   - Cada falha causava restarts (RestartSec=10)
   - Crypto-agents com StartLimitBurst=5 disparavam múltiplas tentativas

---

## Resultados Esperados

### Boot Time
- **Antes**: 10min 13seg + timeout anterior de 1h11min
- **Depois**: 7-8 minutos (redução de ~25%)

### Confiabilidade
- ✅ Crypto-agents iniciam com sucesso
- ✅ Nenhuma falha de conexão ao BD
- ✅ Serviços não mais em cascata de falhas

### Monitoramento
Para validar as correções no próximo boot:

```bash
# Ver duração total
sudo systemd-analyze

# Ver serviços mais lentos
sudo systemd-analyze blame | head -20

# Ver dependências de um serviço
sudo systemctl cat crypto-agent@BTC_USDT.service | grep -A2 "^After="
```

---

## Checklist Final

- [x] Desabilitados snapd e smbd
- [x] Timeout fwupd reduzido
- [x] Script wait_postgres criado
- [x] Script start_eddie_postgres criado
- [x] Dependências de crypto-agents configuradas
- [x] btc-trading-agent com wait_postgres
- [x] autocoinbot-exporter com wait_postgres
- [x] ha-grafana-sync otimizado
- [x] python-training redimensionado
- [x] Serviço eddie-postgres criado
- [x] systemctl daemon-reload executado

---

## Próximas Ações

1. **Próximo boot**: Monitorar com `systemd-analyze`
2. **Se ainda houver problemas**:
   - Verificar logs: `sudo journalctl -b --no-pager`
   - Analisar: `sudo systemd-analyze critical-chain`
3. **Documentar progresso**: Comparar tempos antes/depois

