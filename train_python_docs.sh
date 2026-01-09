#!/bin/bash
# ============================================================================
# Script de Treinamento de IAs com Documentação Python Completa
# Autor: Copilot | Data: Janeiro 2026
# ============================================================================

set -e

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║   🐍 TREINAMENTO DE IAs COM DOCUMENTAÇÃO PYTHON COMPLETA 🐍        ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Diretório para armazenar a documentação
DOCS_DIR="$HOME/python_docs_training"
LOG_FILE="/tmp/python_training_$(date +%Y%m%d_%H%M%S).log"

# Modelos disponíveis no servidor Ollama
declare -a MODELOS=("qwen2.5-coder:1.5b" "qwen2.5-coder:7b" "deepseek-coder-v2:16b" "codestral:22b")

# ============================================================================
# PARTE 1: BAIXAR DOCUMENTAÇÃO PYTHON
# ============================================================================

echo "📥 FASE 1: Baixando Documentação Python Oficial..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mkdir -p "$DOCS_DIR"
cd "$DOCS_DIR"

# Baixar documentação HTML do Python 3.12 (última versão estável)
if [ ! -f "python-3.12.8-docs-html.tar.bz2" ]; then
    echo "⬇️  Baixando documentação Python 3.12..."
    wget -q --show-progress https://docs.python.org/3/archives/python-3.12.8-docs-html.tar.bz2 2>&1 || {
        echo "⬇️  Tentando versão alternativa..."
        wget -q --show-progress https://www.python.org/ftp/python/doc/3.12.0/python-3.12.0-docs-html.tar.bz2 -O python-3.12.8-docs-html.tar.bz2 2>&1 || {
            echo "⚠️  Download direto falhou, criando documentação localmente..."
        }
    }
fi

# Extrair se existir
if [ -f "python-3.12.8-docs-html.tar.bz2" ]; then
    echo "📦 Extraindo documentação..."
    tar -xjf python-3.12.8-docs-html.tar.bz2 2>/dev/null || true
fi

# Criar arquivo de prompts baseado na documentação Python
echo "📝 Gerando prompts de treinamento baseados na documentação Python..."

cat > "$DOCS_DIR/python_prompts.txt" << 'PROMPTS_EOF'
# ===== TIPOS DE DADOS BÁSICOS =====
Explique detalhadamente os tipos de dados int, float, complex em Python com exemplos de uso
Como funcionam as strings em Python? Explique métodos como split, join, format, strip, replace
Quais são as diferenças entre listas, tuplas e sets em Python? Quando usar cada um?
Explique dicionários em Python com todos os métodos disponíveis: keys, values, items, get, update
O que são frozensets e quando devemos usá-los em Python?
Explique o tipo bytes e bytearray em Python e suas diferenças
Como funciona o tipo None em Python e seu uso em funções?
Explique boolean em Python e os valores truthy e falsy

# ===== ESTRUTURAS DE CONTROLE =====
Explique as estruturas condicionais if, elif, else em Python com exemplos
Como funcionam os loops for e while em Python? Inclua exemplos com break, continue, else
O que é a estrutura match-case introduzida no Python 3.10? Mostre exemplos avançados
Explique comprehensions em Python: list, dict, set e generator comprehensions
Como funciona o operador walrus := em Python?

# ===== FUNÇÕES =====
Como definir funções em Python com def? Explique argumentos posicionais, nomeados, *args, **kwargs
O que são funções lambda em Python e quando usá-las?
Explique decorators em Python com exemplos práticos
Como funcionam closures em Python? Dê exemplos
O que são funções geradoras com yield? Explique generators em detalhes
Explique o conceito de first-class functions em Python
Como funciona o functools.partial e functools.wraps?

# ===== PROGRAMAÇÃO ORIENTADA A OBJETOS =====
Como criar classes em Python? Explique __init__, self, atributos de classe e instância
O que são métodos especiais (dunder methods) em Python? Liste os principais
Explique herança simples e múltipla em Python
O que é Method Resolution Order (MRO) em Python?
Como funcionam @property, @classmethod, @staticmethod?
Explique ABC (Abstract Base Classes) em Python
O que são dataclasses em Python? Mostre exemplos completos
Explique slots em Python e quando usá-los para otimização
Como implementar o padrão Singleton em Python?
Explique metaclasses em Python com exemplos práticos

