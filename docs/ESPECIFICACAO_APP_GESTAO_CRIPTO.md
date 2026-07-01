# Especificacao de Produto - App Desktop Portatil de Gestao de BTC e Criptoativos

**Status:** Draft v2
**Data:** 2026-05-31
**Objetivo:** definir o escopo funcional, tecnico e operacional de um app desktop portatil, escrito em Python, instalado e executado a partir de pendrive, para gerenciamento de BTC e outras moedas, aproveitando a infraestrutura de trading multi-coin ja existente no repositorio.

## 1. Resumo Executivo

O aplicativo sera uma camada de controle e visibilidade sobre carteiras, contas em exchanges, ordens, posicoes, risco, alertas e automacoes de trading. O foco nao e substituir o motor de execucao ja existente, e sim orquestrar e tornar operavel, auditavel e expansivel o ecossistema atual.

O produto **nao sera uma aplicacao web como interface principal**. A interface primaria sera um **app desktop local**, distribuido em pendrive, com launchers e empacotamentos proprios para sistemas operacionais distintos, compartilhando a mesma base funcional em Python.

O produto deve comecar com **BTC como ativo principal** e suportar na primeira onda os pares ja presentes na infraestrutura do projeto:

- `BTC-USDT`
- `ETH-USDT`
- `SOL-USDT`
- `XRP-USDT`
- `DOGE-USDT`
- `ADA-USDT`

O primeiro conector de exchange deve ser a **KuCoin**, porque o repositorio ja possui agentes, exporters e rotinas alinhadas a esse ambiente.

## 2. Problema a Resolver

Hoje a operacao de cripto tende a ficar fragmentada entre:

- exchange
- carteiras externas
- agentes de trading
- dashboards de monitoramento
- planilhas ou relatorios manuais

Isso dificulta responder com seguranca a perguntas operacionais simples:

- Qual e a exposicao total por moeda?
- Quanto esta em carteira, quanto esta travado e quanto esta em ordens?
- Qual e o PnL realizado e nao realizado por ativo, conta e estrategia?
- Quais agentes estao autorizados a operar e em qual modo?
- Quando e necessario intervir manualmente?

## 3. Objetivos de Negocio

- Consolidar o patrimonio cripto em uma unica interface.
- Permitir uso direto a partir de pendrive, sem depender de instalacao complexa na maquina hospedeira.
- Permitir operacao segura com trilha de auditoria.
- Reduzir dependencia de consultas manuais em exchange, logs e Grafana.
- Preparar a base para escalar de BTC para operacao multi-moeda.
- Separar claramente o que e leitura, aprovacao e execucao.

## 4. Principios do Produto

- **Read-only first:** toda nova integracao com exchange ou carteira deve nascer em modo leitura.
- **Portabilidade first:** aplicacao, configuracoes, logs e exportacoes devem poder residir no pendrive.
- **Multisistema real:** o mesmo produto deve operar em ambientes Windows, Linux e macOS com pacotes proprios.
- **Python end-to-end:** interface, integracoes, sincronizacao e automacoes devem ser implementadas em Python.
- **Execucao controlada:** operacoes de compra, venda, saque e transferencia exigem guardrails.
- **Multi-moeda nativo:** o modelo de dados nao pode ser centrado apenas em BTC.
- **Auditabilidade total:** toda acao relevante deve gerar evento auditavel.
- **Operacao orientada a risco:** risco vem antes de conveniencia operacional.
- **Aproveitamento do legado:** reutilizar PostgreSQL, exporters, Grafana, Telegram e agentes ja existentes.

## 5. Escopo do Produto

### 5.1 Incluido

- Execucao local a partir de pendrive.
- Interface desktop local para operacao e consulta.
- Consolidacao de saldos por exchange, carteira e ativo.
- Visao de portfolio com custo medio, exposicao e PnL.
- Gestao de ordens manuais e ordens originadas por bots.
- Painel de status dos agentes de trading.
- Alertas de preco, risco, conexao e falha operacional.
- Historico de trades, transferencias, depositos e saques.
- Controle de acesso por perfil.
- Integracao com notificacoes Telegram e canais internos.
- Servicos locais para integracao com automacoes, CLI e componentes auxiliares.

