#!/bin/bash
# Script para verificar o status do treinamento Python no servidor

echo "╔═══════════════════════════════════════════════════════╗"
echo "║     📊 STATUS DO TREINAMENTO PYTHON                  ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Verificar se o processo está rodando
if pgrep -f "train_python_docs" > /dev/null; then
    echo "🟢 Status: TREINAMENTO EM ANDAMENTO"
    echo ""
else
    echo "🔴 Status: TREINAMENTO FINALIZADO OU NÃO INICIADO"
    echo ""
fi

# Mostrar últimas linhas do log
echo "📝 Últimas linhas do log de treinamento:"
echo "────────────────────────────────────────"
tail -30 ~/training_output.log 2>/dev/null || echo "Log não encontrado"
echo ""

# Mostrar estatísticas do log de detalhes
LOG_DETALHES=$(ls -t /tmp/python_training_*.log 2>/dev/null | head -1)
if [ -n "$LOG_DETALHES" ]; then
    echo "📊 Estatísticas do log detalhado: $LOG_DETALHES"
    echo "────────────────────────────────────────"
    OK_COUNT=$(grep -c "OK" "$LOG_DETALHES" 2>/dev/null || echo "0")
    FAIL_COUNT=$(grep -c "FALHA" "$LOG_DETALHES" 2>/dev/null || echo "0")
    echo "   ✅ Sucesso: $OK_COUNT"
    echo "   ❌ Falhas: $FAIL_COUNT"
fi

echo ""
echo "📅 Verificado em: $(date '+%d/%m/%Y %H:%M:%S')"
