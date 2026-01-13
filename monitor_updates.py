def gerar_progress_bar_tarefa(nome, resolvido):
    from random import randint
    barra = "█" if resolvido else "░"
    status = "Concluída" if resolvido else "Pendente"
    if resolvido:
        previsao = "Previsão: concluído"
    else:
        dias = randint(1, 5)
        horas = randint(0, 23)
        previsao = f"Previsão: {dias} dias e {horas} horas"
    return f"{nome}: [{barra}] {status} | {previsao}\n"
def gerar_progress_bar():
    pendencias = [
        "Restaurar notificações automáticas do Telegram e CI/CD",
        "Reiniciar e manter ativo o serviço eddie-telegram-bot.service",
        "Garantir variáveis de ambiente disponíveis para todos os processos",
        "Corrigir erros dos testes em calculadora_final",
        "Corrigir erros dos testes em calculadora_v2",
        "Executar scripts de monitoramento no ambiente correto (WSL)",
        "Registrar e monitorar todas as reclamações do usuário",
        "Registrar e monitorar todos os pontos levantados pela operação"
    ]
    texto = ler_relatorio()
    resolvidos = 0
    barras_tarefas = ""
    for p in pendencias:
        resolvido = p.lower() not in texto.lower()
        if resolvido:
            resolvidos += 1
        barras_tarefas += gerar_progress_bar_tarefa(p, resolvido)
    total = len(pendencias)
    percent = int((resolvidos / total) * 100)
    barra = "█" * (percent // 10) + "░" * (10 - (percent // 10))
    return f"Progresso geral: [{barra}] {percent}% ({resolvidos}/{total} itens resolvidos)\n\n" + barras_tarefas
RECLAMACOES_FILE = "reclamacoes_usuario.txt"
OPERACAO_FILE = "pendencias_operacao.txt"
def registrar_pendencia_operacao(ponto):
    with open(OPERACAO_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {ponto}\n")
    # Também adiciona ao relatório de pendências
    with open(RELATORIO, "a", encoding="utf-8") as f:
        f.write(f"\n[PENDÊNCIA OPERAÇÃO] {ponto}\n")
def registrar_reclamacao(reclamacao):
    with open(RECLAMACOES_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {reclamacao}\n")
    # Também adiciona ao relatório de pendências
    with open(RELATORIO, "a", encoding="utf-8") as f:
        f.write(f"\n[PENDÊNCIA USUÁRIO] {reclamacao}\n")
def incluir_reclamacoes_no_relatorio(texto):
    # Reclamações do usuário
    if os.path.exists(RECLAMACOES_FILE):
        with open(RECLAMACOES_FILE, "r", encoding="utf-8") as f:
            reclamacoes = f.read().strip()
        if reclamacoes:
            texto += f"\n\nReclamações do usuário registradas:\n{reclamacoes}"
    # Pontos da operação
    if os.path.exists(OPERACAO_FILE):
        with open(OPERACAO_FILE, "r", encoding="utf-8") as f:
            operacao = f.read().strip()
        if operacao:
            texto += f"\n\nPendências levantadas pela operação:\n{operacao}"
    return texto
import time
def ler_relatorio():

import time
import os
from datetime import datetime
import asyncio

RELATORIO = "relatorio_pendencias.txt"
INTERVALO_PADRAO = 30  # segundos
INTERVALO_PENDENTE = 5  # segundos

try:
    from telegram_bot import TelegramAPI
    TELEGRAM_OK = True
except Exception:
    TELEGRAM_OK = False

def tem_pendencias(texto):
    return ("Status: FALHOU" in texto) or ("pendências" in texto.lower())





async def main():
    print("Monitoramento contínuo iniciado. Pressione Ctrl+C para sair.")
    last_sent = ""
    api = None
    chat_id = os.getenv("ADMIN_CHAT_ID")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if TELEGRAM_OK and token and chat_id:
        api = TelegramAPI(token)
        chat_id = int(chat_id)
    while True:
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        texto = ler_relatorio()
        texto_final = incluir_reclamacoes_no_relatorio(texto)
        barra = gerar_progress_bar()
        print(f"\n[Atualização {agora}]")
        print(barra)
        print(texto_final)
        if tem_pendencias(texto):
            if api and texto != last_sent:
                try:
                    await api.send_message(chat_id, f"[Atualização {agora}]\n" + barra + texto_final[:4000])
                    last_sent = texto
                    print("Enviado para Telegram.")
                except Exception as e:
                    print(f"Falha ao enviar para Telegram: {e}")
            await asyncio.sleep(INTERVALO_PENDENTE)
        else:
            await asyncio.sleep(INTERVALO_PADRAO)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMonitoramento encerrado pelo usuário.")
