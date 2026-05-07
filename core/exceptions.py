"""
core/exceptions.py
Excepciones personalizadas para el proyecto.

Jerarquía de excepciones:
    MoodleAutomationError (base)
    ├── BrowserError
    │   ├── BrowserInitError
    │   └── BrowserNavigationError
    ├── AuthenticationError
    │   ├── LoginError
    │   └── SessionExpiredError
    ├── UserError
    │   ├── UserNotFoundError
    │   ├── UserCreationError
    │   ├── UserUpdateError
    │   ├── UserAlreadyExistsError
    │   └── UsernameNotAvailableError
    ├── CourseError
    │   ├── CourseNotFoundError
    │   └── EnrollmentError
    ├── ElementError
    │   ├── ElementNotFoundError
    │   └── ElementInteractionError
    ├── ExcelError (NUEVO v5)
    │   ├── ExcelFileNotFoundError
    │   ├── ExcelSheetNotFoundError
    │   ├── ExcelReadError
    │   └── ExcelWriteError
    ├── GeneralistaError (NUEVO v5)
    │   ├── GeneralistaNotFoundError
    │   ├── GeneralistaAlreadyExistsError
    │   └── InvalidGeneralistaDataError
    └── SolicitudError (NUEVO v5)
        ├── SolicitudInvalidaError
        └── SolicitudYaProcesadaError
"""


class MoodleAutomationError(Exception):
    """
    Excepción base para todo el proyecto.
    
    Todas las excepciones personalizadas heredan de esta,
    permitiendo capturar cualquier error del proyecto con:
    
        try:
            ...
        except MoodleAutomationError as e:
            # Maneja cualquier error del proyecto
    """
    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Detalles: {self.details}"
        return self.message


# ============== Errores de Navegador ==============

class BrowserError(MoodleAutomationError):
    """Errores relacionados con el navegador."""
    pass


class BrowserInitError(BrowserError):
    """Error al inicializar el navegador."""
    def __init__(self, details: str = None):
        super().__init__(
            message="No se pudo inicializar el navegador",
            details=details
        )


class BrowserNavigationError(BrowserError):
    """Error al navegar a una URL."""
    def __init__(self, url: str, details: str = None):
        super().__init__(
            message=f"No se pudo navegar a: {url}",
            details=details
        )


# ============== Errores de Autenticación ==============

class AuthenticationError(MoodleAutomationError):
    """Errores relacionados con autenticación."""
    pass


class LoginError(AuthenticationError):
    """Error durante el proceso de login."""
    def __init__(self, reason: str = None, details: str = None):
        message = "Error al iniciar sesión"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message=message, details=details)


class SessionExpiredError(AuthenticationError):
    """La sesión ha expirado."""
    def __init__(self):
        super().__init__(
            message="La sesión ha expirado. Es necesario volver a iniciar sesión."
        )


# ============== Errores de Usuario ==============

class UserError(MoodleAutomationError):
    """Errores relacionados con gestión de usuarios."""
    pass


class UserNotFoundError(UserError):
    """Usuario no encontrado."""
    def __init__(self, identifier: str, details: str = None):
        super().__init__(
            message=f"Usuario no encontrado: {identifier}",
            details=details
        )


class UserCreationError(UserError):
    """Error al crear usuario."""
    def __init__(self, reason: str = None, details: str = None):
        message = "Error al crear usuario"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message=message, details=details)


class UserUpdateError(UserError):
    """Error al actualizar usuario."""
    def __init__(self, username: str, reason: str = None, details: str = None):
        message = f"Error al actualizar usuario '{username}'"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message=message, details=details)


class UserAlreadyExistsError(UserError):
    """El usuario ya existe en el sistema."""
    def __init__(self, identifier: str, details: str = None):
        super().__init__(
            message=f"El usuario ya existe: {identifier}",
            details=details
        )


class UsernameNotAvailableError(UserError):
    """El username no está disponible."""
    def __init__(self, username: str, details: str = None):
        super().__init__(
            message=f"El username '{username}' no está disponible",
            details=details
        )


# ============== Errores de Cursos ==============

class CourseError(MoodleAutomationError):
    """Errores relacionados con cursos."""
    pass


