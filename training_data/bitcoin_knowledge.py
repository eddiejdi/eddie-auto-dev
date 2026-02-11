#!/usr/bin/env python3
"""
Treinamento RAG - Especialista em Bitcoin
Indexa conhecimento profundo sobre Bitcoin no sistema RAG
"""

import requests
import json
from datetime import datetime

# Configurações
RAG_API = "http://192.168.15.2:8001/api/v1"
TODAY = datetime.now().strftime("%Y-%m-%d")

# =============================================================================
# BASE DE CONHECIMENTO BITCOIN
# =============================================================================

BITCOIN_KNOWLEDGE = [
    # =========================================================================
    # FUNDAMENTOS DO BITCOIN
    # =========================================================================
    {
        "topic": "O que é Bitcoin",
        "question": "O que é Bitcoin e como funciona?",
        "answer": """Bitcoin (BTC) é uma criptomoeda descentralizada criada em 2008 por uma pessoa ou grupo usando o pseudônimo Satoshi Nakamoto. Foi introduzida em um whitepaper intitulado "Bitcoin: A Peer-to-Peer Electronic Cash System".

**Características Principais:**
- **Descentralizado**: Não é controlado por nenhum governo, banco ou entidade central
- **Peer-to-peer**: Transações diretas entre usuários sem intermediários
- **Limitado**: Apenas 21 milhões de bitcoins serão criados
- **Transparente**: Todas as transações são públicas na blockchain
- **Imutável**: Transações confirmadas não podem ser alteradas

**Como Funciona:**
1. Transações são agrupadas em blocos
2. Mineradores competem para validar blocos (Proof of Work)
3. O minerador vencedor adiciona o bloco à blockchain
4. A rede verifica e aceita o novo bloco
5. Transações são confirmadas permanentemente

O primeiro bloco (Genesis Block) foi minerado em 3 de janeiro de 2009, contendo a mensagem: "The Times 03/Jan/2009 Chancellor on brink of second bailout for banks"."""
    },
    {
        "topic": "Satoshi Nakamoto",
        "question": "Quem é Satoshi Nakamoto, o criador do Bitcoin?",
        "answer": """Satoshi Nakamoto é o pseudônimo usado pelo criador (ou criadores) do Bitcoin. A identidade real permanece desconhecida até hoje.

**Linha do Tempo:**
- **Agosto 2008**: Registrou o domínio bitcoin.org
- **Outubro 2008**: Publicou o whitepaper do Bitcoin
- **Janeiro 2009**: Minerou o primeiro bloco (Genesis Block)
- **2010-2011**: Comunicou-se via fóruns e emails
- **Abril 2011**: Última comunicação conhecida

**Fatos Conhecidos:**
- Estima-se que possua cerca de 1 milhão de bitcoins (nunca movidos)
- Escrevia em inglês britânico
- Padrões de horário sugerem fuso horário americano ou europeu
- Demonstrou conhecimento profundo de criptografia e economia

**Teorias sobre Identidade:**
Várias pessoas foram especuladas como Satoshi, incluindo Hal Finney, Nick Szabo, Craig Wright e outros, mas nenhuma confirmação foi obtida."""
    },
    {
        "topic": "Whitepaper Bitcoin",
        "question": "O que diz o whitepaper do Bitcoin?",
        "answer": """O whitepaper "Bitcoin: A Peer-to-Peer Electronic Cash System" é o documento fundacional do Bitcoin, publicado em 31 de outubro de 2008.

**Principais Conceitos do Whitepaper:**

1. **Problema**: Sistema financeiro tradicional depende de terceiros confiáveis
2. **Solução**: Sistema de pagamento eletrônico baseado em prova criptográfica

**Seções do Documento:**
- **Transações**: Cadeia de assinaturas digitais
- **Timestamp Server**: Servidor de marca temporal distribuído
- **Proof-of-Work**: Mecanismo para alcançar consenso
- **Rede**: Como os nós operam e se comunicam
- **Incentivo**: Recompensas para mineradores
- **Espaço em Disco**: Poda de transações antigas
- **Verificação Simplificada**: SPV para clientes leves
- **Combinação e Divisão de Valor**: Gestão de UTXOs
- **Privacidade**: Modelo de privacidade do Bitcoin
- **Cálculos**: Probabilidade de ataque

O documento tem apenas 9 páginas e permanece relevante como referência técnica fundamental."""
    },
    
    # =========================================================================
    # BLOCKCHAIN E TECNOLOGIA
    # =========================================================================
    {
        "topic": "Blockchain Bitcoin",
        "question": "Como funciona a blockchain do Bitcoin?",
        "answer": """A blockchain do Bitcoin é um livro-razão distribuído e imutável que registra todas as transações.

**Estrutura de um Bloco:**
- **Block Header (80 bytes)**:
  - Versão do software
  - Hash do bloco anterior
  - Merkle Root (hash de todas as transações)
  - Timestamp
  - Difficulty Target (nBits)
  - Nonce

- **Corpo do Bloco**:
  - Contador de transações
  - Lista de transações

**Características:**
- **Tamanho do bloco**: ~1-4 MB (com SegWit)
- **Tempo entre blocos**: ~10 minutos em média
- **Ajuste de dificuldade**: A cada 2.016 blocos (~2 semanas)
- **Algoritmo de hash**: SHA-256

**Merkle Tree:**
As transações são organizadas em uma árvore de Merkle, permitindo verificação eficiente (SPV - Simplified Payment Verification) sem baixar toda a blockchain.

**Consenso:**
A cadeia mais longa (com mais trabalho acumulado) é considerada a válida. Isso previne ataques de gasto duplo."""
    },
    {
        "topic": "Proof of Work",
        "question": "O que é Proof of Work (PoW) no Bitcoin?",
        "answer": """Proof of Work (Prova de Trabalho) é o mecanismo de consenso do Bitcoin que garante a segurança da rede.

**Como Funciona:**
1. Mineradores coletam transações pendentes
2. Criam um bloco candidato
3. Tentam encontrar um nonce que produza um hash abaixo do target
4. O primeiro a encontrar transmite o bloco para a rede
5. Outros nós verificam e aceitam o bloco

**Processo de Mineração:**
Hash(Block Header) < Target
- O hash deve começar com certo número de zeros
- Quanto mais zeros necessários, maior a dificuldade
- Mineradores testam bilhões de nonces por segundo

**Propriedades do PoW:**
- **Assimétrico**: Difícil de produzir, fácil de verificar
- **Ajustável**: Dificuldade se adapta ao hashrate da rede
- **Custoso**: Requer energia e hardware especializado
- **Seguro**: Atacar a rede exigiria 51%+ do hashrate mundial

**Consumo de Energia:**
O Bitcoin usa aproximadamente 100-150 TWh/ano, comparável ao consumo de alguns países. Debate sobre sustentabilidade continua."""
    },
    {
        "topic": "UTXO Model",
        "question": "O que é o modelo UTXO do Bitcoin?",
        "answer": """UTXO (Unspent Transaction Output) é o modelo contábil do Bitcoin, diferente do modelo de contas usado em bancos tradicionais.

**Conceito:**
- Não existem "saldos" no Bitcoin, apenas UTXOs
- Cada UTXO é uma "moeda" indivisível que pode ser gasta uma vez
- Quando você gasta, consome UTXOs inteiros e cria novos

**Exemplo:**
Se você tem um UTXO de 1 BTC e quer enviar 0.3 BTC:
1. Sua transação consome o UTXO de 1 BTC (input)
2. Cria dois novos UTXOs (outputs):
   - 0.3 BTC para o destinatário
   - 0.699 BTC de troco para você
   - 0.001 BTC vai como taxa para o minerador

**Vantagens do UTXO:**
- **Paralelização**: Transações independentes podem ser processadas simultaneamente
- **Privacidade**: Facilita uso de endereços diferentes
- **Verificação**: Fácil provar que uma moeda não foi gasta
- **Simplicidade**: Estado da rede é conjunto de UTXOs

**UTXO Set:**
O conjunto de todos os UTXOs não gastos (atualmente ~80-100 milhões) que os nós mantêm na memória para validação rápida."""
    },
    {
        "topic": "Transações Bitcoin",
        "question": "Como funcionam as transações de Bitcoin?",
        "answer": """Uma transação Bitcoin transfere valor de inputs (UTXOs existentes) para outputs (novos UTXOs).

**Estrutura de uma Transação:**
- **Version**: Versão do formato
- **Inputs**: UTXOs sendo gastos
  - TXID do UTXO anterior
  - Index do output
  - ScriptSig (assinatura desbloqueando o UTXO)
- **Outputs**: Novos UTXOs criados
  - Valor em satoshis
  - ScriptPubKey (condições para gastar)
- **Locktime**: Quando a transação pode ser minerada

**Tipos de Scripts Comuns:**
- **P2PKH** (Pay-to-Public-Key-Hash): Endereços começando com "1"
- **P2SH** (Pay-to-Script-Hash): Endereços começando com "3"
- **P2WPKH** (SegWit nativo): Endereços começando com "bc1q"
- **P2TR** (Taproot): Endereços começando com "bc1p"

**Taxas:**
- Taxa = (Inputs - Outputs)
- Medidas em sat/vByte (satoshis por byte virtual)
- Transações com taxas maiores são priorizadas

**Confirmações:**
- 0 confirmações: Não minerada (mempool)
- 1 confirmação: Incluída em um bloco
- 6+ confirmações: Considerada irreversível para valores altos"""
    },
    
    # =========================================================================
    # MINERAÇÃO
    # =========================================================================
    {
        "topic": "Mineração Bitcoin",
        "question": "Como funciona a mineração de Bitcoin?",
        "answer": """Mineração é o processo de validar transações e adicionar novos blocos à blockchain, sendo recompensado com bitcoins novos.

**Processo:**
1. Mineradores coletam transações da mempool
2. Constroem um bloco candidato
3. Competem para encontrar um hash válido (PoW)
4. Vencedor transmite o bloco
5. Rede valida e aceita o bloco

**Hardware de Mineração (Evolução):**
- **2009-2010**: CPUs (computadores comuns)
- **2010-2013**: GPUs (placas de vídeo)
- **2013-2014**: FPGAs
- **2014-presente**: ASICs (hardware especializado)

**ASICs Modernos (2024-2025):**
- Hashrate: 100-400+ TH/s por unidade
- Consumo: 3.000-4.000W
- Eficiência: ~20-30 J/TH
- Custo: $2.000-$15.000

**Pools de Mineração:**
Como a mineração solo é quase impossível, mineradores se unem em pools:
- Foundry USA, AntPool, F2Pool, Binance Pool
- Recompensas divididas proporcionalmente ao hashrate contribuído

**Hashrate Global:**
A rede Bitcoin processa ~400-600 EH/s (Exahashes por segundo), equivalente a quintilhões de cálculos por segundo."""
    },
    {
        "topic": "Halving Bitcoin",
        "question": "O que é o halving do Bitcoin e quando ocorre?",
        "answer": """O halving (ou halvening) é a redução pela metade da recompensa de mineração, programada para ocorrer a cada 210.000 blocos (~4 anos).

**Histórico de Halvings:**
| Halving | Data | Bloco | Recompensa |
|---------|------|-------|------------|
| Gênese | Jan 2009 | 0 | 50 BTC |
| 1º | Nov 2012 | 210.000 | 25 BTC |
| 2º | Jul 2016 | 420.000 | 12.5 BTC |
| 3º | Mai 2020 | 630.000 | 6.25 BTC |
| 4º | Abr 2024 | 840.000 | 3.125 BTC |
| 5º | ~2028 | 1.050.000 | 1.5625 BTC |

**Impacto Econômico:**
- Reduz a emissão de novos bitcoins
- Historicamente precedeu grandes altas de preço
- Cria escassez programática (deflação)

**Último Bitcoin:**
- O último satoshi será minerado por volta de 2140
- Total: exatamente 20.999.999,9769 BTC
- Após isso, mineradores ganharão apenas taxas de transação

**Por que Halving Importa:**
- Controle de inflação predeterminado
- Diferente de moedas fiduciárias com emissão ilimitada
- Modelo econômico transparente e previsível"""
    },
    {
        "topic": "Dificuldade Mineração",
        "question": "Como funciona o ajuste de dificuldade na mineração de Bitcoin?",
        "answer": """O ajuste de dificuldade garante que blocos sejam minerados aproximadamente a cada 10 minutos, independentemente do hashrate total da rede.

**Mecanismo:**
- Ajuste a cada 2.016 blocos (~2 semanas)
- Baseado no tempo real vs tempo esperado (20.160 minutos)
- Fórmula: Nova Dificuldade = Antiga × (Tempo Real / 20.160 min)

**Limites:**
- Máximo aumento: 4× (300%)
- Máximo redução: ÷4 (75%)
- Previne mudanças muito bruscas

**Exemplo:**
Se 2.016 blocos foram minerados em 10 dias (ao invés de 14):
- A rede está muito rápida
- Dificuldade aumenta ~40%
- Próximos blocos levarão mais tempo

**Target e Dificuldade:**
- Target: número máximo que o hash deve estar abaixo
- Dificuldade: medida relativa ao target mais fácil possível
- Dificuldade atual (2025): ~75-90 trilhões

**Importância:**
- Mantém emissão de bitcoins previsível
- Adapta-se automaticamente a mudanças de hashrate
- Garante estabilidade do sistema"""
    },
    
    # =========================================================================
    # CARTEIRAS E SEGURANÇA
    # =========================================================================
    {
        "topic": "Carteiras Bitcoin",
        "question": "Quais são os tipos de carteiras Bitcoin?",
        "answer": """Carteiras Bitcoin armazenam as chaves privadas que controlam seus bitcoins. Existem vários tipos:

**1. Hot Wallets (Conectadas à Internet):**
- **Mobile**: Apps para smartphone (BlueWallet, Muun)
- **Desktop**: Software para computador (Electrum, Sparrow)
- **Web**: Acessíveis via navegador (não recomendado para valores altos)
- **Exchange**: Custódia em corretoras (você não controla as chaves)

**2. Cold Wallets (Offline - Mais Seguras):**
- **Hardware Wallets**: Dispositivos dedicados (Ledger, Trezor, Coldcard)
- **Paper Wallets**: Chaves impressas em papel
- **Steel Wallets**: Seed gravada em metal (resistente a fogo/água)
- **Air-gapped**: Computadores nunca conectados à internet

**3. Multi-signature (Multisig):**
- Requer múltiplas chaves para gastar (ex: 2-de-3)
- Maior segurança contra roubo ou perda
- Usado por empresas e hodlers sérios

**Recomendações por Valor:**
- Pequenas quantias: Hot wallet no celular
- Valores médios: Hardware wallet
- Valores altos: Multisig com backups distribuídos

**Regra de Ouro:**
"Not your keys, not your coins" - Se você não controla as chaves privadas, você não possui realmente os bitcoins."""
    },
    {
        "topic": "Seed Phrase",
        "question": "O que é seed phrase (frase de recuperação) no Bitcoin?",
        "answer": """Seed phrase (também chamada de mnemonic ou frase de recuperação) são 12-24 palavras que representam sua chave privada mestre.

**Padrão BIP-39:**
- Lista de 2.048 palavras em inglês (ou outros idiomas)
- 12 palavras = 128 bits de entropia
- 24 palavras = 256 bits de entropia
- Última palavra inclui checksum

**Exemplo de Seed (NUNCA use esta):**
abandon abandon abandon abandon abandon abandon
abandon abandon abandon abandon abandon about
**Derivação de Chaves (BIP-32/44/84/86):**
Da seed são derivadas infinitas chaves privadas/públicas:
- m/84'/0'/0'/0/0 → Primeiro endereço SegWit
- m/84'/0'/0'/0/1 → Segundo endereço
- E assim por diante...

**Segurança da Seed:**
- NUNCA digite online ou em dispositivos conectados
- NUNCA fotografe ou armazene digitalmente
- Guarde em local seguro (cofre, caixa de depósito)
- Considere dividir em partes (Shamir Backup)
- Faça backup em metal para resistir a desastres

**Passphrase Opcional (25ª palavra):**
- Adiciona camada extra de segurança
- Cria carteira completamente diferente
- Útil para "plausible deniability"

**Perda da Seed = Perda dos Bitcoins!**
Estima-se que 3-4 milhões de BTC foram perdidos permanentemente por seeds perdidas."""
    },
    {
        "topic": "Segurança Bitcoin",
        "question": "Como manter meus bitcoins seguros?",
        "answer": """A segurança do Bitcoin depende 100% de você. Aqui estão as melhores práticas:

**Níveis de Segurança:**

**Nível 1 - Básico:**
- Use carteira própria (não deixe em exchange)
- Ative 2FA em todas as contas
- Mantenha software atualizado
- Use senhas fortes e únicas

**Nível 2 - Intermediário:**
- Hardware wallet para valores significativos
- Backup da seed em metal
- Verifique endereços antes de enviar
- Use endereços novos para cada transação

**Nível 3 - Avançado:**
- Multisig (2-de-3 ou 3-de-5)
- Air-gapped signing
- Distribuição geográfica de backups
- Passphrase adicional na seed

**Ameaças Comuns:**
- **Phishing**: Sites/emails falsos pedindo seed
- **Malware**: Vírus que alteram endereços de destino
- **SIM Swap**: Atacante clona seu número de telefone
- **Engenharia Social**: Golpes de suporte técnico
- **Ataque físico**: Roubo sob coerção ($5 wrench attack)

**Regras de Ouro:**
1. Nunca compartilhe sua seed phrase
2. Verifique endereços caractere por caractere
3. Teste com pequenas quantias primeiro
4. Desconfie de "oportunidades" e urgência
5. Mantenha privacidade sobre quanto possui"""
    },
    
    # =========================================================================
    # UPGRADES E MELHORIAS
    # =========================================================================
    {
        "topic": "SegWit",
        "question": "O que é SegWit (Segregated Witness) no Bitcoin?",
        "answer": """SegWit (Segregated Witness) foi um soft fork ativado em agosto de 2017 que separou dados de assinatura do corpo principal da transação.

**Problema Resolvido:**
- **Transaction Malleability**: Possibilidade de alterar TXID sem invalidar
- **Limite de escalabilidade**: Blocos de 1MB eram insuficientes

**Como Funciona:**
- Dados de assinatura (witness) movidos para estrutura separada
- Witness data tem desconto de 75% no cálculo de tamanho
- Efetivamente aumenta capacidade para ~2-4MB por bloco

**Benefícios:**
1. **Mais transações por bloco**: ~2-4x mais capacidade
2. **Taxas menores**: Transações SegWit são mais baratas
3. **Lightning Network**: Habilitou canais de pagamento seguros
4. **Correção de malleability**: Permitiu contratos mais complexos

**Tipos de Endereço SegWit:**
- **P2SH-SegWit** (wrapped): Começa com "3"
- **Native SegWit** (bech32): Começa com "bc1q"

**Adoção:**
Em 2025, ~80-90% das transações usam SegWit, proporcionando economia significativa em taxas."""
    },
    {
        "topic": "Taproot",
        "question": "O que é Taproot e quais seus benefícios para o Bitcoin?",
        "answer": """Taproot foi um soft fork ativado em novembro de 2021 (bloco 709.632), trazendo melhorias significativas em privacidade, eficiência e funcionalidade.

**Componentes do Taproot:**

**1. Schnorr Signatures (BIP-340):**
- Substituem ECDSA para transações Taproot
- Permitem agregação de assinaturas
- Mais eficientes (64 bytes vs 71-72)
- Matematicamente mais simples e seguras

**2. Taproot (BIP-341):**
- Novo tipo de output: P2TR (Pay-to-Taproot)
- Endereços começam com "bc1p"
- Combina pagamento simples com scripts complexos

**3. Tapscript (BIP-342):**
- Nova linguagem de script
- Mais flexível para contratos futuros
- Facilita upgrades posteriores

**Benefícios:**
- **Privacidade**: Multisig parece igual a single-sig
- **Eficiência**: Menores taxas para transações complexas
- **Lightning Network**: Canais indistinguíveis de transações normais
- **Contratos inteligentes**: Base para funcionalidades avançadas

**Ordinals e Inscriptions:**
Taproot também habilitou os controversos Ordinals/Inscriptions (NFTs no Bitcoin), gerando debate na comunidade sobre uso de espaço de bloco."""
    },
    {
        "topic": "Lightning Network",
        "question": "O que é Lightning Network e como funciona?",
        "answer": """Lightning Network é uma solução de segunda camada (Layer 2) para Bitcoin que permite transações instantâneas e baratas.

**Problema que Resolve:**
- Bitcoin on-chain: ~7 transações/segundo
- Visa: ~65.000 transações/segundo
- Lightning: Milhões de transações/segundo

**Como Funciona:**

**1. Canais de Pagamento:**
- Dois usuários abrem um canal (transação on-chain)
- Depositam BTC no canal (funding transaction)
- Fazem transações ilimitadas off-chain entre si
- Fecham o canal quando quiserem (settlement on-chain)

**2. Roteamento:**
- Pagamentos são roteados através de múltiplos canais
- A→B→C: A paga C através de B
- HTLCs garantem atomicidade (tudo ou nada)
- Nós de roteamento ganham pequenas taxas

**Características:**
- **Instantâneo**: Milissegundos para confirmar
- **Barato**: Frações de centavo em taxas
- **Privado**: Transações não ficam na blockchain
- **Micropagamentos**: Viável enviar 1 satoshi

**Carteiras Lightning:**
- Phoenix, Muun, Breez (mobile)
- Core Lightning, LND (nós completos)

**Capacidade da Rede:**
- ~5.000+ BTC em capacidade pública
- ~15.000+ nós ativos
- ~70.000+ canais

Lightning é considerado essencial para Bitcoin como meio de pagamento do dia-a-dia."""
    },
    
    # =========================================================================
    # ECONOMIA E MERCADO
    # =========================================================================
    {
        "topic": "Escassez Bitcoin",
        "question": "Por que o Bitcoin tem valor e é considerado escasso?",
        "answer": """Bitcoin é a primeira forma de escassez digital absoluta, com propriedades monetárias superiores.

**Limite de 21 Milhões:**
- Codificado no protocolo desde o início
- Impossível de alterar sem consenso (improvável)
- ~19.5 milhões já minerados (2025)
- Último bitcoin por volta de 2140

**Comparação com Ouro:**
| Propriedade | Ouro | Bitcoin |
|-------------|------|---------|
| Escassez | Estimada | Verificável |
| Divisibilidade | Limitada | 100 milhões de partes |
| Portabilidade | Difícil | Instantânea global |
| Verificação | Requer especialista | Qualquer nó |
| Confiscabilidade | Física | Praticamente impossível |

**Stock-to-Flow:**
- Razão entre estoque existente e produção anual
- Bitcoin: ~50-60 (similar ao ouro)
- Após halvings, S2F aumenta (mais escasso)

**Bitcoins Perdidos:**
- Estimativa: 3-4 milhões BTC perdidos para sempre
- Aumenta escassez efetiva
- Não podem ser recuperados ou reemitidos

**Por que isso importa:**
- Reserva de valor resistente à inflação
- Política monetária previsível e transparente
- "Digital Gold" ou "Sound Money"
- Hedge contra desvalorização de moedas fiduciárias"""
    },
    {
        "topic": "Bitcoin ETFs",
        "question": "O que são Bitcoin ETFs e qual seu impacto?",
        "answer": """ETFs (Exchange-Traded Funds) de Bitcoin permitem exposição ao BTC através de bolsas de valores tradicionais.

**Tipos de ETFs:**

**1. ETFs de Futuros (aprovados em 2021):**
- Baseados em contratos futuros de Bitcoin
- Não detêm BTC diretamente
- Sofrem de "contango" (custos de rolagem)
- Exemplo: BITO (ProShares)

**2. Spot ETFs (aprovados em janeiro 2024):**
- Detêm Bitcoin real em custódia
- Preço acompanha mercado spot diretamente
- Mais eficientes que ETFs de futuros
- Exemplos: IBIT (BlackRock), FBTC (Fidelity), GBTC (Grayscale)

**Impacto dos Spot ETFs:**
- Bilhões em inflows nos primeiros meses
- Acesso facilitado para investidores tradicionais
- Adoção institucional acelerada
- Maior liquidez e legitimidade

**Vantagens para Investidores:**
- Custódia profissional
- Negociação em corretoras tradicionais
- Relatórios fiscais simplificados
- Sem necessidade de gerenciar carteiras

**Desvantagens:**
- Taxas de administração (0.2-1.5%)
- Não é "self-custody"
- Exposição apenas ao preço, não à tecnologia
- Risco de contraparte

Os Spot Bitcoin ETFs representaram um marco histórico na adoção institucional do Bitcoin."""
    },
    {
        "topic": "Ciclos de Mercado Bitcoin",
        "question": "Quais são os ciclos de mercado do Bitcoin?",
        "answer": """Bitcoin historicamente segue ciclos de aproximadamente 4 anos, correlacionados com os halvings.

**Fases do Ciclo:**

**1. Acumulação (Bear Market tardio):**
- Preços baixos após grande queda
- Baixo interesse público
- Holders acumulam
- Duração: 12-18 meses

**2. Alta Inicial (Bull Market inicial):**
- Preços começam a subir
- Interesse crescente
- Quebra de resistências importantes
- Duração: 6-12 meses

**3. Euforia (Bull Market tardio):**
- Crescimento parabólico
- FOMO intenso
- Mídia mainstream
- Novos ATHs frequentes
- Duração: 3-6 meses

**4. Crash e Capitulação:**
- Queda de 70-85% do topo
- Pânico e desespero
- "Bitcoin está morto" na mídia
- Duração: 6-12 meses

**Histórico de Ciclos:**
| Ciclo | Fundo | Topo | Ganho |
|-------|-------|------|-------|
| 1 | $0.01 | $31 | ~3.100% |
| 2 | $2 | $1.100 | ~55.000% |
| 3 | $200 | $20.000 | ~10.000% |
| 4 | $3.200 | $69.000 | ~2.000% |
| 5 | $15.500 | $100.000+ | ~700%+ |

**Observação:** Retornos diminuem a cada ciclo conforme market cap aumenta, mas volatilidade permanece alta."""
    },
    
    # =========================================================================
    # REGULAMENTAÇÃO E ADOÇÃO
    # =========================================================================
    {
        "topic": "Regulamentação Bitcoin",
        "question": "Como o Bitcoin é regulamentado no mundo?",
        "answer": """A regulamentação de Bitcoin varia significativamente entre países e continua evoluindo.

**Estados Unidos:**
- IRS: Tratado como propriedade (taxável)
- SEC: Não é security (commodity)
- CFTC: Commodity sob sua jurisdição
- Spot ETFs aprovados em 2024
- Estados têm regulações próprias

**União Europeia:**
- MiCA (Markets in Crypto Assets) em vigor desde 2023
- Framework regulatório unificado
- Requisitos para provedores de serviços
- Proteção ao consumidor

**Brasil:**
- Lei 14.478/2022 (Marco Legal das Criptomoedas)
- Banco Central como regulador
- Exchanges precisam de autorização
- Tributação sobre ganhos de capital

**Países Favoráveis:**
- El Salvador: Moeda de curso legal (2021)
- Suíça: "Crypto Valley" em Zug
- Portugal: Isenção fiscal (mudando)
- Emirados Árabes: Zona franca cripto

**Países Restritivos:**
- China: Banido (mineração e trading)
- Índia: Alta tributação e incerteza
- Rússia: Parcialmente restrito

**Tendências Globais:**
- Maior clareza regulatória
- Foco em compliance e KYC/AML
- Regulação de stablecoins
- CBDCs como resposta governamental"""
    },
    {
        "topic": "Adoção Institucional Bitcoin",
        "question": "Como está a adoção institucional do Bitcoin?",
        "answer": """A adoção institucional de Bitcoin acelerou significativamente desde 2020.

**Empresas com Bitcoin no Balanço:**
| Empresa | BTC | Valor (~$90k) |
|---------|-----|---------------|
| MicroStrategy | ~200.000+ | ~$18B+ |
| Tesla | ~10.000 | ~$900M |
| Block (Square) | ~8.000 | ~$720M |
| Marathon Digital | ~15.000+ | ~$1.3B+ |

**Instituições Financeiras:**
- **BlackRock**: Maior gestor de ativos, lançou IBIT
- **Fidelity**: Custódia e ETF (FBTC)
- **JPMorgan**: Acesso para clientes private
- **Goldman Sachs**: Mesa de trading cripto
- **Morgan Stanley**: Fundos para clientes qualificados

**Fundos e Investidores:**
- Fundos de pensão alocando 1-2%
- Family offices diversificando
- Hedge funds com exposição
- Fundos soberanos explorando

**Infraestrutura Institucional:**
- Custódia regulada (Coinbase Custody, BitGo)
- Prime brokerage (Galaxy, Genesis)
- Derivativos (CME, Deribit)
- Índices (Bloomberg, S&P)

**Marcos Importantes:**
- 2020: MicroStrategy inicia acumulação
- 2021: Tesla compra $1.5B em BTC
- 2021: El Salvador adota como moeda legal
- 2024: Spot ETFs aprovados nos EUA
- 2024-2025: Inflows bilionários em ETFs

A "institucionalização" do Bitcoin reduz volatilidade de longo prazo e aumenta legitimidade."""
    },
    
    # =========================================================================
    # CONCEITOS AVANÇADOS
    # =========================================================================
    {
        "topic": "Nós Bitcoin",
        "question": "O que são nós (nodes) Bitcoin e por que são importantes?",
        "answer": """Nós Bitcoin são computadores que mantêm cópia da blockchain e validam transações, sendo fundamentais para a descentralização.

**Tipos de Nós:**

**1. Full Node:**
- Mantém cópia completa da blockchain (~500GB+)
- Valida todas as regras de consenso
- Não precisa confiar em terceiros
- Exemplos: Bitcoin Core, Bitcoin Knots

**2. Pruned Node:**
- Full node que descarta blocos antigos
- Mantém apenas ~5-10GB
- Ainda valida tudo, apenas não armazena

**3. Light Node (SPV):**
- Baixa apenas headers dos blocos
- Confia em full nodes para validação
- Usado em carteiras mobile
- Menor segurança, mais conveniência

**4. Mining Node:**
- Full node + software de mineração
- Cria novos blocos
- Requer hardware especializado

**Por que Rodar um Full Node:**
- Soberania total sobre seus fundos
- Valida suas próprias transações
- Contribui para descentralização
- Vota em upgrades do protocolo
- Privacidade máxima

**Requisitos:**
- ~500GB+ de armazenamento
- ~2GB RAM
- Conexão de internet estável
- Hardware básico (Raspberry Pi funciona)

**Número de Nós:**
~15.000-20.000 full nodes públicos, mas muitos mais privados. Quanto mais nós, mais resistente a ataques."""
    },
    {
        "topic": "Ataque 51%",
        "question": "O que é um ataque de 51% no Bitcoin?",
        "answer": """Um ataque de 51% ocorre quando uma entidade controla mais da metade do hashrate da rede, podendo manipular a blockchain.

**O que o Atacante Pode Fazer:**
- Gastar os mesmos bitcoins duas vezes (double spend)
- Impedir confirmação de transações específicas
- Reverter transações recentes (dele próprio)

**O que o Atacante NÃO Pode Fazer:**
- Criar bitcoins do nada
- Roubar bitcoins de outros
- Alterar transações antigas (muito custoso)
- Mudar regras de consenso

**Por que é Improvável no Bitcoin:**

**Custo Proibitivo:**
- Hashrate atual: ~500-600 EH/s
- Custo do hardware: Dezenas de bilhões de dólares
- Custo de energia: Centenas de milhões/mês
- Logística: Impossível obter tanto hardware

**Incentivos Econômicos:**
- Atacante destruiria valor do próprio investimento
- Preço do BTC despencaria
- Hardware ficaria sem utilidade
- Mais lucrativo minerar honestamente

**Defesas:**
- Esperar mais confirmações para valores altos
- Monitoramento de reorganizações
- Descentralização geográfica de mineradores

**Ataques Bem-Sucedidos:**
- Bitcoin nunca sofreu ataque 51%
- Altcoins menores são vulneráveis (Bitcoin Gold, Ethereum Classic)

Na prática, o Bitcoin é considerado seguro contra este tipo de ataque devido ao custo astronômico necessário."""
    },
    {
        "topic": "Privacidade Bitcoin",
        "question": "Bitcoin é anônimo? Como funciona a privacidade?",
        "answer": """Bitcoin é pseudônimo, não anônimo. Todas as transações são públicas, mas não diretamente ligadas a identidades.

**Modelo de Privacidade:**
- Endereços são pseudônimos (strings alfanuméricas)
- Transações são públicas e rastreáveis
- Análise de blockchain pode desanonimizar

**Riscos à Privacidade:**
- **Exchanges KYC**: Ligam identidade a endereços
- **Reutilização de endereços**: Facilita rastreamento
- **Análise de clustering**: Agrupa endereços do mesmo dono
- **Dust attacks**: Pequenas quantias para rastrear

**Técnicas de Privacidade:**

**Básicas:**
- Usar novo endereço para cada transação
- Não reutilizar endereços
- Rodar próprio full node

**Intermediárias:**
- CoinJoin: Mistura transações de múltiplos usuários
- PayJoin: Receptor participa da transação
- Lightning Network: Transações off-chain

**Avançadas:**
- Wasabi Wallet: CoinJoin integrado
- JoinMarket: Mercado de CoinJoin
- Samourai Wallet: Múltiplas ferramentas de privacidade

**Limitações:**
- Privacidade perfeita é muito difícil
- Metadados ainda podem revelar informações
- Reguladores pressionam por compliance

**Taproot Improvement:**
Todas as transações Taproot parecem iguais (single-sig, multisig, Lightning), melhorando privacidade base."""
    },
    {
        "topic": "Bitcoin vs Altcoins",
        "question": "Qual a diferença entre Bitcoin e outras criptomoedas (altcoins)?",
        "answer": """Bitcoin foi a primeira criptomoeda e permanece única em vários aspectos importantes.

**Por que Bitcoin é Diferente:**

**1. Descentralização:**
- Nenhum fundador/empresa controlando
- Satoshi desapareceu
- Desenvolvimento distribuído
- Maior número de nós

**2. Segurança:**
- Maior hashrate do mundo
- Nunca foi hackeado
- Código auditado por 15+ anos
- Modelo conservador de upgrades

**3. Efeito de Rede:**
- Maior liquidez
- Maior adoção
- Infraestrutura mais madura
- Reconhecimento de marca

**4. Política Monetária:**
- 21 milhões fixos
- Schedule de emissão imutável
- Sem "pré-mine" ou alocação para fundadores

**Altcoins Notáveis:**
| Moeda | Propósito | Trade-off |
|-------|-----------|-----------|
| Ethereum | Smart contracts | Menos descentralizado |
| Litecoin | Pagamentos rápidos | Menor segurança |
| Monero | Privacidade | Regulação adversa |
| Stablecoins | Paridade USD | Centralizado |

**Críticas às Altcoins:**
- Muitas são "securities" disfarçadas
- Pré-mines beneficiam fundadores
- Menos testadas e auditadas
- Frequentemente centralizadas

**Visão Maximalista:**
Bitcoin é a única criptomoeda verdadeiramente descentralizada e segura. Altcoins são experimentos ou golpes.

**Visão Multichain:**
Diferentes blockchains servem diferentes propósitos. Bitcoin é reserva de valor, outros têm utilidades específicas."""
    },
    {
        "topic": "Futuro do Bitcoin",
        "question": "Qual o futuro do Bitcoin?",
        "answer": """O futuro do Bitcoin envolve desenvolvimentos técnicos, adoção crescente e evolução do ecossistema.

**Desenvolvimentos Técnicos Esperados:**

**1. Escalabilidade:**
- Lightning Network mais madura
- Federated sidechains (Liquid)
- Possíveis novos Layer 2s
- Otimizações de protocolo

**2. Privacidade:**
- Maior adoção de Taproot
- CoinJoin mais acessível
- Possíveis novos soft forks

**3. Funcionalidade:**
- Contratos mais complexos via Tapscript
- DLCs (Discrete Log Contracts)
- Vaults nativos (propostas OP_VAULT)

**Cenários de Adoção:**

**Otimista:**
- Reserva de valor global
- Moeda de países emergentes
- Base do sistema financeiro digital
- Preço: $500k-$1M+

**Moderado:**
- "Ouro digital" estabelecido
- Alocação padrão em portfólios (1-5%)
- Pagamentos via Lightning mainstream
- Preço: $150k-$300k

**Pessimista:**
- Regulação hostil
- Competição de CBDCs
- Perda de relevância
- Preço: Estagnação ou queda

**Desafios:**
- Consumo de energia (solução: energia renovável)
- Escalabilidade (solução: Layer 2)
- Regulação (solução: compliance e advocacy)
- Usabilidade (solução: melhores UIs)

**Tese de Longo Prazo:**
Bitcoin representa a separação do dinheiro do Estado, assim como a separação da Igreja do Estado foi revolucionária. Se bem-sucedido, pode ser a inovação monetária mais importante em séculos."""
    },
]

