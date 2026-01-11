"""
SmartLife API - Automation Routes
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..app import get_service

router = APIRouter()


# ================== Schemas ==================

class TriggerConfig(BaseModel):
    """Configuração de trigger para automação."""
    type: str = Field(..., description="Tipo: time, cron, device_state, sensor, sunrise, sunset")
    cron: Optional[str] = Field(None, description="Expressão cron (ex: 0 8 * * *)")
    time: Optional[str] = Field(None, description="Horário (HH:MM)")
    device_id: Optional[str] = Field(None, description="ID do dispositivo para trigger de estado")
    state: Optional[Dict[str, Any]] = Field(None, description="Estado para trigger")


class ActionConfig(BaseModel):
    """Configuração de ação."""
    device_id: str = Field(..., description="ID do dispositivo ou 'all_lights', 'all_devices'")
    command: str = Field(..., description="Comando: on, off, toggle, dim, color")
    value: Optional[Any] = Field(None, description="Valor do comando")
    delay: Optional[int] = Field(None, description="Delay em segundos antes da ação")


class ConditionConfig(BaseModel):
    """Configuração de condição."""
    type: str = Field(..., description="Tipo: time_range, device_state, weekday")
    start_time: Optional[str] = Field(None, description="Horário inicial (HH:MM)")
    end_time: Optional[str] = Field(None, description="Horário final (HH:MM)")
    days: Optional[List[int]] = Field(None, description="Dias da semana (0=seg, 6=dom)")
    device_id: Optional[str] = Field(None, description="ID do dispositivo para condição")
    state: Optional[Dict[str, Any]] = Field(None, description="Estado requerido")


class AutomationCreate(BaseModel):
    """Schema para criar automação."""
    name: str = Field(..., description="Nome da automação")
    description: Optional[str] = Field(None, description="Descrição")
    trigger: TriggerConfig
    actions: List[ActionConfig]
    conditions: Optional[List[ConditionConfig]] = Field(default=[])


class AutomationUpdate(BaseModel):
    """Schema para atualizar automação."""
    name: Optional[str] = None
    description: Optional[str] = None
    trigger: Optional[TriggerConfig] = None
    actions: Optional[List[ActionConfig]] = None
    conditions: Optional[List[ConditionConfig]] = None
    is_active: Optional[bool] = None


# ================== Routes ==================

@router.get("/")
async def list_automations():
    """Lista todas as automações."""
    service = get_service()
    automations = await service.get_automations()
    return automations


@router.get("/{automation_id}")
async def get_automation(automation_id: str):
    """Obtém detalhes de uma automação."""
    service = get_service()
    automation = await service.automation_engine.get(automation_id)
    
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    return automation


@router.post("/")
async def create_automation(automation: AutomationCreate):
    """
    Cria uma nova automação.
    
    Exemplo:
    ```json
    {
        "name": "Boa Noite",
        "trigger": {
            "type": "cron",
            "cron": "0 23 * * *"
        },
        "actions": [
            {"device_id": "all_lights", "command": "off"}
        ]
    }
    ```
    """
    service = get_service()
    
    result = await service.automation_engine.create(
        name=automation.name,
        trigger=automation.trigger.model_dump(),
        actions=[a.model_dump() for a in automation.actions],
        conditions=[c.model_dump() for c in automation.conditions] if automation.conditions else [],
        description=automation.description or ""
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.put("/{automation_id}")
async def update_automation(automation_id: str, automation: AutomationUpdate):
    """Atualiza uma automação existente."""
    service = get_service()
    
    updates = {}
    if automation.name is not None:
        updates["name"] = automation.name
    if automation.description is not None:
        updates["description"] = automation.description
    if automation.trigger is not None:
        updates["trigger"] = automation.trigger.model_dump()
    if automation.actions is not None:
        updates["actions"] = [a.model_dump() for a in automation.actions]
    if automation.conditions is not None:
        updates["conditions"] = [c.model_dump() for c in automation.conditions]
    if automation.is_active is not None:
        updates["is_active"] = automation.is_active
    
    result = await service.automation_engine.update(automation_id, updates)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.delete("/{automation_id}")
async def delete_automation(automation_id: str):
    """Remove uma automação."""
    service = get_service()
    result = await service.automation_engine.delete(automation_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/{automation_id}/enable")
async def enable_automation(automation_id: str):
    """Ativa uma automação."""
    service = get_service()
    result = await service.toggle_automation(automation_id, True)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return {"success": True, "automation_id": automation_id, "is_active": True}


@router.post("/{automation_id}/disable")
async def disable_automation(automation_id: str):
    """Desativa uma automação."""
    service = get_service()
    result = await service.toggle_automation(automation_id, False)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return {"success": True, "automation_id": automation_id, "is_active": False}


@router.post("/{automation_id}/execute")
async def execute_automation(automation_id: str):
    """Executa uma automação manualmente."""
    service = get_service()
    
    automation = await service.automation_engine.get(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    result = await service.automation_engine.execute(automation_id)
    return result


@router.get("/triggers/types")
async def list_trigger_types():
    """Lista tipos de trigger disponíveis."""
    return {
        "time": {
            "description": "Horário específico",
            "params": ["time (HH:MM)"]
        },
        "cron": {
            "description": "Expressão cron",
            "params": ["cron (0 8 * * *)"]
        },
        "sunrise": {
            "description": "Nascer do sol",
            "params": ["offset (minutos, opcional)"]
        },
        "sunset": {
            "description": "Pôr do sol",
            "params": ["offset (minutos, opcional)"]
        },
        "device_state": {
            "description": "Mudança de estado de dispositivo",
            "params": ["device_id", "state"]
        },
        "sensor": {
            "description": "Valor de sensor",
            "params": ["device_id", "comparison", "value"]
        }
    }


@router.get("/templates")
async def list_automation_templates():
    """Lista templates de automações comuns."""
    return [
        {
            "id": "boa_noite",
            "name": "Boa Noite",
            "description": "Desliga todas as luzes às 23h",
            "trigger": {"type": "cron", "cron": "0 23 * * *"},
            "actions": [{"device_id": "all_lights", "command": "off"}]
        },
        {
            "id": "bom_dia",
            "name": "Bom Dia",
            "description": "Liga luzes do quarto às 7h",
            "trigger": {"type": "cron", "cron": "0 7 * * 1-5"},
            "actions": [
                {"device_id": "quarto_luz", "command": "on"},
                {"device_id": "quarto_luz", "command": "dim", "value": 50}
            ]
        },
        {
            "id": "chegando_casa",
            "name": "Chegando em Casa",
            "description": "Liga luzes ao abrir porta",
            "trigger": {"type": "device_state", "device_id": "sensor_porta", "state": {"open": True}},
            "conditions": [{"type": "time_range", "start_time": "18:00", "end_time": "23:00"}],
            "actions": [
                {"device_id": "sala_luz", "command": "on"},
                {"device_id": "corredor_luz", "command": "on"}
            ]
        },
        {
            "id": "tv_ambiente",
            "name": "Modo TV",
            "description": "Ajusta iluminação para assistir TV",
            "trigger": {"type": "device_state", "device_id": "tv_sala", "state": {"on": True}},
            "actions": [
                {"device_id": "sala_luz", "command": "dim", "value": 20},
                {"device_id": "led_tv", "command": "on"}
            ]
        }
    ]