### 5.2 Fora de Escopo Inicial

- Interface web como canal principal do produto.
- Custodia institucional propria.
- Integracao com dezenas de exchanges logo na primeira entrega.
- Execucao on-chain complexa em DEX no MVP.
- Calculo tributario completo por pais no MVP.
- Trading de alta frequencia.

### 5.3 Restricoes Obrigatorias

- O app deve estar instalado e distribuido no pendrive.
- O app deve ser multisistema.
- O app deve ser implementado em Python.
- A experiencia principal deve ser de aplicativo, nao de site.

## 6. Personas

### 6.1 Operador de Trading

Precisa ver saldo, posicoes, alertas, status dos bots e executar intervencoes controladas.

### 6.2 Gestor de Portfolio

Precisa entender exposicao por ativo, risco agregado, performance e concentracao.

### 6.3 Administrador Tecnico

Precisa configurar conectores, chaves, permissoes, jobs e observabilidade.

### 6.4 Auditor ou Compliance

Precisa consultar historico imutavel de ordens, alteracoes de configuracao e aprovacoes.

## 7. Casos de Uso Principais

1. Consultar patrimonio consolidado em BTC, USDT e moeda fiduciaria de referencia.
2. Ver distribuicao por ativo, exchange, carteira e estrategia.
3. Acompanhar entradas e saidas em tempo real.
4. Aprovar, bloquear ou pausar operacoes de bots.
5. Executar compra ou venda manual com confirmacao reforcada.
6. Definir limites de risco por ativo e por conta.
7. Receber alertas de drawdown, desconexao, falha de API ou divergencia de saldo.
8. Exportar historico operacional para analise financeira e fiscal.

## 8. Requisitos Funcionais

### RF-01 - Cadastro de contas e conectores

O sistema deve permitir cadastrar contas de exchange e carteiras externas com os seguintes atributos:

- nome amigavel
- tipo (`exchange`, `wallet`, `bot_account`, `cold_storage`)
- corretora ou rede
- status da conexao
- permissoes disponiveis
- modo de acesso (`read_only`, `trade_enabled`, `withdraw_enabled`)

### RF-02 - Suporte multi-ativo

O sistema deve tratar cada ativo como entidade de primeira classe, incluindo:

- ticker
- rede
- tipo (`spot`, `stablecoin`, `wrapped`, `staking`)
- precisao
- saldo disponivel
- saldo bloqueado
- preco medio
- valor de mercado

### RF-03 - Portfolio consolidado

O app deve exibir:

- patrimonio total
- patrimonio por ativo
- patrimonio por conta
- custo medio por ativo
- PnL realizado
- PnL nao realizado
- exposicao percentual por moeda

### RF-04 - Historico operacional

O sistema deve armazenar e consultar:

- trades
- ordens abertas, executadas, canceladas e rejeitadas
- transferencias internas
- depositos
- saques
- ajustes manuais
- eventos de bot

### RF-05 - Gestao de ordens

O sistema deve permitir:

- criar ordem manual de compra e venda
- consultar livro simplificado e ultimo preco
- acompanhar estado da ordem
- cancelar ordem pendente
- registrar origem da ordem (`manual`, `bot`, `rebalance`, `risk_action`)

### RF-06 - Gestao de bots e estrategias

O aplicativo deve funcionar como plano de controle dos agentes existentes, com capacidade de:

- listar instancias por moeda e perfil
- exibir modo atual (`live`, `dry_run`, `paused`)
- mostrar saude da instancia
- mostrar ultimo sinal, ultima decisao e ultimo trade
- pausar e retomar execucao
- aplicar limites operacionais por instancia

