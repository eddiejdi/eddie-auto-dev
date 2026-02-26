#!/usr/bin/env python3
"""Teste local (dry-run) para `HomeAssistantAdapter.execute_natural_command`.

Este script cria uma instância do adapter e substitui métodos de rede
por versões de teste que apenas imprimem as chamadas esperadas — não
depende de um Home Assistant real.
"""
import asyncio
import json
from specialized_agents.home_automation.ha_adapter import HomeAssistantAdapter


class DummyAdapter(HomeAssistantAdapter):
    def __init__(self):
        # não passar token/url reais
        super().__init__(url="http://localhost:8123", token="fake")

    async def get_devices(self, domain_filter: None = None):
        # retornar um conjunto fixo de dispositivos para matching
        return [
            {"entity_id": "fan.quarto", "name": "Quarto", "state": "off", "domain": "fan", "attributes": {"percentage": 25}},
            {"entity_id": "fan.ventilador_e_luz", "name": "Ventilador e Luz", "state": "on", "domain": "fan", "attributes": {"percentage": 47}},
        ]

    async def call_service(self, domain: str, service: str, data: dict):
        # Simular execução — apenas retornar estrutura semelhante ao adapter real
        print(f"[DRYRUN] call_service -> domain={domain}, service={service}, data={data}")
        return {"success": True, "called": f"{domain}.{service}", "data": data}

    async def get_entity_state(self, entity_id: str):
        # Simular leitura de estado
        if entity_id == "fan.quarto":
            return {"state": "on", "attributes": {"percentage": 50}}
        return {"state": "off", "attributes": {}}


async def run_tests():
    adapter = DummyAdapter()
    tests = [
        "ligar ventilador do quarto",
        "ventilador do quarto 50%",
        "ventilador do quarto velocidade média",
        "alternar ventilador do quarto",
        "ventilador e luz 75 porcento",
    ]

    for t in tests:
        print("\nTEST ->", t)
        res = await adapter.execute_natural_command(t)
        print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(run_tests())
