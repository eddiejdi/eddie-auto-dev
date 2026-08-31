#!/bin/bash
# Script de Treinamento RÁPIDO - Teste com 50 prompts
# Usa apenas o modelo mais leve para teste rápido

echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║   🐍 TREINAMENTO RÁPIDO - DOCUMENTAÇÃO PYTHON (TESTE) 🐍         ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"

LOG_FILE="/tmp/quick_training_$(date +%Y%m%d_%H%M%S).log"
MODELO="qwen2.5-coder:1.5b"

# Prompts de treinamento Python (versão reduzida)
declare -a PROMPTS=(
    "Explique tipos de dados int, float, complex em Python"
    "Como funcionam strings em Python? Métodos principais"
    "Diferenças entre listas, tuplas e sets em Python"
    "Explique dicionários e seus métodos em Python"
    "Estruturas condicionais if, elif, else em Python"
    "Loops for e while em Python com exemplos"
    "Como definir funções em Python com args e kwargs"
    "O que são funções lambda em Python"
    "Explique decorators em Python"
    "Como criar classes em Python"
    "O que são métodos especiais dunder em Python"
    "Herança e polimorfismo em Python"
    "O módulo os para operações de sistema"
    "pathlib para manipulação de caminhos"
    "Expressões regulares com módulo re"
    "Serialização JSON em Python"
    "datetime para datas e horas"
    "logging para registrar eventos"
    "argparse para argumentos de linha de comando"
    "unittest para testes unitários"
    "asyncio para programação assíncrona"
    "threading vs multiprocessing"
    "Tratamento de exceções try except"
    "Context managers com with"
    "List comprehensions em Python"
    "Geradores e yield em Python"
    "O que é GIL em Python"
    "Type hints e módulo typing"
    "Dataclasses em Python"
    "ABC para classes abstratas"
    "Property decorators em Python"
    "Slots para otimização de memória"
    "Closures em Python"
    "Descriptors em Python"
    "Metaclasses explicadas"
    "itertools principais funções"
    "functools reduce, partial, lru_cache"
    "collections Counter defaultdict namedtuple"
    "heapq para filas de prioridade"
    "bisect para busca binária"
    "pickle para serialização de objetos"
    "sqlite3 para bancos de dados"
    "csv para arquivos CSV"
    "requests para HTTP"
    "Flask básico para web"
    "FastAPI para APIs REST"
    "Pytest para testes"
    "Virtual environments venv"
    "pip e gerenciamento de pacotes"
    "Docker com Python"
)

TOTAL=${#PROMPTS[@]}
SUCESSO=0
FALHA=0
INICIO=$(date +%s)

echo ""
echo "📊 Configuração:"
echo "   ├─ Modelo: $MODELO"
echo "   ├─ Total de prompts: $TOTAL"
echo "   └─ Log: $LOG_FILE"
echo ""
echo "🔄 Iniciando treinamento..."
echo "────────────────────────────────────────"

for ((i=0; i<TOTAL; i++)); do
    PROMPT="${PROMPTS[$i]}"
    NUM=$((i+1))
    
    # Mostrar progresso
    printf "\r   [%d/%d] %.50s...   " "$NUM" "$TOTAL" "$PROMPT"
    
    # Construir prompt completo
    FULL_PROMPT="Você é um especialista Python. $PROMPT. Responda de forma técnica e concisa com exemplos de código."
    
    # Fazer requisição ao Ollama
    RESP=$(timeout 120 curl -s http://localhost:11434/api/generate \
        -d "{\"model\":\"$MODELO\",\"prompt\":\"$FULL_PROMPT\",\"stream\":false,\"options\":{\"num_predict\":300,\"temperature\":0.7}}" 2>/dev/null)
    
    if echo "$RESP" | grep -q "response"; then
        ((SUCESSO++))
        echo "[$(date '+%H:%M:%S')] $NUM - OK" >> "$LOG_FILE"
    else
        ((FALHA++))
        echo "[$(date '+%H:%M:%S')] $NUM - FALHA" >> "$LOG_FILE"
    fi
done

echo ""
echo ""

FIM=$(date +%s)
TEMPO=$((FIM - INICIO))
TAXA=$(awk "BEGIN {printf \"%.1f\", $SUCESSO * 100 / $TOTAL}")

echo "════════════════════════════════════════"
echo "✅ TREINAMENTO CONCLUÍDO!"
echo ""
echo "📊 Estatísticas:"
echo "   ├─ Sucesso: $SUCESSO/$TOTAL (${TAXA}%)"
echo "   ├─ Falhas: $FALHA"
echo "   ├─ Tempo: ${TEMPO}s"
echo "   └─ Log: $LOG_FILE"
echo ""
echo "📅 $(date '+%d/%m/%Y %H:%M:%S')"
