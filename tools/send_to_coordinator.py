#!/usr/bin/env python3
from specialized_agents.agent_communication_bus import (
    get_communication_bus,
    MessageType,
)


def main():
    bus = get_communication_bus()
    content = (
        "A) Valide a migração SQLite→Postgres e, se OK, atualize as variáveis de ambiente de produção "
        "para usar `DATABASE_URL`.\n\n"
        "B) Execute a suíte de testes completa em produção e reporte falhas (ex.: `GITHUB_TOKEN` ausente, "
        "serviços parados).\n\n"
        "Próximos passos sugeridos:\n"
        "1. Rodar testes rápidos do interceptor contra Postgres aqui (já disponível localmente).\n"
        "2. Atualizar systemd/Docker/Docker Compose para apontar `DATABASE_URL` para o Postgres migrado.\n"
        "3. Reiniciar serviços `specialized-agents` e `eddie-telegram-bot` após atualização das variáveis.\n"
        "4. Fornecer relatório com falhas, regressões e plano de rollback caso necessário.\n\n"
        "Por favor confirme e execute as etapas de produção ou solicite que eu execute os testes rápidos localmente primeiro."
    )

    msg = bus.publish(MessageType.REQUEST, "DIRETOR", "agent_coordinator", content)
    if msg:
        print("Mensagem publicada:", msg.to_dict())
    else:
        print("Falha ao publicar mensagem (bus inativo ou filtrado)")


if __name__ == "__main__":
    main()
