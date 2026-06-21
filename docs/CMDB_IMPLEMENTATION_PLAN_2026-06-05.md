# Plano de Implantacao CMDB - NetBox + GLPI

Data: 2026-06-05

## Objetivo

Implantar um CMDB pragmatico para o ambiente `empresa + servidores + homelab`, separando:

- `NetBox` como fonte de verdade da infraestrutura pretendida
- `GLPI` como camada operacional de inventario, atendimento e ciclo de vida dos ativos

O objetivo nao e catalogar tudo de uma vez. O objetivo e criar uma base confiavel, com dono claro por tipo de dado, alimentacao controlada e utilidade operacional imediata.

## Decisao Arquitetural

### NetBox sera autoritativo para

- sites, localizacoes tecnicas e racks
- hosts fisicos e virtuais
- IPAM, sub-redes, VLANs e interfaces
- relacoes de conectividade e dependencias de infraestrutura
- clusters, hipervisores, VMs, circuitos e endpoints de rede

### GLPI sera autoritativo para

- inventario automatico de endpoints e servidores
- usuarios vinculados a ativos
- chamados, incidentes e requisicoes
- contratos, licencas, fornecedores e garantias
- ciclo de vida operacional do ativo

### Regras de integracao

- nao fazer sincronizacao bidirecional ampla
- integrar apenas chaves de referencia e campos definidos
- toda divergencia entre inventario descoberto e modelagem pretendida deve gerar reconciliacao, nao sobrescrita cega

## Encaixe no ambiente atual

O repositorio ja mostra as superfices que devem entrar no CMDB inicial:

- inventario Ansible do homelab em `config/inventory_homelab.yml`
- stack de monitoramento em `monitoring/prometheus.yml`, `monitoring/grafana/provisioning/`
- autenticacao centralizada em `tools/authentik_management/configs/docker-compose.override.yml`
- grande volume de servicos operacionais em `systemd/*.service` e `tools/**/*.service`
- stacks containerizadas em `docker/` e `deploy/**/docker-compose.yml`
- componentes de VPN, DNS, tunel e edge em `deploy/vpn/`, `tools/tunnels/` e servicos relacionados

Isso permite comecar com dados reais, em vez de montar o CMDB manualmente do zero.

## Escopo do MVP

### Dentro do MVP

- 1 site principal do homelab/empresa
- hosts Linux do homelab
- servicos systemd mais importantes
- stacks Docker principais
- monitoramento, VPN, DNS, Grafana, Prometheus, Authentik, Storj e componentes de storage
- inventario automatico via GLPI Agent nos servidores e estacoes prioritarias

### Fora do MVP

- descoberta full network em toda a LAN sem curadoria
- catalogacao detalhada de software em todos os endpoints logo no inicio
- processos ITIL completos antes do inventario basico estar confiavel
- integracao bidirecional complexa entre NetBox e GLPI na fase inicial

## Arquitetura Alvo

### Camada de plataforma

Recomendacao:

- uma VM ou host dedicado `cmdb`
- reverse proxy na frente
- SSO via Authentik
- backup diario das bases

### Servicos

- `NetBox`
- `PostgreSQL` do NetBox
- `Redis` do NetBox
- `GLPI`
- `MariaDB` do GLPI
- `Nginx` ou proxy equivalente

### Publicacao

- URL sugerida: `cmdb.rpa4all.com`
- subrotas ou subdominios:
- `netbox.cmdb.rpa4all.com`
- `glpi.cmdb.rpa4all.com`

Se preferir minimizar superficie publica, publicar apenas via VPN ou acesso autenticado interno.

## Modelo de Dados Inicial

### Entidades NetBox

- Site
- Location
- Rack
- Manufacturer
- Device Type
- Device Role
- Platform
- Cluster
- Virtual Machine
- Prefix
- VLAN
- IP Address
- Interface
- Circuit ou Provider quando aplicavel

### Entidades GLPI

- Entity
- Location
- Computer
- Network Equipment
- Virtual Machine como ativo referenciado
- User
- Supplier
- Contract
- License
- Ticket Category

