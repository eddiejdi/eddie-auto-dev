# Incidente: Storj Node Offline por Interface Drift (2026-08-11)

## Resumo

O nó Storj ficou offline por ~4 horas porque a interface de rede WAN mudou de `eth-wan` para `enx00e04c596710` (adaptador USB Ethernet). Todos os serviços que dependem da interface — `storj-host-shim`, rede macvlan e watchdog — falharam em cascata.

## Timeline

| Hora (BRT) | Evento |
|---|---|
| ~08:20 | Container `storagenode` parou (exit 255) |
| ~08:36 | `storj-host-shim.service` falhou: `Cannot find device "eth-wan"` |
| ~13:28 | Diagnóstico iniciado — interface `enx00e04c596710` detectada como WAN ativa |
| ~13:30 | Serviços corrigidos, macvlan recriada, container reiniciado |
| ~13:50 | Nó restaurado — quicStatus=OK, healthy, servindo dados |

## Causa Raiz

A interface de rede física mudou de nome:
- **Antes**: `eth-wan` (referenciada em todos os serviços)
- **Depois**: `enx00e04c596710` (adaptador USB Ethernet, MAC `00:e0:4c:59:67:10`)

A interface `eth-onboard` (MAC `00:e0:4c:b6:3d:5e`, IP `192.168.15.2`) continua existindo, mas a rota default agora usa `enx00e04c596710` (IP `192.168.15.3`).

### Por que aconteceu?

O homelab possui duas interfaces ativas:
- `eth-onboard` — Ethernet onboard (192.168.15.2)
- `enx00e04c596710` — USB Ethernet (192.168.15.3, rota default)

O nome `eth-wan` provavelmente era um alias udev ou naming convention que foi perdido. A macvlan e o host shim foram configurados com `eth-wan` que deixou de existir.

## Impacto

- Nó Storj offline por ~4 horas
- Sem upload/download durante o período
- Risco de desqualificação de satélites (minimizado por ser curto)
- Dados preservados (volume `/mnt/storj8tb/storj/data` intacto)

## Correções Aplicadas

### 1. `systemd/storj-host-shim.service`
```diff
- ip link add storj-host0 link eth-wan type macvlan mode bridge
+ ip link add storj-host0 link enx00e04c596710 type macvlan mode bridge
```

### 2. `systemd/storj-macvlan-network.service`
```diff
- docker network create -d macvlan ... -o parent=eth-wan storj_macvlan
+ docker network create -d macvlan ... -o parent=enx00e04c596710 storj_macvlan
```

### 3. `grafana/exporters/storj_selfheal_exporter.py`
```diff
- config_path="/mnt/disk3/storj/data/config.yaml",
+ config_path="/mnt/storj8tb/storj/data/config.yaml",
```
(path corrigido para refletir o volume real de dados)

### 4. `tests/test_storj_selfheal_exporter.py`
- path do sync_public_address atualizado para `/mnt/storj8tb`

### 5. Deploy no homelab
- Service files atualizados em `/etc/systemd/system/`
- `daemon-reload` executado
- Rede `storj_macvlan` recriada com parent correto
- Container reiniciado via `docker compose -f docker-compose.storj.yml up -d`

## Verificação Pós-Incidente

| Check | Resultado |
|---|---|
| Container | ✅ healthy, running |
| QUIC | ✅ OK |
| API (14002) | ✅ respondendo |
| Porta 28967 | ✅ ativa |
| Public IP | ✅ 189.27.196.49 (confere com config) |
| Host shim | ✅ active, storj-host0 UP |
| Watchdog timer | ✅ active |
| Downloads/uploads | ✅ ativos (satélites conectando) |

## Lições Aprendidas

1. **Interface naming é frágil**: udev rules ou naming convention podem mudar com hardware changes. Considerar usar `ID_PATH` ou MAC address em vez de nomes de interface.
2. **O self-heal não detectou**: O exporter monitora IP/porta mas não verifica se a interface physical parent existe. Adicionar check de interface parent.
3. **Watchdog não ajudou**: O `storj-macvlan-watchdog` só verifica eth0 no namespace do container, não a interface parent no host.
4. **Path do config.yaml estava errado**: O self-heal exporter referenciava `/mnt/disk3/storj/data` mas o volume real é `/mnt/storj8tb/storj/data`.

## Ações Recomendadas

- [ ] Tornar o `storj-host-shim` resiliente a mudanças de interface (detectar WAN automaticamente)
- [ ] Adicionar check de interface parent no self-heal exporter
- [ ] Considerar usar `predictable interface names` ou udev rule estável para a WAN
