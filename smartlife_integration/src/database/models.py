"""
SmartLife Database Models
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, 
    JSON, ForeignKey, Text, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
import enum


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models."""
    pass


class DeviceType(str, enum.Enum):
    """Tipos de dispositivos suportados."""
    SWITCH = "switch"
    LIGHT = "light"
    DIMMER = "dimmer"
    SOCKET = "socket"
    POWER_STRIP = "power_strip"
    AIRCONDITIONER = "airconditioner"
    HEATER = "heater"
    FAN = "fan"
    HUMIDIFIER = "humidifier"
    COVER = "cover"
    LOCK = "lock"
    SENSOR = "sensor"
    MOTION = "motion"
    DOOR = "door"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CAMERA = "camera"
    IR_REMOTE = "ir_remote"
    THERMOSTAT = "thermostat"
    ROBOT_VACUUM = "robot_vacuum"
    UNKNOWN = "unknown"


class UserRole(str, enum.Enum):
    """Roles de usuário."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class AutomationTriggerType(str, enum.Enum):
    """Tipos de trigger para automações."""
    TIME = "time"
    DEVICE_STATE = "device_state"
    SENSOR = "sensor"
    SUNSET = "sunset"
    SUNRISE = "sunrise"
    WEBHOOK = "webhook"
    MANUAL = "manual"


class Device(Base):
    """Modelo de dispositivo SmartLife."""
    __tablename__ = "devices"
    
    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    type = Column(SQLEnum(DeviceType), default=DeviceType.UNKNOWN)
    category = Column(String(32))
    icon = Column(String(16))
    
    # Tuya info
    local_key = Column(String(64))
    ip_address = Column(String(45))
    tuya_version = Column(String(8), default="3.3")
    product_id = Column(String(64))
    product_name = Column(String(128))
    
    # Estado
    is_online = Column(Boolean, default=False)
    last_online = Column(DateTime)
    current_state = Column(JSON, default={})
    
    # Organização
    room = Column(String(64))
    floor = Column(String(32))
    tags = Column(JSON, default=[])
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    permissions = relationship("Permission", back_populates="device", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="device", cascade="all, delete-orphan")


class User(Base):
    """Modelo de usuário."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.USER)
    
    # Identidades
    telegram_id = Column(Integer, unique=True, index=True)
    whatsapp_id = Column(String(32), unique=True, index=True)
    email = Column(String(256), unique=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    last_activity = Column(DateTime)
    
    # Preferências
    language = Column(String(8), default="pt-br")
    timezone = Column(String(64), default="America/Sao_Paulo")
    preferences = Column(JSON, default={})
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    permissions = relationship("Permission", back_populates="user", cascade="all, delete-orphan")


class Permission(Base):
    """Permissões de usuário por dispositivo."""
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(String(64), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    
    # Permissões granulares
    can_view = Column(Boolean, default=True)
    can_control = Column(Boolean, default=False)
    can_configure = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    user = relationship("User", back_populates="permissions")
    device = relationship("Device", back_populates="permissions")


class Automation(Base):
    """Modelo de automação."""
    __tablename__ = "automations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    description = Column(Text)
    
    # Configuração
    is_enabled = Column(Boolean, default=True)
    trigger_type = Column(SQLEnum(AutomationTriggerType), nullable=False)
    trigger_config = Column(JSON, nullable=False)
    conditions = Column(JSON, default=[])
    actions = Column(JSON, nullable=False)
    
    # Execução
    last_executed = Column(DateTime)
    execution_count = Column(Integer, default=0)
    last_error = Column(Text)
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Scene(Base):
    """Modelo de cena (grupo de ações)."""
    __tablename__ = "scenes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    description = Column(Text)
    icon = Column(String(16))
    
    # Ações da cena
    actions = Column(JSON, nullable=False)
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    execution_count = Column(Integer, default=0)
    last_executed = Column(DateTime)


class Event(Base):
    """Log de eventos do sistema."""
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(32), nullable=False, index=True)
    
    # Associações
    device_id = Column(String(64), ForeignKey("devices.id", ondelete="SET NULL"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    automation_id = Column(Integer, ForeignKey("automations.id", ondelete="SET NULL"))
    
    # Dados do evento
    data = Column(JSON)
    message = Column(Text)
    severity = Column(String(16), default="info")  # info, warning, error
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relacionamentos
    device = relationship("Device", back_populates="events")


class DeviceState(Base):
    """Histórico de estados de dispositivos (para gráficos)."""
    __tablename__ = "device_states"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Estado
    state = Column(JSON, nullable=False)
    is_online = Column(Boolean)
    
    # Métricas (se aplicável)
    power = Column(Float)  # watts
    current = Column(Float)  # amperes
    voltage = Column(Float)  # volts
    energy = Column(Float)  # kwh
    temperature = Column(Float)
    humidity = Column(Float)
    
    # Timestamp
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
