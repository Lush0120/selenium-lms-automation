"""
components/auth.py
Componente de autenticación para Moodle.

Este componente maneja todo lo relacionado con el inicio de sesión:
- Login con credenciales
- Verificación de sesión activa
- Logout
- Manejo de errores de autenticación

Uso:
    from core.browser import BrowserManager
    from components.auth import AuthComponent
    
    with BrowserManager() as browser:
        auth = AuthComponent(browser)
        auth.login("usuario", "contraseña")
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from typing import Optional, Tuple

from core.browser import BrowserManager
from core.config import settings
from core.logger import get_logger
from core.exceptions import LoginError, SessionExpiredError

logger = get_logger(__name__)


class AuthComponent:
    """
    Componente para manejar autenticación en Moodle.
    
    Este componente encapsula toda la lógica de login/logout,
    manteniendo el código limpio y reutilizable.
    
    Attributes:
        browser: Instancia de BrowserManager para interactuar con la página
        _is_logged_in: Estado interno de la sesión
    """
    
    def __init__(self, browser: BrowserManager):
        """
        Inicializa el componente de autenticación.
        
        Args:
            browser: Instancia de BrowserManager (debe estar iniciado)
        """
        self._browser = browser
        self._is_logged_in = False
        self._current_user: Optional[str] = None
        
        logger.debug("AuthComponent inicializado")
    
    def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        navigate_to_login: bool = True
    ) -> bool:
        """
        Inicia sesión en Moodle.
        
        Args:
            username: Nombre de usuario (si None, usa settings)
            password: Contraseña (si None, usa settings)
            navigate_to_login: Si True, navega a la página de login primero
            
        Returns:
            True si el login fue exitoso
            
        Raises:
            LoginError: Si las credenciales son incorrectas o hay otro error
        """
        # Usar credenciales de settings si no se proporcionan
        username = username or settings.moodle_username
        password = password or settings.moodle_password
        
        if not username or not password:
            raise LoginError(
                reason="Credenciales no proporcionadas",
                details="Debe proporcionar usuario y contraseña, o configurarlos en .env"
            )
        
        logger.info(f"Iniciando sesión para usuario: {username}")
        
        try:
            # Paso 1: Navegar a la página de login
            if navigate_to_login:
                self._browser.navigate_to(settings.login_url)
                logger.debug("Navegación a página de login completada")
            
            # Paso 2: Manejar banner de cookies si aparece
            self._browser.accept_cookies_if_present()
            
            # Paso 3: Ingresar credenciales
            logger.debug("Ingresando credenciales...")
            self._browser.type_text(
                By.ID,
                settings.selectors.username,
                username
            )
            self._browser.type_text(
                By.ID,
                settings.selectors.password,
                password
            )
            
            # Paso 4: Click en botón de login
            logger.debug("Haciendo click en botón de acceso...")
            self._browser.click(By.ID, settings.selectors.login_button)
            
            # Paso 5: Verificar resultado del login
            if self._verify_login_success():
                self._is_logged_in = True
                self._current_user = username
                logger.info(f"Login exitoso para: {username}")
                return True
            else:
                # Verificar si hay mensaje de error
                error_msg = self._get_login_error_message()
                raise LoginError(
                    reason="Credenciales incorrectas",
                    details=error_msg
                )
                
        except LoginError:
            # Re-lanzar errores de login
            raise
        except Exception as e:
            logger.error(f"Error inesperado durante login: {e}", exc_info=True)
            self._browser.take_screenshot("login_error")
            raise LoginError(
                reason="Error inesperado",
                details=str(e)
            )
    
    def logout(self) -> bool:
        """
        Cierra la sesión actual.
        
        Returns:
            True si el logout fue exitoso
        """
        if not self._is_logged_in:
            logger.warning("No hay sesión activa para cerrar")
            return False
        
        logger.info(f"Cerrando sesión de: {self._current_user}")
        
        try:
            # Moodle usa un enlace de logout con token
            # Navegamos al menú de usuario y buscamos el enlace de salir
            logout_url = f"{settings.moodle_base_url}/login/logout.php"
            self._browser.navigate_to(logout_url)
            
            # Confirmar logout si Moodle lo pide
            try:
                continue_button = self._browser.find_element(
                    By.CSS_SELECTOR,
                    "button[type='submit']",
                    timeout=3,
                    raise_exception=False
                )
                if continue_button:
                    continue_button.click()
            except Exception:
                pass  # No siempre pide confirmación
            
            self._is_logged_in = False
            self._current_user = None
            logger.info("Sesión cerrada correctamente")
            return True
            
        except Exception as e:
            logger.error(f"Error al cerrar sesión: {e}")
            return False
    
    def is_logged_in(self) -> bool:
        """
        Verifica si hay una sesión activa.
        
        Hace una verificación real navegando a una página protegida.
        
        Returns:
            True si hay sesión activa válida
        """
        # Si sabemos que no estamos logueados, retornar False
        if not self._is_logged_in:
            return False
        
        # Verificación real: intentar acceder a página protegida
        try:
            current_url = self._browser.current_url
            self._browser.navigate_to(settings.user_admin_url)
            
            # Si nos redirige a login, la sesión expiró
            if "/login/" in self._browser.current_url:
                logger.warning("La sesión ha expirado")
                self._is_logged_in = False
                self._current_user = None
                return False
            
            # Volver a la URL original
            self._browser.navigate_to(current_url)
            return True
            
        except Exception as e:
            logger.error(f"Error al verificar sesión: {e}")
            return False
    
    def ensure_logged_in(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> bool:
        """
        Asegura que haya una sesión activa, haciendo login si es necesario.
        
        Útil al inicio de operaciones que requieren autenticación.
        
        Args:
            username: Usuario (opcional, usa settings si no se proporciona)
            password: Contraseña (opcional, usa settings si no se proporciona)
            
        Returns:
            True si hay sesión activa (existente o nueva)
            
        Raises:
            LoginError: Si no se puede establecer sesión
        """
        if self.is_logged_in():
            logger.debug("Sesión activa verificada")
            return True
        
        logger.info("No hay sesión activa, iniciando login...")
        return self.login(username, password)
    
    @property
    def current_user(self) -> Optional[str]:
        """Retorna el usuario actualmente logueado."""
        return self._current_user
    
    # ==================== Métodos Privados ====================
    
    def _verify_login_success(self) -> bool:
        """
        Verifica si el login fue exitoso.
        
        Moodle redirige al dashboard o página principal después de login exitoso.
        Si hay error, permanece en la página de login mostrando mensaje.
        
        Returns:
            True si el login fue exitoso
        """
        logger.debug("Verificando resultado del login...")
        
        try:
            # Esperar un momento para que la página se actualice
            WebDriverWait(self._browser.driver, 5).until(
                lambda d: "/login/" not in d.current_url or 
                          self._has_login_error()
            )
            
            current_url = self._browser.current_url
            
            # Si ya no estamos en login, fue exitoso
            if "/login/" not in current_url:
                logger.debug(f"Redirigido a: {current_url}")
                return True
            
            # Si seguimos en login, verificar si hay error
            if self._has_login_error():
                return False
            
            # Caso raro: seguimos en login sin error visible
            logger.warning("Estado de login indeterminado")
            return False
            
        except TimeoutException:
            # Timeout esperando cambio - verificar URL actual
            return "/login/" not in self._browser.current_url
    
    def _has_login_error(self) -> bool:
        """Verifica si hay un mensaje de error en la página de login."""
        # Moodle muestra errores en un div con clase 'alert' o 'loginerrors'
        error_selectors = [
            "div.alert-danger",
            "div.loginerrors",
            "#loginerrormessage",
            "div.alert.alert-danger"
        ]
        
        for selector in error_selectors:
            try:
                element = self._browser.find_element(
                    By.CSS_SELECTOR,
                    selector,
                    timeout=1,
                    raise_exception=False
                )
                if element and element.is_displayed():
                    return True
            except Exception:
                continue
        
        return False
    
    def _get_login_error_message(self) -> Optional[str]:
        """Obtiene el mensaje de error de login si existe."""
        error_selectors = [
            "div.alert-danger",
            "div.loginerrors",
            "#loginerrormessage"
        ]
        
        for selector in error_selectors:
            try:
                element = self._browser.find_element(
                    By.CSS_SELECTOR,
                    selector,
                    timeout=1,
                    raise_exception=False
                )
                if element and element.is_displayed():
                    return element.text.strip()
            except Exception:
                continue
        
        return None