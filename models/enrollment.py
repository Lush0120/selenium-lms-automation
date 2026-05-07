"""
models/enrollment.py
Modelos de datos para matrículas en Moodle.

Define las estructuras para:
- Datos de matrícula (EnrollmentData)
- Resultado de operaciones de matrícula (EnrollmentResult)
- Configuración de matrícula (EnrollmentConfig)
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, computed_field


class EnrollmentStatus(str, Enum):
    """Estados posibles de una matrícula."""
    ACTIVO = "Activo"
    NO_ACTIVO = "No activo"
    SUSPENDIDO = "Suspendido"
    
    @classmethod
    def from_text(cls, text: str) -> "EnrollmentStatus":
        """Convierte texto a EnrollmentStatus."""
        text_lower = text.lower().strip()
        if "no activo" in text_lower:
            return cls.NO_ACTIVO
        elif "suspendido" in text_lower:
            return cls.SUSPENDIDO
        elif "activo" in text_lower:
            return cls.ACTIVO
        return cls.NO_ACTIVO


class EnrollmentRole(str, Enum):
    """Roles disponibles para matrícula."""
    GESTOR = "1"
    PROFESOR = "3"
    PROFESOR_SIN_EDICION = "4"
    ESTUDIANTE = "5"
    ESTUDIANTE_RECLUTADOR = "9"
    SMOWL_USER = "11"
    
    @property
    def display_name(self) -> str:
        """Nombre legible del rol."""
        names = {
            "1": "Gestor",
            "3": "Profesor",
            "4": "Profesor sin permiso de edición",
            "5": "Estudiante",
            "9": "Estudiante Reclutador",
            "11": "SMOWL WebService User"
        }
        return names.get(self.value, "Estudiante")


class EnrollmentDuration(int, Enum):
    """Duraciones predefinidas de matrícula en segundos."""
    UN_DIA = 86400
    DOS_DIAS = 172800
    TRES_DIAS = 259200
    
    @property
    def days(self) -> int:
        """Retorna el número de días."""
        return self.value // 86400
    
    @property
    def display_name(self) -> str:
        """Nombre legible."""
        return f"{self.days} día{'s' if self.days > 1 else ''}"
    
    @classmethod
    def from_days(cls, days: int) -> "EnrollmentDuration":
        """Crea EnrollmentDuration desde número de días."""
        mapping = {1: cls.UN_DIA, 2: cls.DOS_DIAS, 3: cls.TRES_DIAS}
        return mapping.get(days, cls.UN_DIA)


class EnrollmentConfig(BaseModel):
    """
    Configuración para una matrícula nueva.
    
    Attributes:
        role: Rol a asignar (por defecto Estudiante)
        duration: Duración de la matrícula
        start_now: Si iniciar desde ahora
    """
    role: EnrollmentRole = EnrollmentRole.ESTUDIANTE
    duration: EnrollmentDuration = EnrollmentDuration.UN_DIA
    start_now: bool = True
    
    @property
    def duration_seconds(self) -> int:
        """Duración en segundos."""
        return self.duration.value
    
    @property
    def duration_days(self) -> int:
        """Duración en días."""
        return self.duration.days


class EnrollmentData(BaseModel):
    """
    Datos de una matrícula existente.
    
    Contiene la información extraída de los detalles
    de matrícula de un usuario en un curso.
    
    Attributes:
        user_id: ID del usuario en Moodle
        user_fullname: Nombre completo del usuario
        user_email: Email del usuario
        course_id: ID del curso
        course_name: Nombre del curso
        enrollment_id: ID de la matrícula (ue)
        status: Estado de la matrícula
        method: Método de matriculación
        time_start: Fecha/hora de inicio
        time_end: Fecha/hora de fin
        time_enrolled: Fecha/hora de creación
    """
    user_id: str
    user_fullname: str
    user_email: str
    course_id: str
    course_name: str
    enrollment_id: Optional[str] = None  # ue parameter
    status: EnrollmentStatus = EnrollmentStatus.NO_ACTIVO
    method: str = "Matriculación manual"
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    time_enrolled: Optional[str] = None
    
    @property
    def is_active(self) -> bool:
        """Si la matrícula está activa."""
        return self.status == EnrollmentStatus.ACTIVO
    
    def to_summary(self) -> str:
        """Genera resumen de la matrícula."""
        lines = [
            f"👤 Usuario: {self.user_fullname}",
            f"📧 Email: {self.user_email}",
            f"📚 Curso: {self.course_name}",
            f"📋 Estado: {self.status.value}",
        ]
        if self.time_start:
            lines.append(f"🕐 Inicio: {self.time_start}")
        if self.time_end:
            lines.append(f"🕐 Fin: {self.time_end}")
        return "\n".join(lines)


class EnrollmentResult(BaseModel):
    """
    Resultado de una operación de matrícula.
    
    Attributes:
        success: Si la operación fue exitosa
        action: Acción realizada (created, updated, already_enrolled)
        enrollment: Datos de la matrícula (si exitoso)
        message: Mensaje descriptivo
        error: Mensaje de error (si falló)
    """
    success: bool
    action: str  # "created", "updated", "already_active", "error"
    enrollment: Optional[EnrollmentData] = None
    message: str = ""
    error: Optional[str] = None
    
    @classmethod
    def created(cls, enrollment: EnrollmentData) -> "EnrollmentResult":
        """Crea resultado de matrícula nueva."""
        return cls(
            success=True,
            action="created",
            enrollment=enrollment,
            message=f"Usuario matriculado exitosamente en {enrollment.course_name}"
        )
    
    @classmethod
    def updated(cls, enrollment: EnrollmentData) -> "EnrollmentResult":
        """Crea resultado de matrícula actualizada."""
        return cls(
            success=True,
            action="updated",
            enrollment=enrollment,
            message=f"Matrícula reactivada en {enrollment.course_name}"
        )
    
    @classmethod
    def already_active(cls, enrollment: EnrollmentData) -> "EnrollmentResult":
        """Crea resultado cuando ya está matriculado y activo."""
        return cls(
            success=True,
            action="already_active",
            enrollment=enrollment,
            message=f"Usuario ya está activo en {enrollment.course_name}"
        )
    
    @classmethod
    def failed(cls, error: str) -> "EnrollmentResult":
        """Crea resultado de error."""
        return cls(
            success=False,
            action="error",
            error=error,
            message=f"Error en matrícula: {error}"
        )