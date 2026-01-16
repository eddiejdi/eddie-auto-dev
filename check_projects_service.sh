#!/bin/bash
# Serviço: check_projects_service.sh
# Roda periodicamente testes em todos os projetos python e atualiza relatórios de CI/CD

BASE="/home/eddie/myClaude/dev_projects/python"
LOGDIR="/tmp"
for proj in "$BASE"/*; do
  if [ -d "$proj" ]; then
    name=$(basename "$proj")
    cd "$proj"
    pytest > "$LOGDIR/pytest_${name}.log" 2>&1
    echo $? > "$LOGDIR/pytest_${name}.exit"
    # Atualiza relatório
    if [ -f "$proj/CI_REPORT.txt" ]; then
      status=$(cat "$LOGDIR/pytest_${name}.exit")
      if [ "$status" = "0" ]; then
        echo -e "# Relatório de CI/CD - $name\n\nStatus: OK\n\nTodos os testes passaram com sucesso." > "$proj/CI_REPORT.txt"
      else
        head -40 "$LOGDIR/pytest_${name}.log" > "$proj/CI_REPORT.txt"
      fi
    fi
  fi
done

# Gerar e enviar relatório consolidado para o Telegram
python3 /home/eddie/myClaude/send_pending_report.py
