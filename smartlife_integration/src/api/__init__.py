"""
SmartLife API Package
"""
from .app import app, create_app
from .routes import devices, automations, scenes, users

__all__ = [
    "app",
    "create_app",
    "devices",
    "automations",
    "scenes",
    "users"
]
