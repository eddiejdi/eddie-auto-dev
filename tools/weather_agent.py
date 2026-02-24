#!/usr/bin/env python3
"""Weather Monitoring Agent — coleta dados meteorológicos a cada 15 min e grava no Postgres.

Usa a API Open-Meteo (gratuita, sem API key) para obter:
- Temperatura (°C)
- Umidade relativa (%)
- Precipitação / chuva (mm)
- Pressão atmosférica (hPa)
- Velocidade do vento (km/h)
- Direção do vento (°)
- Rajada de vento (km/h)
- Nebulosidade (%)
- Radiação solar (W/m²)
- Índice UV
- Sensação térmica aparente (°C)
- Ponto de orvalho (°C)

Configuração via variáveis de ambiente:
    DATABASE_URL       — conexão Postgres (obrigatório)
    WEATHER_LATITUDE   — latitude (default: -23.5505 — São Paulo)
    WEATHER_LONGITUDE  — longitude (default: -46.6333 — São Paulo)
    WEATHER_INTERVAL   — intervalo em segundos (default: 900 = 15 min)
    WEATHER_LOCATION   — nome da localização (default: "São Paulo, BR")
    WEATHER_TIMEZONE   — timezone (default: "America/Sao_Paulo")

Uso:
    python tools/weather_agent.py              # loop contínuo (15 min)
    python tools/weather_agent.py --once       # coleta única e sai
    python tools/weather_agent.py --migrate    # apenas cria tabela e sai
    python tools/weather_agent.py --history 24 # últimas 24 horas de dados
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("weather_agent")

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
LATITUDE = float(os.environ.get("WEATHER_LATITUDE", "-23.5505"))
LONGITUDE = float(os.environ.get("WEATHER_LONGITUDE", "-46.6333"))
INTERVAL_SECONDS = int(os.environ.get("WEATHER_INTERVAL", "900"))  # 15 min
LOCATION_NAME = os.environ.get("WEATHER_LOCATION", "São Paulo, BR")
TIMEZONE = os.environ.get("WEATHER_TIMEZONE", "America/Sao_Paulo")

# Open-Meteo API — variáveis solicitadas
OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
CURRENT_PARAMS = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "snowfall",
    "cloud_cover",
    "pressure_msl",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "dew_point_2m",
    "uv_index",
    "shortwave_radiation",
    "weather_code",
    "is_day",
]

# WMO weather codes → descrição amigável
WMO_CODES = {
    0: "Céu limpo",
    1: "Predominantemente limpo",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Nevoeiro",
    48: "Nevoeiro com geada",
    51: "Garoa leve",
    53: "Garoa moderada",
    55: "Garoa densa",
    56: "Garoa congelante leve",
    57: "Garoa congelante densa",
    61: "Chuva leve",
    63: "Chuva moderada",
    65: "Chuva forte",
    66: "Chuva congelante leve",
    67: "Chuva congelante forte",
    71: "Neve leve",
    73: "Neve moderada",
    75: "Neve forte",
    77: "Grãos de neve",
    80: "Pancadas de chuva leve",
    81: "Pancadas de chuva moderada",
    82: "Pancadas de chuva violentas",
    85: "Pancadas de neve leve",
    86: "Pancadas de neve forte",
    95: "Trovoada",
    96: "Trovoada com granizo leve",
    99: "Trovoada com granizo forte",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class WeatherReading:
    """Leitura meteorológica pontual."""
    timestamp: datetime
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
    raw_json: Optional[Dict[str, Any]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Open-Meteo fetch
# ---------------------------------------------------------------------------
def fetch_weather(
    lat: float = LATITUDE,
    lon: float = LONGITUDE,
    tz: str = TIMEZONE,
) -> WeatherReading:
    """Busca dados atuais na Open-Meteo API (gratuita, sem key)."""

    params_str = ",".join(CURRENT_PARAMS)
    url = (
        f"{OPEN_METEO_BASE}"
        f"?latitude={lat}&longitude={lon}"
        f"&current={params_str}"
        f"&timezone={tz}"
    )

    logger.debug("GET %s", url)
    req = Request(url, headers={"User-Agent": "eddie-weather-agent/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, OSError) as exc:
        logger.error("Falha ao buscar Open-Meteo: %s", exc)
        raise

    current = data.get("current", {})
    wcode = current.get("weather_code")

    reading = WeatherReading(
        timestamp=datetime.now(timezone.utc),
        location=LOCATION_NAME,
        latitude=lat,
        longitude=lon,
        temperature_c=current.get("temperature_2m"),
        apparent_temperature_c=current.get("apparent_temperature"),
        humidity_pct=current.get("relative_humidity_2m"),
        dew_point_c=current.get("dew_point_2m"),
        precipitation_mm=current.get("precipitation"),
        rain_mm=current.get("rain"),
        snowfall_cm=current.get("snowfall"),
        cloud_cover_pct=current.get("cloud_cover"),
        pressure_msl_hpa=current.get("pressure_msl"),
        surface_pressure_hpa=current.get("surface_pressure"),
        wind_speed_kmh=current.get("wind_speed_10m"),
        wind_direction_deg=current.get("wind_direction_10m"),
        wind_gusts_kmh=current.get("wind_gusts_10m"),
        uv_index=current.get("uv_index"),
        solar_radiation_wm2=current.get("shortwave_radiation"),
        weather_code=wcode,
        weather_description=WMO_CODES.get(wcode, f"Código {wcode}") if wcode is not None else None,
        is_day=bool(current.get("is_day")) if current.get("is_day") is not None else None,
        raw_json=data,
    )
    return reading


# ---------------------------------------------------------------------------
# PostgreSQL persistence
# ---------------------------------------------------------------------------
def _get_conn():
    """Cria conexão Postgres."""
    import psycopg2
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não definida — impossível gravar no Postgres")
    return psycopg2.connect(DATABASE_URL)


def init_table():
    """Cria tabela weather_readings se não existir."""
    sql = """
    CREATE TABLE IF NOT EXISTS weather_readings (
        id              SERIAL PRIMARY KEY,
        recorded_at     TIMESTAMP WITH TIME ZONE DEFAULT now(),
        location        TEXT NOT NULL,
        latitude        DOUBLE PRECISION,
        longitude       DOUBLE PRECISION,
        temperature_c   DOUBLE PRECISION,
        apparent_temperature_c DOUBLE PRECISION,
        humidity_pct    DOUBLE PRECISION,
        dew_point_c     DOUBLE PRECISION,
        precipitation_mm DOUBLE PRECISION,
        rain_mm         DOUBLE PRECISION,
        snowfall_cm     DOUBLE PRECISION,
        cloud_cover_pct DOUBLE PRECISION,
        pressure_msl_hpa DOUBLE PRECISION,
        surface_pressure_hpa DOUBLE PRECISION,
        wind_speed_kmh  DOUBLE PRECISION,
        wind_direction_deg DOUBLE PRECISION,
        wind_gusts_kmh  DOUBLE PRECISION,
        uv_index        DOUBLE PRECISION,
        solar_radiation_wm2 DOUBLE PRECISION,
        weather_code    INTEGER,
        weather_description TEXT,
        is_day          BOOLEAN,
        raw_json        JSONB
    );

    -- Índices para consultas comuns
    CREATE INDEX IF NOT EXISTS idx_weather_recorded_at ON weather_readings(recorded_at DESC);
    CREATE INDEX IF NOT EXISTS idx_weather_location    ON weather_readings(location);
    CREATE INDEX IF NOT EXISTS idx_weather_location_time ON weather_readings(location, recorded_at DESC);
    """
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        logger.info("✅ Tabela weather_readings pronta")
    finally:
        conn.close()


def save_reading(reading: WeatherReading) -> int:
    """Insere leitura no Postgres e retorna o ID."""
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO weather_readings (
                        recorded_at, location, latitude, longitude,
                        temperature_c, apparent_temperature_c, humidity_pct, dew_point_c,
                        precipitation_mm, rain_mm, snowfall_cm,
                        cloud_cover_pct, pressure_msl_hpa, surface_pressure_hpa,
                        wind_speed_kmh, wind_direction_deg, wind_gusts_kmh,
                        uv_index, solar_radiation_wm2,
                        weather_code, weather_description, is_day,
                        raw_json
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s
                    ) RETURNING id
                    """,
                    (
                        reading.timestamp, reading.location, reading.latitude, reading.longitude,
                        reading.temperature_c, reading.apparent_temperature_c,
                        reading.humidity_pct, reading.dew_point_c,
                        reading.precipitation_mm, reading.rain_mm, reading.snowfall_cm,
                        reading.cloud_cover_pct, reading.pressure_msl_hpa, reading.surface_pressure_hpa,
                        reading.wind_speed_kmh, reading.wind_direction_deg, reading.wind_gusts_kmh,
                        reading.uv_index, reading.solar_radiation_wm2,
                        reading.weather_code, reading.weather_description, reading.is_day,
                        json.dumps(reading.raw_json) if reading.raw_json else None,
                    ),
                )
                row_id = cur.fetchone()[0]
                return row_id
    finally:
        conn.close()


