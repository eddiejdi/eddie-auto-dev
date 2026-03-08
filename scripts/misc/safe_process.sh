#!/bin/bash
# Wrapper script para processamento seguro de vagas
# Executa verificação de saúde antes de processar

echo "🛡️ PROCESSAMENTO SEGURO DE VAGAS"
echo "================================="

# Executar verificação de saúde
echo "🔍 Executando verificação de saúde..."
if ! ./health_check.sh; then
    echo "❌ Verificação de saúde falhou. Abortando processamento."
    exit 1
fi

echo ""
echo "🚀 Iniciando processamento..."

# Verificar se devemos usar modo one-by-one
if [ "$1" = "--process-one-by-one" ]; then
    MODE="--process-one-by-one"
    echo "📝 Modo: Processamento uma a uma (recomendado)"
else
    MODE=""
    echo "📝 Modo: Processamento normal (use --process-one-by-one para modo seguro)"
fi

echo ""
echo "⚠️  MONITORAMENTO: Mantenha este terminal aberto para acompanhar o progresso"
echo "⚠️  INTERVENÇÃO: Pressione Ctrl+C a qualquer momento para parar"
echo ""

# Executar processamento com timeout de segurança
timeout 1800 python3 apply_real_job.py $MODE

exit_code=$?
echo ""
if [ $exit_code -eq 0 ]; then
    echo "✅ Processamento concluído com sucesso!"
elif [ $exit_code -eq 124 ]; then
    echo "⏰ Processamento interrompido por timeout (30 minutos)"
else
    echo "❌ Processamento falhou (código: $exit_code)"
fi

echo ""
echo "💡 Para próximos processamentos:"
echo "   ./safe_process.sh --process-one-by-one  # Modo seguro"
echo "   ./safe_process.sh                       # Modo normal"