# ===== MÓDULOS E PACOTES =====
Como funciona o sistema de imports em Python? Explique import, from, as, relative imports
O que é __init__.py e como criar pacotes Python?
Explique __all__ e como controlar exportações de módulos
Como funciona o PYTHONPATH e sys.path?
O que são namespace packages em Python?
Explique importlib e imports dinâmicos

# ===== TRATAMENTO DE EXCEÇÕES =====
Explique try, except, else, finally em Python com exemplos
Como criar exceções personalizadas em Python?
O que são context managers e como criar com __enter__ e __exit__?
Explique o módulo contextlib e @contextmanager
Como funciona exception chaining com raise from?
O que são ExceptionGroups no Python 3.11+?

# ===== MÓDULOS BUILTIN ESSENCIAIS =====
Explique o módulo os em Python: operações de arquivos, diretórios, variáveis de ambiente
Como usar o módulo pathlib para manipulação de caminhos?
Explique o módulo sys: argumentos, stdin, stdout, exit, versão
O que o módulo collections oferece? Counter, defaultdict, namedtuple, deque, OrderedDict
Explique o módulo itertools com exemplos: chain, cycle, combinations, permutations
Como usar o módulo functools? reduce, partial, lru_cache, singledispatch
Explique o módulo re para expressões regulares em Python
Como funciona o módulo json para serialização?
Explique pickle para serialização de objetos Python
O módulo datetime: date, time, datetime, timedelta, timezone
Como usar o módulo logging para logs em aplicações?
Explique o módulo argparse para CLI em Python
O que o módulo typing oferece para type hints?
Explique Protocol e TypedDict do módulo typing
Como usar o módulo unittest para testes?
O que é pytest e como difere do unittest?
Explique o módulo asyncio para programação assíncrona
Como funcionam async/await em Python?
O módulo threading vs multiprocessing em Python
Explique concurrent.futures: ThreadPoolExecutor e ProcessPoolExecutor
Como usar o módulo subprocess para executar comandos?
Explique o módulo socket para programação de rede
O módulo http.server para criar servidores HTTP simples
Como usar urllib e requests para requisições HTTP?
Explique o módulo sqlite3 para bancos de dados
O módulo csv para leitura e escrita de arquivos CSV
Como usar o módulo xml.etree.ElementTree?
Explique o módulo hashlib para hashing
O módulo secrets para geração segura de números aleatórios
Como usar o módulo struct para dados binários?
Explique o módulo io: StringIO, BytesIO, TextIOWrapper
O módulo tempfile para arquivos temporários
Como funciona o módulo shutil para operações de arquivos?
Explique o módulo glob para pattern matching de arquivos
O módulo fnmatch para matching de nomes
Como usar o módulo copy: copy vs deepcopy?
Explique o módulo weakref para referências fracas
O módulo gc para controle do garbage collector
Como usar o módulo inspect para introspecção?
Explique o módulo dis para disassembly de bytecode
O módulo ast para Abstract Syntax Trees
Como usar o módulo profile e cProfile?
Explique o módulo timeit para benchmarking
O módulo pdb para debugging
Como funciona o módulo traceback?
Explique o módulo warnings em Python
O módulo abc para Abstract Base Classes
Como usar o módulo enum para enumerações?
Explique o módulo dataclasses em detalhes
O módulo graphlib para ordenação topológica
Como usar o módulo statistics para estatísticas?
Explique o módulo math: funções matemáticas
O módulo random para geração de números aleatórios
Como usar o módulo decimal para precisão decimal?
Explique o módulo fractions para números racionais
O módulo cmath para números complexos
Como usar o módulo heapq para filas de prioridade?
Explique o módulo bisect para busca binária
O módulo array para arrays eficientes

# ===== PYTHON AVANÇADO =====
Explique descriptors em Python: __get__, __set__, __delete__
Como funciona o protocolo de iteração: __iter__ e __next__?
O que é o GIL (Global Interpreter Lock) e como afeta multithreading?
Explique memory management em Python: reference counting, garbage collection
Como funciona interning de strings e inteiros em Python?
Explique o conceito de duck typing em Python
O que são type guards e como usar TypeGuard?
Como usar Generic e TypeVar para tipos genéricos?
Explique o módulo ctypes para integração com C
Como usar Cython para otimização de código Python?
Explique f-strings e suas features avançadas (Python 3.12)
O que são walrus operators e quando usá-los?
Como funciona pattern matching estrutural (match-case)?
Explique positional-only e keyword-only parameters
O que são assignment expressions?
Como criar context managers assíncronos?
Explique async generators em Python
O que é asyncio.gather vs asyncio.wait?
Como usar asyncio.Queue para comunicação entre tasks?
Explique aiohttp para requisições HTTP assíncronas
O que são semaphores e locks em asyncio?
Como implementar rate limiting com asyncio?
Explique o conceito de event loop em asyncio
O que são coroutines e como diferem de generators?
Como debugar código assíncrono em Python?