## Mapeamento de Responsabilidades

| Dado | Sistema dono | Origem inicial |
|---|---|---|
| Hosts e VMs de infraestrutura | NetBox | inventario Ansible, hipervisor, cadastro manual inicial |
| IPs, VLANs, interfaces e prefixes | NetBox | rede atual, DNS, DHCP, configuracoes operacionais |
| Equipamentos de usuario | GLPI | GLPI Agent |
| Softwares instalados | GLPI | GLPI Agent |
| Dono do ativo e suporte | GLPI | cadastro operacional |
| Relacao host -> servicos monitorados | NetBox + observabilidade | Prometheus/Grafana + curadoria |
| Contratos e licencas | GLPI | cadastro manual/importacao |

## Fases de Implantacao

## Fase 0 - Preparacao e baseline

Duracao sugerida: 3 a 5 dias

### Atividades

- confirmar host ou VM onde o stack CMDB sera executado
- definir estrategia de backup e restauracao
- confirmar dominio, DNS e forma de exposicao
- definir grupos e roles de acesso no Authentik
- classificar o inventario inicial do repositorio por dominio:
- infraestrutura
- rede
- identidades
- monitoramento
- storage
- servicos de negocio

### Entregaveis

- planilha ou tabela de fontes de verdade por dominio
- lista de ativos do MVP
- nomenclatura padrao para sites, roles, tags e ambientes

### Criterio de aceite

- existe uma lista fechada do que entra no MVP
- existe decisao explicita de onde cada tipo de dado vai morar

## Fase 1 - Fundacao da plataforma

Duracao sugerida: 2 a 4 dias

### Atividades

- subir `NetBox + PostgreSQL + Redis`
- subir `GLPI + MariaDB`
- configurar reverse proxy
- integrar login com Authentik
- habilitar backup automatico
- criar monitoramento basico de disponibilidade dos dois sistemas

### Entregaveis

- ambientes acessiveis
- login SSO funcional
- rotina de backup testada

### Criterio de aceite

- acesso aos dois sistemas funcionando
- backup restauravel em ambiente de teste ou procedimento validado

## Fase 2 - Modelagem base no NetBox

Duracao sugerida: 4 a 7 dias

### Atividades

- criar site principal
- cadastrar locations tecnicas
- modelar device roles
- modelar platforms
- cadastrar hosts fisicos do homelab
- cadastrar VMs principais
- cadastrar prefixes, ranges e VLANs reais
- relacionar interfaces principais e IPs

### Fontes de entrada

- `config/inventory_homelab.yml`
- servicos e stacks em `systemd/`, `deploy/`, `docker/`, `tools/`
- documentacao de rede em `docs/`

### Entregaveis

- inventario de infraestrutura principal dentro do NetBox
- mapa inicial de IPAM

### Criterio de aceite

- pelo menos 80 por cento dos ativos do MVP aparecem no NetBox com role e IP corretos

## Fase 3 - GLPI operacional e agentes

Duracao sugerida: 4 a 7 dias

### Atividades

- configurar entidades, locations e categorias
- instalar GLPI Inventory plugin
- implantar GLPI Agent em:
- servidores Linux prioritarios
- estacoes Windows principais
- notebooks ou endpoints relevantes
- revisar fabricantes, modelos, softwares e usuarios coletados
- configurar categorias de chamados e fluxo minimo de atendimento

### Entregaveis

- inventario automatico funcionando
- ativos operacionais enriquecidos com software e usuario

### Criterio de aceite

- ao menos os endpoints prioritarios reportam para o GLPI
- o inventario coletado e utilizavel e nao esta poluido por ativos descartaveis

## Fase 4 - Integracao controlada NetBox <-> GLPI

Duracao sugerida: 3 a 5 dias

### Regra

Integrar pouco e com intencao.

### Integracoes recomendadas no inicio

- correlacionar hostname ou asset tag entre NetBox e GLPI
- exibir referencia cruzada entre ativo de infra e ativo operacional
- usar NetBox como consulta para times de operacao
- usar GLPI como origem de tickets e ownership

### Nao fazer no inicio

