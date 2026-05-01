# Pi-hole Client DNS Remediation — 2026-04-29

> Diagnostico e remediacao da falha em que o Pi-hole estava funcional no homelab, mas esta maquina local ainda podia escapar do bloqueio ou perder navegacao.

**Wiki.js:** `https://wiki.rpa4all.com/pt/troubleshooting/pihole-client-dns-remediation-2026-04-29`

## Resumo Executivo

Em 2026-04-29 foi validado que:

- o **Pi-hole no homelab `192.168.15.2` estava operacional**;
- o **DHCP da LAN anunciava `192.168.15.2` como DNS** corretamente;
- esta maquina local tinha **overrides locais de DNS e de gerenciamento de `resolv.conf`**;
- havia tambem **instabilidade de rede local** por:
  - uma **reserva DHCP stale** para a placa cabeada;
  - **ARP flux** com Wi-Fi e Ethernet ativos no mesmo segmento LAN.

Ao final da intervencao, o estado ficou:

- DNS **automatico via DHCP no IPv4**;
- `resolv.conf` **gerado pelo NetworkManager**;
- DNS efetivo entregue pelo servidor: **`192.168.15.2`**;
- bloqueio Pi-hole funcional para dominios de anuncio;
- navegacao IP e DNS restauradas;
- coexistencia Wi-Fi + Ethernet estabilizada.

---

## Escopo da Intervencao

### Ambientes analisados

- **Homelab**
  - host: `192.168.15.2`
  - Pi-hole em container
  - DHCP LAN via `dnsmasq` no host
- **Cliente local**
  - hostname: `edenilson`
  - interfaces:
    - `enp0s31f6` -> `192.168.15.137`
    - `wlp2s0` -> `192.168.15.109`

### Validacoes executadas

- status de `pihole.service` e `homelab-lan-dhcp.service`
- verificacao de portas `53`, `67` e admin `8053`
- `dig @192.168.15.2` para dominios conhecidos
- consulta ao `pihole-FTL.db` para bloqueios recentes
- leitura de `nmcli`, `ip route`, `/etc/resolv.conf`
- reconexao controlada da interface cabeada
- revisao de logs do `NetworkManager`

---

## Diagnostico

### 1. Pi-hole funcional no servidor

Foi validado no homelab que:

- `pihole.service` estava `active`;
- `homelab-lan-dhcp.service` estava `active`;
- o FTL escutava em `0.0.0.0:53` e `[::]:53`;
- `doubleclick.net`, `googleadservices.com` e `static.doubleclick.net` eram bloqueados;
- havia bloqueios reais recentes para clientes da LAN no `pihole-FTL.db`.

Conclusao:

- o problema **nao era indisponibilidade do Pi-hole**.

### 2. Cliente local com bypass de DNS

Nesta maquina, o estado inicial mostrava:

- `/etc/resolv.conf` com:
  - `nameserver 192.168.15.2`
  - `nameserver 8.8.8.8`
  - `nameserver 8.8.4.4`
- a conexao `Wired connection 1` tinha DNS manual:
  - `192.168.15.2,8.8.8.8,8.8.4.4`
- o `NetworkManager` estava com:
  - `/etc/NetworkManager/conf.d/99-dns.conf`
  - `dns=none`

Impacto:

- o sistema podia consultar DNS fora do Pi-hole;
- `resolv.conf` nao era mais gerenciado automaticamente;
- a correcao local anterior de DNS estava manual, e nao automatica via DHCP.

### 3. `resolv.conf` corrompido por script local

O arquivo:

- `/etc/NetworkManager/dispatcher.d/10-no-aaaa`

estava com esta logica:

- adicionava `options no-aaaa` por efeito colateral de precedencia shell;
- podia appendar repetidamente no `resolv.conf`.

Impacto:

- `resolv.conf` ficava poluido com dezenas de linhas repetidas.

### 4. Navegacao perdida por rota default ausente

Em um momento da intervencao, a maquina ficou apenas com rota local:

- havia rota para `192.168.15.0/24`;
- nao havia `default via 192.168.15.1`.

Impacto:

- `ping 192.168.15.1` funcionava;
- `ping 1.1.1.1` retornava `Network is unreachable`;
- a falha era **de roteamento**, nao de DNS.

### 5. Reserva DHCP stale no homelab

No arquivo do DHCP LAN do homelab:

- `/etc/dnsmasq.d/homelab-lan.conf`

existia a linha:

- `dhcp-host=18:66:da:fe:58:94,192.168.15.4,12h`