### RF-07 - Guardrails e risco

O sistema deve suportar politicas de risco configuraveis:

- limite maximo por ativo
- limite maximo por conta
- drawdown diario
- drawdown por estrategia
- bloqueio de saque
- exigencia de dupla confirmacao para acoes sensiveis
- circuit breaker para desconectar operacao automatica

### RF-08 - Alertas e notificacoes

O app deve emitir alertas para:

- variacao de preco acima de limite
- queda de saldo inesperada
- desconexao de API
- falha de sincronizacao
- bot parado ou degradado
- perda acima de limite
- ordem rejeitada
- deposito confirmado
- saque solicitado, aprovado ou concluido

Os canais iniciais devem incluir:

- interface desktop
- Telegram
- webhook

### RF-09 - Relatorios

O sistema deve gerar:

- resumo diario de portfolio
- relatorio por ativo
- relatorio por conta
- relatorio por estrategia
- relatorio de risco
- extrato operacional por periodo

### RF-10 - Auditoria e trilha de decisoes

Toda acao relevante deve registrar:

- quem executou
- quando executou
- origem da acao
- payload resumido
- estado anterior
- estado posterior
- resultado

### RF-11 - Controle de acesso

O sistema deve suportar pelo menos os perfis:

- `viewer`
- `operator`
- `risk_manager`
- `admin`

### RF-12 - Integracao local e automacao

O nucleo da aplicacao deve expor servicos reutilizaveis pela interface desktop, por rotinas de sincronizacao e por automacoes locais. Se existir API HTTP, ela deve ser opcional e restrita ao host local.

Capacidades minimas:

- portfolio consolidado
- saldos por conta
- ordens
- trades
- alertas
- status de bots
- configuracoes de risco
- eventos de auditoria

### RF-13 - Execucao portatil via pendrive

O sistema deve:

- iniciar diretamente a partir do pendrive
- usar caminhos relativos
- gravar configuracoes, logs, cache e exportacoes no proprio pendrive
- evitar dependencia de instalacao manual de componentes do sistema hospedeiro

### RF-14 - Compatibilidade multisistema

O sistema deve fornecer empacotamentos ou launchers para:

- Windows
- Linux
- macOS

O comportamento funcional deve ser equivalente entre os sistemas suportados.

### RF-15 - Stack padronizada em Python

O sistema deve ser implementado em Python, incluindo:

- interface do aplicativo
- conectores com exchange
- sincronizacao de dados
- motor de risco
- automacoes locais

## 9. Requisitos Nao Funcionais

### RNF-01 - Portabilidade

- O app deve operar a partir do pendrive sem depender de instalacao completa no host.
- O app deve usar estrutura de diretorios relativa ao ponto de execucao.
- Configuracoes, logs, cache e exportacoes devem poder permanecer no pendrive.

### RNF-02 - Multisistema

- O app deve funcionar em Windows, Linux e macOS com distribuicoes especificas por sistema.
- O pendrive deve poder conter os artefatos necessarios para cada sistema suportado.
- O comportamento principal do produto nao pode depender de navegador.

### RNF-03 - Seguranca

- Chaves de API nao podem ser armazenadas em texto puro em documentos ou codigo.
- Segredos devem ficar em cofre ou backend de secrets, com cache local criptografado apenas quando indispensavel.
- Toda acao sensivel deve ser autenticada e autorizada.
- Escrita em exchange deve poder ser desativada por ambiente.
- Perda do pendrive nao deve expor credenciais sem mecanismo adicional de protecao.

### RNF-04 - Disponibilidade

- O app deve continuar util em modo degradado mesmo se um conector falhar.
- Os servicos locais devem registrar falhas por conector sem derrubar o aplicativo inteiro.

### RNF-05 - Observabilidade

- O sistema deve expor metricas Prometheus.
- Deve haver dashboards Grafana para portfolio, conectores, bots e alertas.
- Logs devem ser estruturados por conta, ativo e correlacao.