# ===== BOAS PRÁTICAS E PADRÕES =====
O que é PEP 8 e quais são as convenções de estilo Python?
Explique PEP 257 sobre docstrings
Como escrever código Pythonic?
O que é EAFP vs LBYL em Python?
Explique o Zen of Python (import this)
Quais são os anti-patterns mais comuns em Python?
Como otimizar performance em Python?
Explique profiling e como identificar bottlenecks
O que são slots e como melhoram performance?
Como usar __slots__ corretamente?
Explique memoization e caching em Python
O que é lazy evaluation e como implementar?
Como escrever código thread-safe em Python?
Explique imutabilidade e seus benefícios
O que são frozen dataclasses?
Como implementar o padrão Factory em Python?
Explique o padrão Observer em Python
O que é Dependency Injection em Python?
Como implementar o padrão Strategy?
Explique o padrão Command em Python
O que é o padrão Adapter e como implementar?
Como usar o padrão Decorator (design pattern, não Python decorator)?
Explique o padrão Composite em Python
O que é o padrão Iterator além do protocolo Python?
Como implementar Chain of Responsibility?

# ===== BIBLIOTECAS CIENTÍFICAS =====
Explique NumPy: arrays, broadcasting, ufuncs, slicing avançado
Como usar pandas para análise de dados: DataFrame, Series, groupby, merge
O que é matplotlib e como criar visualizações?
Explique scikit-learn para machine learning
Como usar TensorFlow e Keras para deep learning?
O que é PyTorch e suas diferenças do TensorFlow?
Explique SciPy para computação científica
Como usar Jupyter notebooks eficientemente?

# ===== WEB DEVELOPMENT =====
Explique Flask: rotas, templates, blueprints, extensões
O que é Django e sua arquitetura MTV?
Como criar APIs REST com FastAPI?
Explique Pydantic para validação de dados
O que é SQLAlchemy para ORM?
Como usar Celery para tarefas assíncronas?
Explique Redis com Python
O que é WebSockets com Python?
Como implementar autenticação JWT em Python?
Explique GraphQL com Python (Strawberry, Ariadne)

# ===== DEPLOYMENT E DEVOPS =====
Como criar ambientes virtuais com venv e virtualenv?
O que é pip e como gerenciar dependências?
Explique Poetry para gerenciamento de projetos
Como criar um setup.py e pyproject.toml?
O que é Docker e como containerizar apps Python?
Explique CI/CD para projetos Python
Como usar GitHub Actions com Python?
O que é pytest-cov para cobertura de testes?
Explique linting com pylint, flake8, black, ruff
Como configurar pre-commit hooks para Python?
PROMPTS_EOF

echo "✅ Prompts gerados!"
echo ""

# ============================================================================
# PARTE 2: TREINAR MODELOS COM DOCUMENTAÇÃO PYTHON
# ============================================================================

echo "🧠 FASE 2: Treinando Modelos com Documentação Python..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Carregar prompts do arquivo
mapfile -t PYTHON_PROMPTS < <(grep -v '^#' "$DOCS_DIR/python_prompts.txt" | grep -v '^$')

