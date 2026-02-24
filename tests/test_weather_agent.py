#!/usr/bin/env python3
"""Testes unitários para o Weather Monitoring Agent."""

import json
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.weather_agent import (
    WMO_CODES,
    WeatherReading,
    fetch_weather,
    format_reading,
)


# ---------------------------------------------------------------------------
# Fixture: resposta simulada da Open-Meteo
# ---------------------------------------------------------------------------
MOCK_OPEN_METEO_RESPONSE = {
    "latitude": -23.5505,
    "longitude": -46.6333,
    "timezone": "America/Sao_Paulo",
    "current": {
        "time": "2026-02-23T14:00",
        "temperature_2m": 28.5,
        "relative_humidity_2m": 65,
        "apparent_temperature": 30.2,
        "precipitation": 0.0,
        "rain": 0.0,
        "snowfall": 0.0,
        "cloud_cover": 40,
        "pressure_msl": 1013.2,
        "surface_pressure": 935.8,
        "wind_speed_10m": 12.5,
        "wind_direction_10m": 180,
        "wind_gusts_10m": 22.3,
        "dew_point_2m": 20.1,
        "uv_index": 8.5,
        "shortwave_radiation": 650.0,
        "weather_code": 2,
        "is_day": 1,
    },
}


@pytest.fixture
def mock_reading() -> WeatherReading:
    return WeatherReading(
        timestamp=datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc),
        location="São Paulo, BR",
        latitude=-23.5505,
        longitude=-46.6333,
        temperature_c=28.5,
        apparent_temperature_c=30.2,
        humidity_pct=65,
        dew_point_c=20.1,
        precipitation_mm=0.0,
        rain_mm=0.0,
        snowfall_cm=0.0,
        cloud_cover_pct=40,
        pressure_msl_hpa=1013.2,
        surface_pressure_hpa=935.8,
        wind_speed_kmh=12.5,
        wind_direction_deg=180,
        wind_gusts_kmh=22.3,
        uv_index=8.5,
        solar_radiation_wm2=650.0,
        weather_code=2,
        weather_description="Parcialmente nublado",
        is_day=True,
        raw_json=MOCK_OPEN_METEO_RESPONSE,
    )


# ---------------------------------------------------------------------------
# Tests: WeatherReading dataclass
# ---------------------------------------------------------------------------
class TestWeatherReading:
    def test_create_minimal(self):
        r = WeatherReading(
            timestamp=datetime.now(timezone.utc),
            location="Test",
            latitude=0.0,
            longitude=0.0,
        )
        assert r.location == "Test"
        assert r.temperature_c is None

    def test_all_fields(self, mock_reading):
        assert mock_reading.temperature_c == 28.5
        assert mock_reading.humidity_pct == 65
        assert mock_reading.rain_mm == 0.0
        assert mock_reading.weather_description == "Parcialmente nublado"
        assert mock_reading.is_day is True


# ---------------------------------------------------------------------------
# Tests: WMO codes
# ---------------------------------------------------------------------------
class TestWMOCodes:
    def test_clear_sky(self):
        assert WMO_CODES[0] == "Céu limpo"

    def test_thunderstorm(self):
        assert WMO_CODES[95] == "Trovoada"

    def test_heavy_rain(self):
        assert WMO_CODES[65] == "Chuva forte"

    def test_all_codes_are_strings(self):
        for code, desc in WMO_CODES.items():
            assert isinstance(code, int)
            assert isinstance(desc, str)
            assert len(desc) > 0


# ---------------------------------------------------------------------------
# Tests: fetch_weather (mocked HTTP)
# ---------------------------------------------------------------------------
class TestFetchWeather:
    @patch("tools.weather_agent.urlopen")
    def test_fetch_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(MOCK_OPEN_METEO_RESPONSE).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        reading = fetch_weather(lat=-23.5505, lon=-46.6333)

        assert reading.temperature_c == 28.5
        assert reading.humidity_pct == 65
        assert reading.rain_mm == 0.0
        assert reading.pressure_msl_hpa == 1013.2
        assert reading.wind_speed_kmh == 12.5
        assert reading.weather_code == 2
        assert reading.weather_description == "Parcialmente nublado"
        assert reading.is_day is True
        assert reading.uv_index == 8.5

    @patch("tools.weather_agent.urlopen")
    def test_fetch_handles_missing_fields(self, mock_urlopen):
        minimal_response = {"current": {"temperature_2m": 25.0}}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(minimal_response).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        reading = fetch_weather()
        assert reading.temperature_c == 25.0
        assert reading.humidity_pct is None
        assert reading.rain_mm is None

    @patch("tools.weather_agent.urlopen")
    def test_fetch_network_error(self, mock_urlopen):
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Network unreachable")

        with pytest.raises(URLError):
            fetch_weather()


# ---------------------------------------------------------------------------
# Tests: format_reading
# ---------------------------------------------------------------------------
class TestFormatReading:
    def test_format_contains_key_data(self, mock_reading):
        output = format_reading(mock_reading)
        assert "28.5°C" in output
        assert "65%" in output
        assert "São Paulo" in output
        assert "Parcialmente nublado" in output
        assert "12.5 km/h" in output
        assert "Dia" in output

    def test_format_night(self, mock_reading):
        mock_reading.is_day = False
        output = format_reading(mock_reading)
        assert "Noite" in output


# ---------------------------------------------------------------------------
# Tests: DB functions (mocked psycopg2)
# ---------------------------------------------------------------------------
class TestDBFunctions:
    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"})
    @patch("tools.weather_agent.psycopg2.connect" if False else "psycopg2.connect")
    def test_init_table(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Recarregar com DATABASE_URL setado
        import importlib
        import tools.weather_agent as wa
        wa.DATABASE_URL = "postgresql://test:test@localhost/test"
        wa.init_table()

        mock_cursor.execute.assert_called_once()
        call_sql = mock_cursor.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS weather_readings" in call_sql

    @patch("psycopg2.connect")
    def test_save_reading(self, mock_connect, mock_reading):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (42,)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        import tools.weather_agent as wa
        wa.DATABASE_URL = "postgresql://test:test@localhost/test"
        row_id = wa.save_reading(mock_reading)

        assert row_id == 42
        assert mock_cursor.execute.called
        call_sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO weather_readings" in call_sql


# ---------------------------------------------------------------------------
# Tests: collect_and_save (integration mock)
# ---------------------------------------------------------------------------
class TestCollectAndSave:
    @patch("tools.weather_agent.save_reading", return_value=99)
    @patch("tools.weather_agent.fetch_weather")
    def test_collect_success(self, mock_fetch, mock_save, mock_reading):
        mock_fetch.return_value = mock_reading

        import tools.weather_agent as wa
        result = wa.collect_and_save()

        assert result == 99
        mock_fetch.assert_called_once()
        mock_save.assert_called_once()

    @patch("tools.weather_agent.fetch_weather", side_effect=Exception("API down"))
    def test_collect_handles_error(self, mock_fetch):
        import tools.weather_agent as wa
        result = wa.collect_and_save()

        assert result is None
