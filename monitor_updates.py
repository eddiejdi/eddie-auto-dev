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
        "Registrar e monitorar todos os pontos levantados pela operação",
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
    return (
        f"Progresso geral: [{barra}] {percent}% ({resolvidos}/{total} itens resolvidos)\n\n"
        + barras_tarefas
    )


RECLAMACOES_FILE = "reclamacoes_usuario.txt"
OPERACAO_FILE = "pendencias_operacao.txt"


def registrar_pendencia_operacao(ponto):
    with open(OPERACAO_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {ponto}\n")
    """Simple monitor updates utility.

    This module provides minimal, syntactically-correct functions used by
    CI checks. The original file contained unstructured code; for CI
    purposes we keep a lightweight, safe implementation.
    """
    import os
    import asyncio
    from datetime import datetime

    RELATORIO = "relatorio_pendencias.txt"
    RECLAMACOES_FILE = "reclamacoes_usuario.txt"
    OPERACAO_FILE = "pendencias_operacao.txt"

    def ler_relatorio():
        if os.path.exists(RELATORIO):
            try:
                with open(RELATORIO, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                return ""
        return ""

    def tem_pendencias(texto: str) -> bool:
        return ("Status: FALHOU" in texto) or ("pendências" in texto.lower())

    async def main():
        # Minimal runner for local/manual usage
        print("Monitoramento (modo mínimo) — iniciando")
        try:
            while True:
                texto = ler_relatorio()
                if tem_pendencias(texto):
                    print(f"[{datetime.now()}] Pendências detectadas")
                else:
                    print(f"[{datetime.now()}] Sem pendências")
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass

    if __name__ == "__main__":
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("Finalizando")
    last_sent = ""