NUM_PROMPTS=${#PYTHON_PROMPTS[@]}
NUM_MODELOS=${#MODELOS[@]}

# Calcular total de rodadas (cada prompt para cada modelo)
TOTAL=$((NUM_PROMPTS * NUM_MODELOS))

echo ""
echo "📊 Configuração de Treinamento:"
echo "   ├─ Total de prompts Python: $NUM_PROMPTS"
echo "   ├─ Modelos a treinar: ${MODELOS[*]}"
echo "   ├─ Total de rodadas: $TOTAL"
echo "   └─ Log: $LOG_FILE"
echo ""

SUCESSO=0
FALHA=0
INICIO=$(date +%s)
RODADA=0

# Treinar cada modelo com cada prompt
for MODELO in "${MODELOS[@]}"; do
    echo ""
    echo "🔄 Treinando modelo: $MODELO"
    echo "────────────────────────────────────────"
    
    for PROMPT in "${PYTHON_PROMPTS[@]}"; do
        ((RODADA++))
        
        # Mostrar progresso a cada 10 rodadas
        if (( RODADA % 10 == 0 )) || (( RODADA == 1 )); then
            AGORA=$(date +%s)
            DECORRIDO=$((AGORA - INICIO))
            if (( RODADA > 1 )) && (( DECORRIDO > 0 )); then
                PCT=$(awk "BEGIN {printf \"%.1f\", $RODADA * 100 / $TOTAL}")
                ESTIMADO=$(awk "BEGIN {printf \"%.0f\", ($DECORRIDO * $TOTAL / $RODADA) - $DECORRIDO}")
                printf "\r   📈 Progresso: %d/%d (%s%%) | ETA: ~%ds     " "$RODADA" "$TOTAL" "$PCT" "$ESTIMADO"
            else
                printf "\r   📈 Progresso: %d/%d                        " "$RODADA" "$TOTAL"
            fi
        fi
        
        # Construir prompt completo para treinamento
        FULL_PROMPT="Você é um especialista em Python. $PROMPT Forneça uma resposta completa, técnica e com exemplos de código quando apropriado."
        
        # Escapar aspas no prompt
        ESCAPED_PROMPT=$(echo "$FULL_PROMPT" | sed 's/"/\\"/g')
        
        # Executar inferência no Ollama (timeout de 120s para respostas mais longas)
        RESP=$(timeout 120 curl -s http://localhost:11434/api/generate \
            -d "{\"model\":\"$MODELO\",\"prompt\":\"$ESCAPED_PROMPT\",\"stream\":false,\"options\":{\"num_predict\":500,\"temperature\":0.7}}" 2>/dev/null)
        
        if echo "$RESP" | grep -q "response"; then
            ((SUCESSO++))
            # Log detalhado
            if (( RODADA % 25 == 0 )); then
                echo "[$(date '+%H:%M:%S')] Rodada $RODADA - $MODELO - OK" >> "$LOG_FILE"
            fi
        else
            ((FALHA++))
            echo "[$(date '+%H:%M:%S')] Rodada $RODADA - $MODELO - FALHA" >> "$LOG_FILE"
        fi
    done
    
    echo ""
    echo "   ✅ Modelo $MODELO concluído!"
done

echo ""
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

FIM=$(date +%s)
TEMPO_TOTAL=$((FIM - INICIO))
TEMPO_MIN=$((TEMPO_TOTAL / 60))
TEMPO_SEG=$((TEMPO_TOTAL % 60))

if (( TOTAL > 0 )); then
    TAXA=$(awk "BEGIN {printf \"%.1f\", $SUCESSO * 100 / $TOTAL}")
else
    TAXA="0.0"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║      ✅ TREINAMENTO PYTHON CONCLUÍDO COM SUCESSO!                   ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 ESTATÍSTICAS FINAIS:"
echo "   ├─ Total de rodadas: $TOTAL"
echo "   ├─ Prompts Python: $NUM_PROMPTS"
echo "   ├─ Modelos treinados: $NUM_MODELOS"
echo "   ├─ Sucesso: $SUCESSO"
echo "   ├─ Falhas: $FALHA"
echo "   ├─ Taxa de sucesso: ${TAXA}%"
echo "   └─ Tempo total: ${TEMPO_MIN}min ${TEMPO_SEG}s"
echo ""
echo "📂 Log salvo em: $LOG_FILE"
echo "📂 Prompts em: $DOCS_DIR/python_prompts.txt"
echo ""
echo "🎯 Modelos exercitados:"
for m in "${MODELOS[@]}"; do
    echo "   ✅ $m"
done
echo ""
echo "📚 Tópicos Python cobertos:"
echo "   ✅ Tipos de dados e estruturas"
echo "   ✅ Funções e decorators"
echo "   ✅ POO e classes"
echo "   ✅ Módulos standard library"
echo "   ✅ Programação assíncrona"
echo "   ✅ Boas práticas e padrões"
echo "   ✅ Bibliotecas científicas"
echo "   ✅ Web development"
echo "   ✅ DevOps e deployment"
echo ""
echo "📅 Data: $(date '+%d/%m/%Y %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