### RNF-06 - Desempenho

- Atualizacao de portfolio: ate 30 segundos para conectores centralizados.
- Abertura do dashboard principal: ate 3 segundos em condicoes normais.
- Consulta de historico recente: ate 2 segundos para janela de 7 dias.

### RNF-07 - Consistencia

- Eventos financeiros devem ser idempotentes.
- Divergencias entre saldo local e saldo remoto devem ser marcadas explicitamente.

### RNF-08 - Escalabilidade

- O modelo deve suportar novas moedas e novas exchanges sem refatorar a base.
- O processamento de sincronizacao deve ser assinado por conectores independentes.

### RNF-09 - Tecnologia

- A base principal do produto deve ser Python.
- O app deve trazer runtime Python isolado ou empacotado para evitar conflitos com o host.
- Dependencias nativas devem ser minimizadas para preservar a portabilidade do pendrive.

## 10. Arquitetura Proposta

### 10.1 Visao Geral

O aplicativo deve ser organizado em cinco blocos:

1. **Interface desktop local**
2. **Core da aplicacao em Python**
3. **Workers de sincronizacao**
4. **Camada de persistencia portatil**
5. **Motor de risco, integracao e observabilidade**

Nao ha frontend web como premissa do produto. Grafana e outros paineis externos permanecem como apoio operacional, nao como interface principal do usuario.

### 10.2 Reaproveitamento do repositorio atual

A implementacao deve aproveitar:

- `btc_trading_agent/` como fonte de integracao com trading e KuCoin
- PostgreSQL como fonte operacional principal quando disponivel
- exporters Prometheus ja existentes
- dashboards Grafana ja existentes como apoio de observabilidade
- Telegram para notificacoes operacionais

### 10.3 Separacao de responsabilidades

- **Interface desktop:** portfolio, ordens, alertas, configuracao e operacao.
- **Core Python:** autenticacao, autorizacao, consolidacao, auditoria e regras de negocio.
- **Workers:** sincronizacao com exchange, enriquecimento de dados e reconciliacao.
- **Persistencia portatil:** configuracao, logs, cache local e exportacoes no pendrive.
- **Integracao e observabilidade:** metricas, notificacoes, traces, eventos de saude e conectores auxiliares.

### 10.4 Stack Tecnica Recomendada

- `Python 3.12+` como base da aplicacao
- `PySide6` para interface desktop multiplataforma
- `httpx` para conectores HTTP com exchanges e servicos
- `pydantic` para contratos de configuracao e validacao
- `SQLAlchemy` ou camada equivalente para acesso a dados operacionais
- `PyInstaller` ou `Nuitka` para empacotamento por sistema operacional

### 10.5 Estrutura Sugerida do Pendrive

```text
/CryptoManager/
  /windows/
  /linux/
  /macos/
  /app/
  /config/
  /data/
  /logs/
  /exports/
```

Diretrizes:

- `windows/`, `linux/` e `macos/` contem launchers e binarios especificos.
- `app/` contem o codigo Python compartilhado.
- `config/`, `data/`, `logs/` e `exports/` armazenam dados operacionais portateis.

## 11. Modelo de Dados Minimo

Entidades principais:

- `user`
- `role`
- `account`
- `asset`
- `portfolio_snapshot`
- `balance_snapshot`
- `order`
- `trade`
- `transfer`
- `deposit`
- `withdrawal`
- `bot_instance`
- `strategy_profile`
- `risk_policy`
- `alert_rule`
- `alert_event`
- `audit_event`

Campos chave esperados:

- `account.id`, `account.type`, `account.provider`, `account.mode`
- `asset.symbol`, `asset.base_currency`, `asset.quote_currency`, `asset.network`
- `trade.symbol`, `trade.side`, `trade.price`, `trade.size`, `trade.pnl`
- `bot_instance.symbol`, `bot_instance.profile`, `bot_instance.mode`, `bot_instance.health`
- `audit_event.actor`, `audit_event.action`, `audit_event.target`, `audit_event.result`