def get_latest(location: str = LOCATION_NAME, limit: int = 1) -> List[Dict]:
    """Retorna as últimas N leituras."""
    conn = _get_conn()
    try:
        import psycopg2.extras
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM weather_readings
                WHERE location = %s
                ORDER BY recorded_at DESC
                LIMIT %s
                """,
                (location, limit),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_history(hours: int = 24, location: str = LOCATION_NAME) -> List[Dict]:
    """Retorna leituras das últimas N horas."""
    conn = _get_conn()
    try:
        import psycopg2.extras
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, recorded_at, temperature_c, apparent_temperature_c,
                       humidity_pct, precipitation_mm, rain_mm, cloud_cover_pct,
                       pressure_msl_hpa, wind_speed_kmh, wind_gusts_kmh,
                       uv_index, weather_description, is_day
                FROM weather_readings
                WHERE location = %s AND recorded_at >= now() - interval '%s hours'
                ORDER BY recorded_at ASC
                """,
                (location, hours),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_daily_summary(location: str = LOCATION_NAME, days: int = 7) -> List[Dict]:
    """Resumo diário agregado (média, min, max) dos últimos N dias."""
    conn = _get_conn()
    try:
        import psycopg2.extras
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    date_trunc('day', recorded_at AT TIME ZONE %s) AS day,
                    COUNT(*) as readings,
                    ROUND(AVG(temperature_c)::numeric, 1) AS avg_temp,
                    ROUND(MIN(temperature_c)::numeric, 1) AS min_temp,
                    ROUND(MAX(temperature_c)::numeric, 1) AS max_temp,
                    ROUND(AVG(humidity_pct)::numeric, 1) AS avg_humidity,
                    ROUND(SUM(COALESCE(rain_mm, 0))::numeric, 1) AS total_rain_mm,
                    ROUND(AVG(pressure_msl_hpa)::numeric, 1) AS avg_pressure,
                    ROUND(AVG(wind_speed_kmh)::numeric, 1) AS avg_wind,
                    ROUND(MAX(wind_gusts_kmh)::numeric, 1) AS max_gusts,
                    ROUND(MAX(COALESCE(uv_index, 0))::numeric, 1) AS max_uv
                FROM weather_readings
                WHERE location = %s
                  AND recorded_at >= now() - interval '%s days'
                GROUP BY day
                ORDER BY day DESC
                """,
                (TIMEZONE, location, days),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Coleta + gravação
# ---------------------------------------------------------------------------
def collect_and_save() -> Optional[int]:
    """Busca dados meteorológicos e grava no Postgres. Retorna ID do registro."""
    try:
        reading = fetch_weather()
        row_id = save_reading(reading)

        logger.info(
            "🌤️  [%s] %.1f°C  💧 %s%%  🌧️ %.1fmm  💨 %.1fkm/h  ☁️ %s%%  — %s  (id=%d)",
            reading.location,
            reading.temperature_c or 0,
            reading.humidity_pct or "?",
            reading.rain_mm or 0,
            reading.wind_speed_kmh or 0,
            reading.cloud_cover_pct or "?",
            reading.weather_description or "?",
            row_id,
        )
        return row_id

    except Exception as exc:
        logger.error("❌ Erro na coleta: %s", exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------
_running = True


def _handle_signal(signum, _frame):
    global _running
    logger.info("Sinal %s recebido — encerrando...", signal.Signals(signum).name)
    _running = False


def run_loop(interval: int = INTERVAL_SECONDS):
    """Loop contínuo de coleta a cada `interval` segundos."""
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info(
        "🚀 Weather Agent iniciado — %s (%.4f, %.4f) — intervalo: %ds",
        LOCATION_NAME, LATITUDE, LONGITUDE, interval,
    )
    init_table()

    while _running:
        collect_and_save()
        # Sleep interruptível
        waited = 0
        while waited < interval and _running:
            time.sleep(min(5, interval - waited))
            waited += 5

    logger.info("Weather Agent encerrado.")


# ---------------------------------------------------------------------------
# Formatação para exibição
# ---------------------------------------------------------------------------
def format_reading(reading: WeatherReading) -> str:
    """Formata leitura para exibição (Telegram, CLI, etc)."""
    lines = [
        f"🌡️ **{reading.location}** — {reading.timestamp.strftime('%d/%m/%Y %H:%M')}",
        f"",
        f"🌡️ Temperatura: {reading.temperature_c}°C (sensação: {reading.apparent_temperature_c}°C)",
        f"💧 Umidade: {reading.humidity_pct}%",
        f"🌧️ Precipitação: {reading.precipitation_mm}mm (chuva: {reading.rain_mm}mm)",
        f"☁️ Nebulosidade: {reading.cloud_cover_pct}%",
        f"🔵 Pressão: {reading.pressure_msl_hpa} hPa",
        f"💨 Vento: {reading.wind_speed_kmh} km/h (rajadas: {reading.wind_gusts_kmh} km/h) dir: {reading.wind_direction_deg}°",
        f"☀️ UV: {reading.uv_index} | Radiação: {reading.solar_radiation_wm2} W/m²",
        f"🌿 Ponto de orvalho: {reading.dew_point_c}°C",
        f"",
        f"📋 Condição: {reading.weather_description}",
        f"{'🌞 Dia' if reading.is_day else '🌙 Noite'}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Weather Monitoring Agent")
    parser.add_argument("--once", action="store_true", help="Coleta única e sai")
    parser.add_argument("--migrate", action="store_true", help="Apenas cria tabela e sai")
    parser.add_argument("--history", type=int, metavar="HOURS", help="Mostra histórico das últimas N horas")
    parser.add_argument("--summary", type=int, metavar="DAYS", help="Resumo diário dos últimos N dias")
    parser.add_argument("--latest", action="store_true", help="Mostra última leitura")
    parser.add_argument("--interval", type=int, default=INTERVAL_SECONDS, help=f"Intervalo em segundos (default: {INTERVAL_SECONDS})")
    parser.add_argument("--fetch-only", action="store_true", help="Apenas busca da API e exibe (sem gravar)")
    args = parser.parse_args()

    if args.fetch_only:
        reading = fetch_weather()
        print(format_reading(reading))
        return

    if args.migrate:
        init_table()
        return

    if args.latest:
        rows = get_latest()
        if rows:
            for r in rows:
                print(json.dumps(r, indent=2, default=str))
        else:
            print("Nenhuma leitura encontrada.")
        return

    if args.history:
        rows = get_history(args.history)
        print(f"📊 {len(rows)} leituras nas últimas {args.history}h:")
        for r in rows:
            print(
                f"  {r['recorded_at']}  {r['temperature_c']}°C  "
                f"{r['humidity_pct']}%  {r['rain_mm']}mm  "
                f"{r['weather_description']}"
            )
        return

    if args.summary:
        rows = get_daily_summary(days=args.summary)
        print(f"📊 Resumo diário ({args.summary} dias):")
        for r in rows:
            print(
                f"  {r['day']}  "
                f"🌡️ {r['min_temp']}–{r['max_temp']}°C (avg {r['avg_temp']})  "
                f"🌧️ {r['total_rain_mm']}mm  💧 {r['avg_humidity']}%  "
                f"💨 {r['avg_wind']}km/h  ({r['readings']} leituras)"
            )
        return

    if args.once:
        init_table()
        result = collect_and_save()
        if result:
            print(f"✅ Leitura gravada (id={result})")
        else:
            print("❌ Falha na coleta")
            sys.exit(1)
        return

    # Loop contínuo
    run_loop(interval=args.interval)


if __name__ == "__main__":
    main()
