#!/usr/bin/env python3
import pathlib, importlib.util, json
from datetime import datetime

bus_path = pathlib.Path(__file__).resolve().parents[1] / 'specialized_agents' / 'agent_communication_bus.py'
spec = importlib.util.spec_from_file_location('agent_bus', str(bus_path))
agent_bus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_bus)
get_communication_bus = agent_bus.get_communication_bus
MessageType = agent_bus.MessageType

bus = get_communication_bus()
now = datetime.utcnow().isoformat()
msg_text = (
    "Solicitação: Por favor, DIRETOR — distribuir a tarefa de atualização da página de serviços e documentação a todos os desenvolvedores.\n\n"
    "Resumo da tarefa:\n"
    "- Gerar e completar OpenAPI para todos os endpoints detectados.\n"
    "- Converter OpenAPI para draw.io e publicar nos docs.\n"
    "- Substituir IPs locais por URLs públicas (criar docs/public_url_overrides.json).\n"
    "- Auditar e consolidar segredos no cofre do projeto (tools/vault).\n"
    "- Criar túnel persistente / DNS (Cloudflare) se necessário para testes e verificação.\n\n"
    "Atribuições sugeridas (por favor distribuir):\n"
    "- Infra (Cloudflare/DNS/Tunnel)\n- Backend (Open WebUI auth & endpoint validation)\n- Docs (OpenAPI + draw.io + Confluence upload)\n- Security (vault migration & credential audit)\n\n"
    "Solicito que o DIRETOR confirme responsáveis, prazos e publique a tarefa para todos os desenvolvedores."
)
msg = bus.publish(MessageType.REQUEST, 'assistant', 'DIRETOR', msg_text, {'task':'services_page_update','generated_at':now})
print('Published to DIRETOR:', msg.to_dict())