- sincronizar todos os campos de ambos os lados
- deixar descoberta automatica criar objetos de infraestrutura sem revisao
- usar GLPI para sobrescrever IPAM do NetBox

### Entregaveis

- tabela de correlacao entre os sistemas
- procedimento de reconciliacao de divergencias

### Criterio de aceite

- um host prioritario pode ser rastreado nos dois sistemas sem ambiguidade

## Fase 5 - Integracoes operacionais

Duracao sugerida: 1 a 2 semanas

### Integracoes prioritarias

- `Authentik` para SSO e grupos
- `Prometheus/Grafana` para dashboards de cobertura e saude do CMDB
- `Ansible` usando NetBox como referencia para inventario ou grupos logicos
- automacoes locais consumindo API do NetBox ou GLPI quando houver ganho claro

### Casos de uso reais

- localizar rapidamente um host, IP, role e dono
- saber quais servicos criticos rodam em um servidor
- abrir atendimento ja associado ao ativo certo
- auditar ativos sem agente ou sem dono

## Fase 6 - Governanca

Duracao sugerida: continua

### Politicas minimas

- nenhum ativo de producao entra sem owner
- nenhum IP ou prefixo critico fica fora do NetBox
- todo endpoint gerenciado relevante precisa reportar ao GLPI
- reconciliacao quinzenal das divergencias
- revisao mensal de ativos orfaos, duplicados e obsoletos

## Ordem Recomendada de Execucao

1. subir a plataforma
2. modelar NetBox com ativos de infraestrutura
3. ligar GLPI e agentes
4. cruzar os dois mundos
5. so depois automatizar integracoes mais profundas

## Backlog Tecnico Inicial

### Sprint 1

- definir host do CMDB
- publicar DNS e proxy
- instalar NetBox
- instalar GLPI
- integrar Authentik
- configurar backup

### Sprint 2

- cadastrar site, locations, roles e platforms
- importar ativos do `config/inventory_homelab.yml`
- levantar lista de hosts a partir de `systemd/*.service` e stacks docker
- cadastrar IPAM basico

### Sprint 3

- instalar GLPI Agent nos servidores Linux
- instalar GLPI Agent nas estacoes prioritarias
- revisar dados coletados
- configurar categorias de chamados

### Sprint 4

- criar reconciliacao NetBox x GLPI
- publicar dashboard de cobertura
- documentar processo operacional

## Riscos e Mitigacoes

### Risco: CMDB virar deposito de lixo

Mitigacao:

- limitar MVP
- definir dono por campo
- nao aceitar descoberta sem curadoria

### Risco: dados duplicados entre NetBox e GLPI

Mitigacao:

- ownership explicito por dominio
- integracao por referencia, nao por espelhamento amplo

### Risco: excesso de escopo logo no inicio

Mitigacao:

- comecar por homelab e servidores
- deixar endpoints secundarios e processos ITIL avancados para onda 2

## Criterios de Sucesso

- 100 por cento dos servidores criticos do MVP cadastrados
- 100 por cento das sub-redes criticas do MVP no NetBox
- 90 por cento dos endpoints prioritarios reportando ao GLPI
- todo ativo critico com owner definido
- tempo de resposta para localizar ativo, IP e dono reduzido de forma perceptivel

## Recomendacao Final

Para o seu ambiente, a melhor implantacao nao e `GLPI sozinho` nem `NetBox sozinho`.

O melhor caminho e:

- `NetBox` para infraestrutura, rede e estado pretendido
- `GLPI` para inventario automatico, usuarios, suporte e ciclo de vida

Comece pequeno:

- primeiro o homelab e os servidores principais
- depois estacoes e ativos corporativos
- por ultimo automacoes e reconciliacoes mais profundas

## Proximo Passo Recomendado

Executar uma fase `0.5` de descoberta estruturada e produzir os artefatos abaixo:

- lista de ativos do MVP
- taxonomy de roles e tags
- mapa inicial de sites, locations e redes
- matriz de ownership de dados entre NetBox e GLPI

Com isso, a implantacao deixa de ser conceitual e vira backlog executavel.
