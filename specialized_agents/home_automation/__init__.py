"""
Home Automation Agent — Google Assistant Integration
Controla dispositivos smart home via Google Home / Assistant APIs.
"""

from .agent import GoogleAssistantAgent, get_google_assistant_agent
from .device_manager import DeviceManager, Device, DeviceType, DeviceState
from .routes import router as home_automation_router
from .tinytuya_executor import TinyTuyaExecutor, get_executor, set_executor
from .google_assistant import router as google_assistant_router

__all__ = [
    "GoogleAssistantAgent",
    "get_google_assistant_agent",
    "DeviceManager",
    "Device",
    "DeviceType",
    "DeviceState",
    "home_automation_router",
    "google_assistant_router",
    "TinyTuyaExecutor",
    "get_executor",
    "set_executor",
]