Esse MAC e o da interface cabeada desta maquina:

- `18:66:da:fe:58:94`

Mas a maquina estava ativa em:

- `192.168.15.137`

e o IP `192.168.15.4` ja estava ocupado por outro host.

Impacto observado nos logs do `NetworkManager`:

- tentativas de configurar `192.168.15.4`;
- mensagens de conflito de endereco;
- instabilidade de conectividade.

### 6. ARP flux com Wi-Fi e Ethernet na mesma LAN

Com `wlp2s0` e `enp0s31f6` ativas na mesma sub-rede `192.168.15.0/24`, o `NetworkManager` registrava conflitos como:

- `conflict detected for IP address 192.168.15.137 with host D4:6A:6A:FD:9D:47`

Esse MAC corresponde a interface Wi-Fi da propria maquina.

Conclusao:

- havia **ARP flux** entre as duas interfaces;
- isso gerava ruido e aumentava risco de instabilidade em reconexoes.

### 7. Túnel `wg-panama` interferindo na saída direta

Mesmo com LAN e DNS corretos, foi identificado que:

- `ip route get 1.1.1.1` podia sair por `wg-panama`;
- a conexao `wg-panama` ainda trazia:
  - `allowed-ips=0.0.0.0/0;::/0;`
  - DNS proprio `1.1.1.1`
  - comportamento de full tunnel;
- em cenarios especificos isso desviava trafego e podia dar a impressao de "internet caiu", apesar de Pi-hole e DHCP estarem corretos.

Conclusao:

- havia uma **causa adicional e separada do Pi-hole**: o perfil WireGuard `wg-panama` ainda podia sequestrar saida e DNS.

---

## Alteracoes Aplicadas

## Homelab

### DHCP LAN

Arquivo alterado no host:

- `/etc/dnsmasq.d/homelab-lan.conf`

Ajuste aplicado:

- remocao da reserva stale:
  - `dhcp-host=18:66:da:fe:58:94,192.168.15.4,12h`

Servico reiniciado:

- `homelab-lan-dhcp.service`

Objetivo:

- eliminar atribuicao conflitante para a interface cabeada do cliente.

## Cliente local

### Perfis de rede

Conexoes ajustadas:

- `Wired connection 1`
- `GVT-38AA`

Estado final:

- DNS IPv4 sem fixacao manual;
- `ipv4.ignore-auto-dns = no`;
- `ipv6.ignore-auto-dns = yes`;
- Wi-Fi com:
  - `ipv4.never-default = yes`
  - `ipv4.ignore-auto-routes = yes`

Objetivo:

- deixar o DNS IPv4 vir automaticamente do DHCP;
- impedir que o Wi-Fi concorra como rota default;
- evitar bypass por DNS IPv6 enquanto a LAN nao entregar DNS IPv6 do Pi-hole.

### NetworkManager

Arquivo removido:

- `/etc/NetworkManager/conf.d/99-dns.conf`

Conteudo removido:

- `dns=none`

Objetivo:

- devolver ao `NetworkManager` o controle de `/etc/resolv.conf`.

### Script dispatcher local

Arquivo corrigido:

- `/etc/NetworkManager/dispatcher.d/10-no-aaaa`

Nova logica:

- adicionar `options no-aaaa` somente em evento `up`;
- adicionar apenas se a linha ainda nao existir.

Objetivo:

- impedir crescimento indefinido do `resolv.conf`.

### Mitigacao de ARP flux

Arquivo criado:

- `/etc/sysctl.d/90-arp-flux-avoidance.conf`

Parametros aplicados:

- `net.ipv4.conf.all.arp_ignore = 1`
- `net.ipv4.conf.all.arp_announce = 2`
- `net.ipv4.conf.default.arp_ignore = 1`
- `net.ipv4.conf.default.arp_announce = 2`
- `net.ipv4.conf.enp0s31f6.arp_ignore = 1`
- `net.ipv4.conf.enp0s31f6.arp_announce = 2`
- `net.ipv4.conf.wlp2s0.arp_ignore = 1`
- `net.ipv4.conf.wlp2s0.arp_announce = 2`

Objetivo:

- reduzir ambiguidade ARP com duas interfaces na mesma LAN.

### Perfil `wg-panama`

Arquivo persistido:

- `/etc/NetworkManager/system-connections/wg-panama.nmconnection`

Ajustes aplicados:

- `autoconnect=false`
- `peer-routes=false`
- `ignore-auto-dns=true`
- `never-default=true`
- remocao do DNS proprio do tunel no estado efetivo

