"""FastAPI routes para o Weather Monitoring Agent.

Endpoints:
    GET  /weather/current        — leitura atual (tempo real da API)
    GET  /weather/latest         — última leitura gravada no Postgres
    GET  /weather/history        — leituras das últimas N horas
    GET  /weather/summary        — resumo diário dos últimos N dias
    POST /weather/collect        — força coleta + gravação imediata
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger("weather_routes")

router = APIRouter(prefix="/weather", tags=["weather"])

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class WeatherCurrentResponse(BaseModel):
    location: str
    latitude: float
    longitude: float
    temperature_c: Optional[float] = None
    apparent_temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    dew_point_c: Optional[float] = None
    precipitation_mm: Optional[float] = None
    rain_mm: Optional[float] = None
    snowfall_cm: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    pressure_msl_hpa: Optional[float] = None
    surface_pressure_hpa: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    wind_gusts_kmh: Optional[float] = None
    uv_index: Optional[float] = None
    solar_radiation_wm2: Optional[float] = None
    weather_code: Optional[int] = None
    weather_description: Optional[str] = None
    is_day: Optional[bool] = None
    timestamp: str


class CollectResponse(BaseModel):
    success: bool
    record_id: Optional[int] = None
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/current", response_model=WeatherCurrentResponse, summary="Dados meteorológicos em tempo real")
async def weather_current():
    """Busca dados atuais direto da Open-Meteo API (sem gravar no DB)."""
    try:
        from tools.weather_agent import fetch_weather
        reading = fetch_weather()
        return WeatherCurrentResponse(
            location=reading.location,
            latitude=reading.latitude,
            longitude=reading.longitude,
            temperature_c=reading.temperature_c,
            apparent_temperature_c=reading.apparent_temperature_c,
            humidity_pct=reading.humidity_pct,
            dew_point_c=reading.dew_point_c,
            precipitation_mm=reading.precipitation_mm,
            rain_mm=reading.rain_mm,
            snowfall_cm=reading.snowfall_cm,
            cloud_cover_pct=reading.cloud_cover_pct,
            pressure_msl_hpa=reading.pressure_msl_hpa,
            surface_pressure_hpa=reading.surface_pressure_hpa,
            wind_speed_kmh=reading.wind_speed_kmh,
            wind_direction_deg=reading.wind_direction_deg,
            wind_gusts_kmh=reading.wind_gusts_kmh,
            uv_index=reading.uv_index,
            solar_radiation_wm2=reading.solar_radiation_wm2,
            weather_code=reading.weather_code,
            weather_description=reading.weather_description,
            is_day=reading.is_day,
            timestamp=reading.timestamp.isoformat(),
        )
    except Exception as exc:
        logger.error("Erro ao buscar clima: %s", exc)
        raise HTTPException(status_code=502, detail=f"Erro na API Open-Meteo: {exc}")


@router.get("/latest", summary="Últimas N leituras gravadas")
async def weather_latest(limit: int = Query(1, ge=1, le=100)):
    """Retorna as últimas leituras salvas no Postgres."""
    try:
        from tools.weather_agent import get_latest
        rows = get_latest(limit=limit)
        return {"count": len(rows), "readings": rows}
    except Exception as exc:
        logger.error("Erro ao buscar latest: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/history", summary="Histórico de leituras")
async def weather_history(
    hours: int = Query(24, ge=1, le=720, description="Últimas N horas"),
):
    """Retorna leituras das últimas N horas."""
    try:
        from tools.weather_agent import get_history
        rows = get_history(hours=hours)
        return {"hours": hours, "count": len(rows), "readings": rows}
    except Exception as exc:
        logger.error("Erro ao buscar history: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/summary", summary="Resumo diário agregado")
async def weather_summary(
    days: int = Query(7, ge=1, le=90, description="Últimos N dias"),
):
    """Retorna resumo diário (avg, min, max) dos últimos N dias."""
    try:
        from tools.weather_agent import get_daily_summary
        rows = get_daily_summary(days=days)
        return {"days": days, "count": len(rows), "summary": rows}
    except Exception as exc:
        logger.error("Erro ao buscar summary: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/collect", response_model=CollectResponse, summary="Força coleta imediata")
async def weather_collect():
    """Busca dados meteorológicos e grava no Postgres imediatamente."""
    try:
        from tools.weather_agent import collect_and_save
        row_id = collect_and_save()
        if row_id:
            return CollectResponse(success=True, record_id=row_id, message=f"Leitura gravada (id={row_id})")
        else:
            return CollectResponse(success=False, message="Falha na coleta")
    except Exception as exc:
        logger.error("Erro ao coletar: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
