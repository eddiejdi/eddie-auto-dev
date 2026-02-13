"""
Home Automation Agent — Google Assistant Integration
Controla dispositivos smart home via Google Home / Assistant APIs + Home Assistant.
"""

from .agent import GoogleAssistantAgent, get_google_assistant_agent
from .device_manager import DeviceManager, Device, DeviceType, DeviceState

# Conditional imports for optional dependencies
try:
    from .routes import router as home_automation_router
except ImportError:
    home_automation_router = None  # type: ignore

try:
    from .tinytuya_executor import TinyTuyaExecutor, get_executor, set_executor
except ImportError:
    TinyTuyaExecutor = None  # type: ignore
    get_executor = None  # type: ignore
    set_executor = None  # type: ignore

try:
    from .google_assistant import router as google_assistant_router
except ImportError:
    google_assistant_router = None  # type: ignore

try:
    from .ha_adapter import HomeAssistantAdapter
except ImportError:
    HomeAssistantAdapter = None  # type: ignore

__all__ = [
    "GoogleAssistantAgent",
    "get_google_assistant_agent",
    "DeviceManager",
    "Device",
    "DeviceType",
    "DeviceState",
    "home_automation_router",
    "google_assistant_router",
    "HomeAssistantAdapter",
    "set_executor",
]
