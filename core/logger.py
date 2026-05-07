"""
core/logger.py
Sistema de logging centralizado para el proyecto.

Características:
- Salida a consola con colores (según nivel)
- Salida a archivo con rotación automática
- Formato consistente en todo el proyecto
- Fácil de extender para GUI (agregar handlers)

Uso:
    from core.logger import get_logger
    
    logger = get_logger(__name__)
    logger.info("Operación exitosa")
    logger.error("Algo falló", exc_info=True)
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional


# Directorio para archivos de log
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Formato de los mensajes
LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)-20s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Nivel por defecto (puede cambiarse desde config o variable de entorno)
DEFAULT_LOG_LEVEL = logging.INFO


class ColoredFormatter(logging.Formatter):
    """
    Formatter que agrega colores a los mensajes en consola.
    
    Los colores ayudan a identificar rápidamente el nivel:
    - DEBUG: Gris
    - INFO: Verde
    - WARNING: Amarillo
    - ERROR: Rojo
    - CRITICAL: Rojo con fondo
    """
    
    # Códigos ANSI para colores
    COLORS = {
        logging.DEBUG: "\033[90m",      # Gris
        logging.INFO: "\033[92m",       # Verde
        logging.WARNING: "\033[93m",    # Amarillo
        logging.ERROR: "\033[91m",      # Rojo
        logging.CRITICAL: "\033[97;41m" # Blanco sobre fondo rojo
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        # Guardar el formato original
        original_msg = super().format(record)
        
        # Agregar color según el nivel
        color = self.COLORS.get(record.levelno, self.RESET)
        return f"{color}{original_msg}{self.RESET}"


class LoggerManager:
    """
    Gestor centralizado de loggers.
    
    Implementa el patrón Singleton para asegurar que todos los módulos
    usen la misma configuración de logging.
    
    Atributos:
        _initialized: Indica si ya se configuró el logging
        _handlers: Lista de handlers activos (útil para GUI)
        _log_file: Ruta del archivo de log actual
    """
    
    _initialized: bool = False
    _handlers: list = []
    _log_file: Optional[Path] = None
    
    @classmethod
    def setup(
        cls,
        level: int = DEFAULT_LOG_LEVEL,
        log_to_file: bool = True,
        log_to_console: bool = True
    ) -> None:
        """
        Configura el sistema de logging.
        
        Args:
            level: Nivel mínimo de logs a registrar
            log_to_file: Si True, guarda logs en archivo
            log_to_console: Si True, muestra logs en consola
        
        Esta función solo se ejecuta una vez. Llamadas posteriores
        son ignoradas para evitar duplicación de handlers.
        """
        if cls._initialized:
            return
        
        # Obtener el logger raíz
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Limpiar handlers existentes (evita duplicados)
        root_logger.handlers.clear()
        cls._handlers.clear()
        
        # Handler de consola
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(
                ColoredFormatter(LOG_FORMAT, LOG_DATE_FORMAT)
            )
            root_logger.addHandler(console_handler)
            cls._handlers.append(console_handler)
        
        # Handler de archivo
        if log_to_file:
            # Nombre de archivo con fecha
            timestamp = datetime.now().strftime("%Y-%m-%d")
            cls._log_file = LOG_DIR / f"moodle_automation_{timestamp}.log"
            
            # RotatingFileHandler: máximo 5MB por archivo, mantiene 5 backups
            file_handler = RotatingFileHandler(
                cls._log_file,
                maxBytes=5 * 1024 * 1024,  # 5 MB
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(
                logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)
            )
            root_logger.addHandler(file_handler)
            cls._handlers.append(file_handler)
        
        cls._initialized = True
    
    @classmethod
    def add_handler(cls, handler: logging.Handler) -> None:
        """
        Agrega un handler personalizado.
        
        Útil para GUI: puedes agregar un handler que escriba
        en un widget de texto.
        
        Args:
            handler: Handler de logging a agregar
        
        Ejemplo para GUI (futuro):
            text_handler = TextWidgetHandler(text_widget)
            LoggerManager.add_handler(text_handler)
        """
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        cls._handlers.append(handler)
    
    @classmethod
    def set_level(cls, level: int) -> None:
        """
        Cambia el nivel de logging en tiempo de ejecución.
        
        Args:
            level: Nuevo nivel (logging.DEBUG, logging.INFO, etc.)
        """
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        for handler in cls._handlers:
            handler.setLevel(level)
    
    @classmethod
    def get_log_file(cls) -> Optional[Path]:
        """Retorna la ruta del archivo de log actual."""
        return cls._log_file


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger configurado para un módulo.
    
    Args:
        name: Nombre del módulo (usar __name__)
    
    Returns:
        Logger configurado
    
    Uso:
        from core.logger import get_logger
        
        logger = get_logger(__name__)
        logger.info("Mensaje informativo")
        logger.error("Error ocurrido", exc_info=True)  # Incluye traceback
    """
    # Asegurar que el logging está configurado
    LoggerManager.setup()
    
    return logging.getLogger(name)


# Función de conveniencia para inicializar manualmente
def setup_logging(
    level: int = DEFAULT_LOG_LEVEL,
    log_to_file: bool = True,
    log_to_console: bool = True
) -> None:
    """
    Inicializa el sistema de logging.
    
    Llamar al inicio de la aplicación para configuración personalizada.
    Si no se llama, get_logger() usa la configuración por defecto.
    
    Args:
        level: Nivel de logging (logging.DEBUG, logging.INFO, etc.)
        log_to_file: Guardar logs en archivo
        log_to_console: Mostrar logs en consola
    """
    LoggerManager.setup(level, log_to_file, log_to_console)