Objetivo:

- impedir que o `wg-panama` assuma rota default;
- impedir que ele substitua o DNS do Pi-hole;
- manter o perfil disponivel para uso manual sem derrubar a navegacao local.

---

## Estado Final Validado

### Homelab

Validado:

- Pi-hole funcional em `192.168.15.2`;
- DHCP LAN anunciando:
  - `router = 192.168.15.1`
  - `dns-server = 192.168.15.2`
- reserva stale removida do `dnsmasq`.

### Cliente local

Validado:

- `nmcli` mostra na interface cabeada:
  - `IP4.GATEWAY: 192.168.15.1`
  - `IP4.DNS[1]: 192.168.15.2`
- `/etc/resolv.conf` agora e:

```conf
# Generated by NetworkManager
search lan
nameserver 192.168.15.2
options no-aaaa
```

- rota default final:

```bash
default via 192.168.15.1 dev enp0s31f6 proto dhcp src 192.168.15.137 metric 100
```

- `wg-panama` sem papel de default route:

```bash
GENERAL.DEFAULT: no
ipv4.never-default: yes
ipv4.ignore-auto-dns: yes
wireguard.peer-routes: no
connection.autoconnect: no
```

### Testes finais

Passaram com sucesso:

- `ping 1.1.1.1`
- `ping google.com`
- `curl -I https://www.google.com`
- `curl -I https://www.google.com` sem proxy
- `nslookup google.com`
- `nslookup doubleclick.net`

Resultados esperados confirmados:

- resolucao normal para dominios legitimos;
- `doubleclick.net -> 0.0.0.0`.
- saida direta continua pela LAN mesmo com `wg-panama` ativo.

---

## Decisoes Operacionais

### DNS automatico apenas no IPv4

Foi deliberadamente mantido:

- **automatico via DHCP no IPv4**
- **ignorando DNS automatico no IPv6**

Motivo:

- o DHCP IPv4 da LAN ja entrega o Pi-hole corretamente;
- o ambiente ainda nao foi validado para anunciar DNS IPv6 do Pi-hole;
- liberar DNS IPv6 automatico agora poderia reintroduzir bypass do bloqueio.

### Wi-Fi sem papel de default route

Foi mantido:

- `wlp2s0` ativa;
- mas sem assumir rota default.

Motivo:

- preservar conectividade secundaria;
- evitar competicao com a interface cabeada, que e o caminho principal.

---

## Pendencias e Melhorias Futuras

### 1. DNS IPv6 do Pi-hole

Melhoria recomendada:

- anunciar DNS IPv6 do Pi-hole na LAN;
- depois remover `ipv6.ignore-auto-dns = yes` no cliente.

Beneficio:

- comportamento totalmente automatico tambem para IPv6.

### 2. Revisao de outras reservas DHCP

Melhoria recomendada:

- revisar entradas `dhcp-host=` antigas em `/etc/dnsmasq.d/homelab-lan.conf`.

Beneficio:

- evitar novas colisoes por amarracoes stale.

### 3. Politica de multi-homing

Melhoria recomendada:

- documentar padrao oficial para hosts com Wi-Fi e Ethernet ativos na mesma LAN.

Beneficio:

- reduzir incidentes de ARP flux e de selecao de rota.

---

## Comandos de Verificacao Rapida

### No cliente local

```bash
nmcli device show enp0s31f6
ip route
cat /etc/resolv.conf
nslookup google.com
nslookup doubleclick.net
ping -c 2 1.1.1.1
```

### No homelab

```bash
ssh homelab@192.168.15.2 'sudo systemctl is-active pihole.service homelab-lan-dhcp.service'
ssh homelab@192.168.15.2 'dig @192.168.15.2 google.com +short'
ssh homelab@192.168.15.2 'dig @192.168.15.2 doubleclick.net +short'
ssh homelab@192.168.15.2 'grep -n "dhcp-host=" /etc/dnsmasq.d/homelab-lan.conf'
```

---

## Relacao com Documentacao Existente

Este documento complementa:

- `docs/HOMELAB_NETWORK_RECOVERY_2026-04-15.md`
- `docs/HOMELAB_QUICK_REFERENCE.md`

Diferenca principal:

- o documento de 2026-04-15 restaurou o **Pi-hole e DHCP no servidor**;
- este documento de 2026-04-29 fecha o ciclo no **cliente local**, removendo overrides de DNS, reserva stale e ARP flux.