## 12. Integracoes Prioritarias

### Fase inicial

- KuCoin
- Telegram
- sistema de arquivos do pendrive
- PostgreSQL
- Prometheus
- Grafana

### Fase seguinte

- Binance
- Coinbase
- wallets on-chain em modo leitura
- webhooks externos
- modulo fiscal/exportacao contabil

## 13. Fluxos Criticos

### 13.1 Onboarding de conta

1. Administrador cadastra a conta.
2. Sistema valida conectividade em modo leitura.
3. Sistema importa ativos suportados.
4. Conta entra em estado `active_read_only`.

### 13.2 Inicializacao em maquina hospedeira

1. Usuario conecta o pendrive.
2. Usuario executa o launcher do sistema correspondente.
3. O app inicializa o runtime Python local e carrega os caminhos do pendrive.
4. O app valida configuracoes, segredos e conectores disponiveis.
5. A interface desktop e aberta sem exigir navegador.

### 13.3 Venda manual protegida

1. Operador seleciona ativo e conta.
2. Sistema mostra saldo disponivel, preco e impacto estimado.
3. Operador confirma a ordem.
4. Se a politica exigir, `risk_manager` aprova.
5. Ordem e enviada.
6. Resultado e auditado e notificado.

### 13.4 Pausa de bot por risco

1. Sistema detecta drawdown acima do limite.
2. Circuit breaker muda a instancia para `paused`.
3. Operador recebe alerta.
4. Liberacao posterior exige evento auditado.

## 14. MVP Recomendado

### MVP-1 - App portatil e visibilidade

- launchers para Windows, Linux e macOS
- runtime Python empacotado
- login e perfis
- conexao KuCoin em modo leitura
- dashboard desktop consolidado
- historico de ordens e trades
- status de bots por moeda
- alertas Telegram
- auditoria basica

### MVP-2 - Operacao controlada

- compra e venda manual
- pausar e retomar bots
- politicas de risco configuraveis
- aprovacoes para acoes sensiveis

### MVP-3 - Expansao multi-canal

- novas exchanges
- wallets on-chain
- relatorios financeiros avancados
- rebalanceamento de portfolio

## 15. Criterios de Aceite do MVP-1

- O sistema consolida BTC e pelo menos outras 5 moedas suportadas no repositorio.
- O app executa a partir do pendrive em todos os sistemas operacionais suportados.
- O app nao depende de navegador para a interface principal.
- O usuario consegue ver patrimonio total e composicao por conta e ativo.
- O sistema mostra status das instancias de bot por moeda.
- Toda acao administrativa gera evento de auditoria consultavel.
- Alertas criticos chegam por Telegram.
- Falha de um conector nao derruba a consulta das demais contas.

## 16. Decisoes em Aberto

- O produto sera single-tenant ou multi-tenant?
- O MVP tera permissao de trade logo no inicio ou apenas modo leitura?
- Saques serao suportados ou apenas monitorados?
- O valor de referencia principal sera USDT, BRL ou ambos?
- O modulo fiscal sera nativo ou exportado para ferramenta externa?

## 17. Direcao Tecnica Recomendada

Para este repositorio, a melhor direcao e tratar o novo produto como **app desktop portatil em Python**, distribuido em pendrive, operando como camada superior de controle sobre a infraestrutura multi-coin ja existente. Isso reduz risco, reaproveita o legado de trading e permite evoluir por fases:

1. primeiro entregar a base portatil multisistema e a consolidacao de dados
2. depois habilitar operacao manual controlada e guardrails
3. por fim expandir automacao, relatorios e integracoes

## 18. Referencias Internas

- `docs/MULTI_COIN_TRADING_INFRASTRUCTURE.md`
- `docs/TRADING_RUNTIME_SELFHEAL.md`
- `docs/INVESTMENTS.md`
- `btc_trading_agent/`
