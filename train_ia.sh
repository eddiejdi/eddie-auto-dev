#!/bin/bash
# Script de Treinamento Massivo de IAs - 1009 Rodadas
# Autor: Copilot | Data: Janeiro 2026

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     🚀 INICIANDO 1009 RODADAS DE TREINAMENTO DE IAs 🚀      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

TOTAL=1009
LOG_FILE="/tmp/training_log_$(date +%Y%m%d_%H%M%S).txt"

# Modelos disponíveis no servidor
declare -a MODELOS=("qwen2.5-coder:1.5b" "qwen2.5-coder:7b" "deepseek-coder-v2:16b" "codestral:22b")

# Prompts de treinamento variados
declare -a PROMPTS=(
    "Explique o conceito de recursao em programacao"
    "Escreva uma funcao Python para calcular fibonacci"
    "O que e uma arvore binaria de busca"
    "Como funciona o algoritmo quicksort"
    "Explique o padrao de projeto Singleton"
    "O que e programacao orientada a objetos"
    "Como criar uma API REST"
    "Explique o conceito de closure em JavaScript"
    "O que sao ponteiros em C"
    "Como funciona o garbage collector"
    "Explique heranca e polimorfismo"
    "O que e um banco de dados NoSQL"
    "Como otimizar queries SQL"
    "Explique microservicos"
    "O que e Docker e containers"
    "Como funciona Git internamente"
    "Explique threads vs processos"
    "O que e deadlock em sistemas"
    "Como funciona HTTPS e TLS"
    "Explique JWT tokens e autenticacao"
    "O que e CI CD e DevOps"
    "Como funciona load balancing"
    "Explique caching strategies"
    "O que e GraphQL vs REST"
    "Como funciona WebSocket"
    "Explique design patterns principais"
    "O que e TDD test driven development"
    "Como fazer debugging eficiente"
    "Explique Big O notation complexidade"
    "O que e clean code e boas praticas"
)

NUM_PROMPTS=${#PROMPTS[@]}
NUM_MODELOS=${#MODELOS[@]}

SUCESSO=0
FALHA=0
INICIO=$(date +%s)

echo "📊 Configuração:"
echo "   • Total de rodadas: $TOTAL"
echo "   • Modelos: ${MODELOS[*]}"
echo "   • Prompts variados: $NUM_PROMPTS"
echo "   • Log: $LOG_FILE"
echo ""

echo "🔄 Iniciando treinamento..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

for ((i=1; i<=TOTAL; i++)); do
    M_IDX=$(( (i-1) % NUM_MODELOS ))
    P_IDX=$(( (i-1) % NUM_PROMPTS ))
    MODELO="${MODELOS[$M_IDX]}"
    PROMPT_BASE="${PROMPTS[$P_IDX]}"
    PROMPT="Rodada $i: $PROMPT_BASE. Responda de forma concisa em 2-3 frases."
    
    # Mostrar progresso a cada 20 rodadas
    if (( i % 20 == 0 )) || (( i == 1 )); then
        AGORA=$(date +%s)
        DECORRIDO=$((AGORA - INICIO))
        if (( i > 1 )) && (( DECORRIDO > 0 )); then
            PCT=$(awk "BEGIN {printf \"%.1f\", $i * 100 / $TOTAL}")
            ESTIMADO=$(awk "BEGIN {printf \"%.0f\", ($DECORRIDO * $TOTAL / $i) - $DECORRIDO}")
            printf "\r🔄 Progresso: %d/%d (%s%%) | Modelo: %-20s | ETA: ~%ss     " "$i" "$TOTAL" "$PCT" "$MODELO" "$ESTIMADO"
        else
            printf "\r🔄 Progresso: %d/%d | Modelo: %-20s                        " "$i" "$TOTAL" "$MODELO"
        fi
    fi
    
    # Executar inferência no Ollama
    RESP=$(timeout 60 curl -s http://localhost:11434/api/generate \
        -d "{\"model\":\"$MODELO\",\"prompt\":\"$PROMPT\",\"stream\":false,\"options\":{\"num_predict\":100}}" 2>/dev/null)
    
    if echo "$RESP" | grep -q "response"; then
        ((SUCESSO++))
        # Log a cada 50 rodadas
        if (( i % 50 == 0 )); then
            echo "[$(date '+%H:%M:%S')] Rodada $i - $MODELO - OK" >> "$LOG_FILE"
        fi
    else
        ((FALHA++))
        echo "[$(date '+%H:%M:%S')] Rodada $i - $MODELO - FALHA: $RESP" >> "$LOG_FILE"
    fi
done

echo ""
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

FIM=$(date +%s)
TEMPO_TOTAL=$((FIM - INICIO))
TEMPO_MIN=$((TEMPO_TOTAL / 60))
TEMPO_SEG=$((TEMPO_TOTAL % 60))
TAXA=$(awk "BEGIN {printf \"%.1f\", $SUCESSO * 100 / $TOTAL}")

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║            ✅ TREINAMENTO CONCLUÍDO COM SUCESSO!            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 ESTATÍSTICAS FINAIS:"
echo "   ├─ Total de rodadas: $TOTAL"
echo "   ├─ Sucesso: $SUCESSO"
echo "   ├─ Falhas: $FALHA"
echo "   ├─ Taxa de sucesso: ${TAXA}%"
echo "   └─ Tempo total: ${TEMPO_MIN}min ${TEMPO_SEG}s"
echo ""
echo "📂 Log salvo em: $LOG_FILE"
echo ""
echo "🎯 Modelos exercitados:"
for m in "${MODELOS[@]}"; do
    echo "   ✅ $m"
done
echo ""
echo "📅 Data: $(date '+%d/%m/%Y %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
