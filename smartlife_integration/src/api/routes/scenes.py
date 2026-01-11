"""
SmartLife API - Scene Routes
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..app import get_service

router = APIRouter()


# ================== Schemas ==================

class SceneAction(BaseModel):
    """Ação de uma cena."""
    device_id: str = Field(..., description="ID do dispositivo")
    command: str = Field(..., description="Comando: on, off, dim, color")
    value: Optional[Any] = Field(None, description="Valor do comando")
    delay: Optional[int] = Field(0, description="Delay em segundos")


class SceneCreate(BaseModel):
    """Schema para criar cena."""
    name: str = Field(..., description="Nome da cena")
    description: Optional[str] = Field(None, description="Descrição")
    icon: Optional[str] = Field("🎬", description="Ícone da cena")
    actions: List[SceneAction]


class SceneUpdate(BaseModel):
    """Schema para atualizar cena."""
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    actions: Optional[List[SceneAction]] = None


# ================== Routes ==================

@router.get("/")
async def list_scenes():
    """Lista todas as cenas."""
    service = get_service()
    scenes = await service.get_scenes()
    return scenes


@router.get("/{scene_id}")
async def get_scene(scene_id: str):
    """Obtém detalhes de uma cena."""
    service = get_service()
    scenes = await service.get_scenes()
    
    scene = next((s for s in scenes if s.get("id") == scene_id), None)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    return scene


@router.post("/")
async def create_scene(scene: SceneCreate):
    """
    Cria uma nova cena.
    
    Uma cena é um conjunto de ações que podem ser executadas com um único comando.
    
    Exemplo:
    ```json
    {
        "name": "Cinema",
        "description": "Modo para assistir filmes",
        "icon": "🎬",
        "actions": [
            {"device_id": "sala_luz", "command": "dim", "value": 10},
            {"device_id": "led_tv", "command": "on"},
            {"device_id": "led_tv", "command": "color", "value": "#0000FF"}
        ]
    }
    ```
    """
    service = get_service()
    
    result = await service.create_scene(
        name=scene.name,
        actions=[a.model_dump() for a in scene.actions]
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.put("/{scene_id}")
async def update_scene(scene_id: str, scene: SceneUpdate):
    """Atualiza uma cena existente."""
    service = get_service()
    
    updates = {}
    if scene.name is not None:
        updates["name"] = scene.name
    if scene.description is not None:
        updates["description"] = scene.description
    if scene.icon is not None:
        updates["icon"] = scene.icon
    if scene.actions is not None:
        updates["actions"] = [a.model_dump() for a in scene.actions]
    
    result = await service.device_manager.update_scene(scene_id, updates)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.delete("/{scene_id}")
async def delete_scene(scene_id: str):
    """Remove uma cena."""
    service = get_service()
    result = await service.device_manager.delete_scene(scene_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/{scene_id}/execute")
async def execute_scene(scene_id: str):
    """
    Executa uma cena.
    
    Executa todas as ações configuradas na cena em sequência.
    """
    service = get_service()
    result = await service.execute_scene(scene_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/execute/name/{scene_name}")
async def execute_scene_by_name(scene_name: str):
    """
    Executa uma cena pelo nome.
    
    Busca a cena pelo nome (case-insensitive) e executa.
    """
    service = get_service()
    scenes = await service.get_scenes()
    
    # Buscar por nome
    scene = next(
        (s for s in scenes if s.get("name", "").lower() == scene_name.lower()),
        None
    )
    
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene '{scene_name}' not found")
    
    result = await service.execute_scene(scene["id"])
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.get("/templates/presets")
async def list_scene_presets():
    """Lista templates de cenas comuns."""
    return [
        {
            "id": "cinema",
            "name": "Cinema",
            "description": "Modo para assistir filmes",
            "icon": "🎬",
            "actions": [
                {"device_id": "sala_luz", "command": "dim", "value": 10},
                {"device_id": "led_tv", "command": "on"}
            ]
        },
        {
            "id": "jantar",
            "name": "Jantar",
            "description": "Iluminação para refeições",
            "icon": "🍽️",
            "actions": [
                {"device_id": "sala_jantar_luz", "command": "dim", "value": 70},
                {"device_id": "sala_jantar_luz", "command": "color", "value": "warm"}
            ]
        },
        {
            "id": "trabalho",
            "name": "Trabalho",
            "description": "Iluminação para home office",
            "icon": "💻",
            "actions": [
                {"device_id": "escritorio_luz", "command": "on"},
                {"device_id": "escritorio_luz", "command": "dim", "value": 100},
                {"device_id": "escritorio_luz", "command": "color", "value": "cool"}
            ]
        },
        {
            "id": "relaxar",
            "name": "Relaxar",
            "description": "Iluminação ambiente para relaxar",
            "icon": "🛋️",
            "actions": [
                {"device_id": "sala_luz", "command": "dim", "value": 30},
                {"device_id": "sala_luz", "command": "color", "value": "#FF8800"}
            ]
        },
        {
            "id": "saindo",
            "name": "Saindo",
            "description": "Desliga tudo ao sair de casa",
            "icon": "🚪",
            "actions": [
                {"device_id": "all_lights", "command": "off"},
                {"device_id": "all_devices", "command": "off"}
            ]
        },
        {
            "id": "festa",
            "name": "Festa",
            "description": "Modo festa com luzes coloridas",
            "icon": "🎉",
            "actions": [
                {"device_id": "sala_luz", "command": "color", "value": "#FF00FF"},
                {"device_id": "led_rgb", "command": "on"},
                {"device_id": "led_rgb", "command": "color", "value": "rainbow"}
            ]
        }
    ]