class CourseNotFoundError(CourseError):
    """Curso no encontrado."""
    def __init__(self, course_name: str, details: str = None):
        super().__init__(
            message=f"Curso no encontrado: {course_name}",
            details=details
        )


class EnrollmentError(CourseError):
    """Error al matricular usuario en curso."""
    def __init__(self, username: str, course_name: str, reason: str = None, details: str = None):
        message = f"Error al matricular '{username}' en '{course_name}'"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message=message, details=details)


# ============== Errores de Elementos DOM ==============

class ElementError(MoodleAutomationError):
    """Errores relacionados con elementos del DOM."""
    pass


class ElementNotFoundError(ElementError):
    """Elemento no encontrado en la página."""
    def __init__(self, selector: str, selector_type: str = "ID", timeout: int = None, details: str = None):
        message = f"Elemento no encontrado: {selector_type}='{selector}'"
        if timeout:
            message = f"{message} (timeout: {timeout}s)"
        super().__init__(message=message, details=details)


class NavigationError(MoodleAutomationError):
    """Error al navegar a una página."""
    pass


class ElementInteractionError(ElementError):
    """Error al interactuar con un elemento."""
    def __init__(self, selector: str, action: str, details: str = None):
        super().__init__(
            message=f"Error al {action} elemento '{selector}'",
            details=details
        )


# ============== Errores de Excel (NUEVO v5) ==============

class ExcelError(MoodleAutomationError):
    """Errores relacionados con archivos Excel."""
    pass


class ExcelFileNotFoundError(ExcelError):
    """Archivo Excel no encontrado."""
    def __init__(self, filepath: str, details: str = None):
        super().__init__(
            message=f"Archivo Excel no encontrado: {filepath}",
            details=details
        )


class ExcelSheetNotFoundError(ExcelError):
    """Hoja de Excel no encontrada."""
    def __init__(self, sheet_name: str, filepath: str = None, details: str = None):
        message = f"Hoja no encontrada: '{sheet_name}'"
        if filepath:
            message = f"{message} en {filepath}"
        super().__init__(message=message, details=details)


class ExcelReadError(ExcelError):
    """Error al leer archivo Excel."""
    def __init__(self, filepath: str, reason: str = None, details: str = None):
        message = f"Error al leer archivo Excel: {filepath}"
        if reason:
            message = f"{message} - {reason}"
        super().__init__(message=message, details=details)


class ExcelWriteError(ExcelError):
    """Error al escribir archivo Excel."""
    def __init__(self, filepath: str, reason: str = None, details: str = None):
        message = f"Error al escribir archivo Excel: {filepath}"
        if reason:
            message = f"{message} - {reason}"
        super().__init__(message=message, details=details)


# ============== Errores de Generalistas (NUEVO v5) ==============

class GeneralistaError(MoodleAutomationError):
    """Errores relacionados con generalistas."""
    pass


class GeneralistaNotFoundError(GeneralistaError):
    """Generalista no encontrado."""
    def __init__(self, identifier: str, details: str = None):
        super().__init__(
            message=f"Generalista no encontrado: {identifier}",
            details=details
        )


class GeneralistaAlreadyExistsError(GeneralistaError):
    """El generalista ya existe."""
    def __init__(self, identifier: str, details: str = None):
        super().__init__(
            message=f"El generalista ya existe: {identifier}",
            details=details
        )


class InvalidGeneralistaDataError(GeneralistaError):
    """Datos de generalista inválidos."""
    def __init__(self, reason: str, details: str = None):
        super().__init__(
            message=f"Datos de generalista inválidos: {reason}",
            details=details
        )


# ============== Errores de Solicitudes (NUEVO v5) ==============

class SolicitudError(MoodleAutomationError):
    """Errores relacionados con solicitudes del Excel."""
    pass


class SolicitudInvalidaError(SolicitudError):
    """Solicitud con datos inválidos."""
    def __init__(self, codigo: str, errores: list, details: str = None):
        errores_str = ", ".join(errores) if errores else "desconocido"
        super().__init__(
            message=f"Solicitud inválida '{codigo}': {errores_str}",
            details=details
        )


class SolicitudYaProcesadaError(SolicitudError):
    """Solicitud ya fue procesada."""
    def __init__(self, codigo: str, details: str = None):
        super().__init__(
            message=f"La solicitud '{codigo}' ya fue procesada",
            details=details
        )