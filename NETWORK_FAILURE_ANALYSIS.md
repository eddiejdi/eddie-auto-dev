# Análise: O que quebrou a rede e como corrigir

## 🔍 Identificação do Problema

**Culpado**: `agent-network-exporter` iniciado em 00:50:42  
**Sintoma**: Servidor ${HOMELAB_HOST} inacessível após deploy  
**Causa Root**: 
1. Consumo excessivo de memória (427.3MB em segundos)
2. Queries SQL pesadas sem LIMIT durante inicialização
3. Intervalo de atualização muito agressivo (30s)

## 📋 Cronograma da Falha

| Tempo | Ação | Status |
|-------|------|--------|
| 00:35:12 | Deploy de memória | ✅ OK |
| 00:50:42 | Agent Network Exporter iniciado | ✅ Iniciou |
| 00:50:50 | Exporter disparou queries pesadas | ⚠️ Carga alta |
| ~00:51:00 | Servidor começou a degradar | 🔴 OOM/Travamento |
| ~00:51:30 | Conexão SSH perdida | ❌ Inacessível |

## 🔧 Correções Aplicadas

### 1. **Agent Network Exporter Otimizado**
- ✅ Adicionado `LIMIT 1000` nas queries de métricas
- ✅ Adicionado `LIMIT 100` nas queries de nodes  
- ✅ Adicionado `LIMIT 500` nas queries de edges
- ✅ Intervalo de atualização aumentado: 30s → 60s

### 2. **Chaves SSH Corrigidas**
- ✅ Gerada nova chave RSA dedicada: `~/.ssh/id_rsa_eddie`
- ⚠️ Pendente: Instalar no servidor quando estiver online

## 🚀 Como Recuperar

### Quando o servidor voltar online:

```bash
# Execute o script de recuperação
./recovery_network.sh
Este script irá:
1. Conectar ao servidor com a nova chave RSA
2. Parar o serviço problemático
3. Desabilitar permanentemente
4. Remover arquivo de serviço
5. Reiniciar SSH
6. Atualizar código
7. Validar status

### Se o servidor continuar inacessível:

Acesse fisicamente (ou via consola Proxmox/VirtualBox) e execute:

```bash
# No servidor
sudo systemctl stop agent-network-exporter
sudo systemctl disable agent-network-exporter
sudo systemctl restart ssh
## 📊 Dashboard Neural Network

O dashboard Grafana foi parcialmente deployado:
- ✅ Arquivos criados e copiados
- ✅ Service systemd criado
- ✅ Exporter iniciado (mas com problemas de memória)
- ❌ Dashboard não foi importado (erro 6 no curl)

### Quando recuperar:

1. Aguarde server ficar online
2. Remova agent-network-exporter
3. Deploy do dashboard pode ser retomado depois com:
   ```bash
   ./deploy_neural_network_grafana.sh
   ```

## ⚡ Lições Aprendidas

1. **Queries sem LIMIT são perigosas** em Prometheus/exporters
2. **Intervalos de 30s são muito agressivos** para queries pesadas
3. **OOM não mata SSH imediatamente** - servidor fica em estado degradado
4. **Múltiplas tentativas de ssh-copy-id podem corromper authorized_keys**

## 📝 Próximos Passos

1. ✅ Aguardar servidor voltar online
2. ✅ Executar `./recovery_network.sh`
3. ✅ Validar serviços essenciais
4. ⏳ (Opcional) Re-habilitar dashboard com otimizações

## 🔐 Arquivos Modificados

- `specialized_agents/agent_network_exporter.py` - Otimizado com LIMITs
- `recovery_network.sh` - Script de recuperação (novo)
- `deploy_neural_network_grafana.sh` - Mantido para retry após recuperação
