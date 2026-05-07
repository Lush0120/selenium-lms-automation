"""
core/__init__.py
Módulo core - Componentes básicos (Átomos)
"""

from core.config import settings
from core.logger import get_logger
from core.browser import BrowserManager
from core.exceptions import (
    MoodleAutomationError,
    BrowserError,
    AuthenticationError,
    UserError,
    CourseError,
)

__all__ = [
    "settings",
    "get_logger",
    "BrowserManager",
    "MoodleAutomationError",
    "BrowserError",
    "AuthenticationError",
    "UserError",
    "CourseError",
]