def check_rag_health():
    """Verifica se o RAG está online"""
    try:
        r = requests.get(f"{RAG_API.replace('/api/v1', '')}/health", timeout=10)
        print(f"✅ RAG Health: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"❌ RAG offline: {e}")
        return False

def index_knowledge():
    """Indexa conhecimento Bitcoin no RAG"""
    
    print(f"\n{'='*60}")
    print(f"🪙 TREINAMENTO RAG - ESPECIALISTA BITCOIN")
    print(f"{'='*60}")
    print(f"📅 Data: {TODAY}")
    print(f"📚 Total de tópicos: {len(BITCOIN_KNOWLEDGE)}")
    
    if not check_rag_health():
        print("⚠️ Tentando continuar mesmo assim...")
    
    documents = []
    
    for i, item in enumerate(BITCOIN_KNOWLEDGE):
        doc = {
            "id": f"bitcoin_{TODAY}_{i:04d}",
            "content": f"## {item['topic']}\n\n### Pergunta:\n{item['question']}\n\n### Resposta:\n{item['answer']}",
            "metadata": {
                "type": "bitcoin_knowledge",
                "topic": item['topic'],
                "source": "bitcoin_training",
                "date": TODAY,
                "language": "pt-br",
                "category": "cryptocurrency"
            }
        }
        documents.append(doc)
    
    print(f"\n📤 Indexando {len(documents)} documentos no RAG...")
    
    # Indexar em lotes
    batch_size = 5
    success_count = 0
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        
        try:
            response = requests.post(
                f"{RAG_API}/rag/index",
                json={
                    "documents": batch,
                    "collection": "bitcoin_knowledge"
                },
                timeout=60
            )
            
            if response.status_code == 200:
                success_count += len(batch)
                topics = [d['metadata']['topic'] for d in batch]
                print(f"  ✅ Batch {i//batch_size + 1}: {', '.join(topics)}")
            else:
                # Tentar collection default
                response2 = requests.post(
                    f"{RAG_API}/rag/index",
                    json={
                        "documents": batch,
                        "collection": "default"
                    },
                    timeout=60
                )
                if response2.status_code == 200:
                    success_count += len(batch)
                    print(f"  ✅ Batch {i//batch_size + 1}: Indexado em 'default'")
                else:
                    print(f"  ⚠️ Batch {i//batch_size + 1}: Status {response.status_code}")
                    
        except Exception as e:
            print(f"  ❌ Erro no batch {i//batch_size + 1}: {e}")
    
    return success_count

def test_knowledge():
    """Testa se o conhecimento foi indexado"""
    
    print(f"\n{'='*60}")
    print("🔍 TESTANDO CONHECIMENTO INDEXADO")
    print(f"{'='*60}")
    
    test_queries = [
        "O que é Bitcoin?",
        "Como funciona o halving?",
        "O que é Lightning Network?",
        "Quem é Satoshi Nakamoto?",
        "Como funciona a mineração de Bitcoin?"
    ]
    
    for query in test_queries:
        try:
            response = requests.post(
                f"{RAG_API}/rag/search",
                json={
                    "query": query,
                    "collection": "bitcoin_knowledge",
                    "n_results": 1
                },
                timeout=30
            )
            
            if response.status_code == 200:
                results = response.json()
                if results.get('results'):
                    topic = results['results'][0].get('metadata', {}).get('topic', 'N/A')
                    print(f"  ✅ '{query}' → {topic}")
                else:
                    print(f"  ⚠️ '{query}' → Sem resultados")
            else:
                print(f"  ❌ '{query}' → Erro {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ '{query}' → {e}")

def main():
    """Função principal"""
    
    # Indexar conhecimento
    indexed = index_knowledge()
    
    # Testar
    test_knowledge()
    
    print(f"\n{'='*60}")
    print("🎉 TREINAMENTO CONCLUÍDO!")
    print(f"{'='*60}")
    print(f"📊 Documentos indexados: {indexed}/{len(BITCOIN_KNOWLEDGE)}")
    print(f"\n💡 Seu RAG agora é especialista em Bitcoin!")
    print(f"   Pergunte sobre: blockchain, mineração, halving, carteiras,")
    print(f"   segurança, Lightning Network, Taproot, ETFs, e muito mais!")

if __name__ == "__main__":
    main()
