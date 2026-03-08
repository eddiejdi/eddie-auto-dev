#!/bin/bash
# Limita o uso de CPU dos processos VS Code e Python
# 80% quando tela ligada, 100% quando desligada

# Função para verificar se a tela está ligada
is_screen_on() {
    xset q | grep -q 'Monitor is On'
}

# Função para aplicar limite de CPU
limit_cpu() {
    local limit=$1
    for pname in code python; do
        for pid in $(pgrep $pname); do
            cpulimit -p $pid -l $limit -b
        done
    done
}

while true; do
    if is_screen_on; then
        limit_cpu 80
    else
        limit_cpu 100
    fi
    sleep 30
done
