"""
components/user.py
Componente de gestión de usuarios para Moodle.

Maneja búsqueda, verificación de username y creación de usuarios.
Este componente interactúa con Moodle para:
1. Buscar usuarios existentes por email o username
2. Verificar disponibilidad de usernames
3. Crear nuevos usuarios con username único automático
4. Actualizar contraseña de usuarios existentes

VERSIÓN 2.1:
- CORREGIDO: Limpiar filtros de búsqueda anteriores antes de cada búsqueda
- Selector verificado: #id_removeall

Uso:
    from core.browser import BrowserManager
    from components.auth import AuthComponent
    from components.user import UserComponent
    from models.user import UserData
    
    with BrowserManager() as browser:
        auth = AuthComponent(browser)
        auth.login()
        
        user_comp = UserComponent(browser)
        
        # Verificar si existe
        result = user_comp.search_by_email("test@example.com")
        
        # Crear usuario
        user_data = UserData(
            primer_nombre="Juan",
            primer_apellido="García",
            correo="juan@example.com",
            telefono="3001234567",
            ciudad="Medellín"
        )
        user_comp.create_user(user_data)
        
        # Actualizar contraseña de usuario existente
        user_data = user_comp.update_user_password("test@example.com")
"""

import re
import time
import secrets
import string
from typing import Optional
from dataclasses import dataclass

from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from core.browser import BrowserManager
from core.config import settings
from core.logger import get_logger
from core.exceptions import (
    UserError,
    UserNotFoundError,
    UserAlreadyExistsError,
    UserCreationError,
    UsernameNotAvailableError,
    ElementNotFoundError,
)
from models.user import UserData, UserSearchResult

logger = get_logger(__name__)


@dataclass
class UserUpdateResult:
    """
    Resultado de actualización de usuario.
    
    Contiene todos los datos relevantes del usuario después de actualizar.
    """
    success: bool
    user_id: str
    username: str
    password: str
    firstname: str
    lastname: str
    email: str
    phone: str = ""
    city: str = ""
    message: str = ""
    
    @property
    def full_name(self) -> str:
        """Retorna el nombre completo."""
        return f"{self.firstname} {self.lastname}"


class UserComponent:
    """
    Componente para manejar operaciones de usuario en Moodle.
    
    Funcionalidades:
    - Buscar usuarios por email, username o nombre
    - Verificar disponibilidad de username
    - Crear nuevos usuarios
    - Generar username único automáticamente
    - Actualizar contraseña de usuarios existentes
    """
    
    # Operadores de búsqueda de Moodle
    SEARCH_OP_CONTAINS = "0"
    SEARCH_OP_NOT_CONTAINS = "1"
    SEARCH_OP_EQUALS = "2"
    SEARCH_OP_STARTS_WITH = "3"
    SEARCH_OP_ENDS_WITH = "4"
    SEARCH_OP_IS_EMPTY = "5"
    
    # Selectores para edición de usuario
    EDIT_SELECTORS = {
        "edit_icon": "a[href*='user/editadvanced.php'] i[title='Editar']",
        "edit_link": "a[href*='user/editadvanced.php']",
        "password_edit_link": "a[data-passwordunmask='edit']",
        "password_field": "#id_newpassword",
        "username_field": "#id_username",
        "firstname_field": "#id_firstname",
        "lastname_field": "#id_lastname",
        "email_field": "#id_email",
        "phone_field": "#id_phone1",
        "city_field": "#id_city",
        "country_field": "#id_country",
        "update_button": "#id_submitbutton",
        # Sección opcional (donde está el teléfono)
        "optional_section": "#id_moodle_optional",
        "optional_section_link": "#collapseElement-4",
    }
    
    def __init__(self, browser: BrowserManager):
        """
        Inicializa el componente de usuario.
        
        Args:
            browser: Instancia de BrowserManager
        """
        self.browser = browser
    
    # ==================== BÚSQUEDA ====================
    
    def _navigate_to_user_admin(self) -> None:
        """Navega a la página de administración de usuarios"""
        current_url = self.browser.current_url
        if settings.moodle_user_admin_path not in current_url:
            logger.debug("Navegando a administración de usuarios...")
            self.browser.navigate_to(settings.user_admin_url)
            self.browser.wait_for_page_load()
    
    def _expand_search_filters(self) -> None:
        """Expande los filtros de búsqueda avanzados si están colapsados"""
        try:
            # Buscar el enlace "Mostrar más..."
            show_more = self.browser.find_element(
                By.CSS_SELECTOR,
                settings.selectors.search_show_more,
                timeout=3
            )
            
            # Verificar si está colapsado (aria-expanded="false")
            aria_expanded = show_more.get_attribute("aria-expanded")
            if aria_expanded == "false":
                logger.debug("Expandiendo filtros de búsqueda...")
                show_more.click()
                time.sleep(0.5)  # Esperar animación
                
        except ElementNotFoundError:
            logger.debug("Filtros de búsqueda ya expandidos o no disponibles")
    
    def _clear_search_filters(self) -> None:
        """
        Limpia los filtros de búsqueda existentes.
        
        CORREGIDO: Usar selector por ID verificado del HTML real.
        El botón tiene: id="id_removeall", name="removeall"
        """
        try:
            # Buscar el botón por ID (más confiable)
            clear_btn = None
            
            try:
                clear_btn = self.browser.driver.find_element(By.ID, "id_removeall")
            except NoSuchElementException:
                pass
            
            # Backup: buscar por name
            if not clear_btn:
                try:
                    clear_btn = self.browser.driver.find_element(
                        By.CSS_SELECTOR, 
                        "input[name='removeall']"
                    )
                except NoSuchElementException:
                    pass
            
            if clear_btn and clear_btn.is_displayed():
                logger.info("Limpiando filtros de búsqueda anteriores...")
                self.browser.driver.execute_script("arguments[0].click();", clear_btn)
                time.sleep(1)
                self.browser.wait_for_page_load()
                logger.info("Filtros limpiados correctamente")
            
        except Exception as e:
            logger.debug(f"No hay filtros que limpiar: {e}")
    
    def _perform_search(
        self,
        field_id: str,
        operator_id: str,
        value: str,
        operator: str = None
    ) -> None:
        """
        Ejecuta una búsqueda con el campo y valor especificados.
        
        Args:
            field_id: ID del campo de búsqueda
            operator_id: ID del selector de operador
            value: Valor a buscar
            operator: Operador de búsqueda (default: EQUALS)
        """
        operator = operator or self.SEARCH_OP_EQUALS
        
        self._navigate_to_user_admin()
        
        # IMPORTANTE: Limpiar filtros anteriores antes de buscar
        self._clear_search_filters()
        
        self._expand_search_filters()
        
        # Seleccionar operador
        self.browser.select_option(By.ID, operator_id, operator, select_by="value")
        
        # Ingresar valor
        self.browser.type_text(By.ID, field_id, value)
        
        # Hacer clic en buscar
        self.browser.click(By.ID, settings.selectors.search_submit)
        self.browser.wait_for_page_load()
    
    def _parse_search_results(self) -> list[UserSearchResult]:
        """
        Parsea los resultados de búsqueda de la tabla de usuarios.
        
        Returns:
            Lista de UserSearchResult
        """
        results = []
        
        try:
            # Verificar si la tabla existe
            table = self.browser.driver.find_elements(By.ID, "users")
            logger.debug(f"Tablas encontradas con ID 'users': {len(table)}")
            
            if not table:
                logger.debug("No se encontró la tabla de usuarios")
                return results
            
            # Buscar filas en tbody
            rows = self.browser.driver.find_elements(By.CSS_SELECTOR, "#users tbody tr")
            logger.debug(f"Filas encontradas: {len(rows)}")
            
            if not rows:
                logger.debug("No se encontraron filas en la tabla")
                return results
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    logger.debug(f"Celdas en fila: {len(cells)}")
                    
                    if len(cells) < 2:
                        continue
                    
                    try:
                        profile_link = row.find_element(By.CSS_SELECTOR, "a[href*='user/view.php']")
                        href = profile_link.get_attribute("href")
                        full_name = profile_link.text.strip()
                        logger.debug(f"Enlace encontrado: {full_name} -> {href}")
                    except Exception as e:
                        logger.debug(f"No se encontró enlace de perfil: {e}")
                        continue
                    
                    user_id_match = re.search(r"id=(\d+)", href)
                    user_id = user_id_match.group(1) if user_id_match else None
                    
                    email = cells[1].text.strip() if len(cells) > 1 else ""
                    logger.debug(f"Email extraído: {email}")
                    
                    result = UserSearchResult(
                        found=True,
                        user_id=user_id,
                        full_name=full_name,
                        email=email,
                        profile_url=href
                    )
                    results.append(result)
                    
                except Exception as e:
                    logger.debug(f"Error parseando fila: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"Error buscando tabla: {e}")
        
        logger.debug(f"Total resultados: {len(results)}")
        return results
    
    def search_by_email(self, email: str) -> UserSearchResult:
        """
        Busca un usuario por email.
        
        Args:
            email: Email a buscar
        
        Returns:
            UserSearchResult con los datos del usuario o not_found()
        """
        logger.info(f"Buscando usuario por email: {email}")
        
        self._perform_search(
            settings.selectors.search_email,
            settings.selectors.search_email_op,
            email,
            self.SEARCH_OP_EQUALS
        )
        
        results = self._parse_search_results()
        
        if results:
            logger.info(f"Usuario encontrado: {results[0].full_name}")
            return results[0]
        
        logger.info(f"No se encontró usuario con email: {email}")
        return UserSearchResult.not_found()
    
    def search_by_username(self, username: str) -> UserSearchResult:
        """
        Busca un usuario por username.
        
        Args:
            username: Username a buscar
        
        Returns:
            UserSearchResult
        """
        logger.info(f"Buscando usuario por username: {username}")
        
        self._perform_search(
            settings.selectors.search_username,
            settings.selectors.search_username_op,
            username,
            self.SEARCH_OP_EQUALS
        )
        
        results = self._parse_search_results()
        
        if results:
            # Asignar el username que buscamos
            results[0].username = username
            logger.info(f"Usuario encontrado: {results[0].full_name}")
            return results[0]
        
        logger.info(f"No se encontró usuario con username: {username}")
        return UserSearchResult.not_found()
    
    def username_exists(self, username: str) -> bool:
        """
        Verifica si un username ya existe.
        
        Args:
            username: Username a verificar
        
        Returns:
            True si existe, False si está disponible
        """
        result = self.search_by_username(username)
        return result.found
    
    def email_exists(self, email: str) -> bool:
        """
        Verifica si un email ya está registrado.
        
        Args:
            email: Email a verificar
        
        Returns:
            True si existe, False si está disponible
        """
        result = self.search_by_email(email)
        return result.found
    
    # ==================== GENERACIÓN DE USERNAME ====================
    
    def find_available_username(self, user_data: UserData, max_attempts: int = 15) -> str:
        """
        Encuentra un username disponible para el usuario.
        
        Prueba las diferentes estrategias de username hasta encontrar uno libre.
        
        Args:
            user_data: Datos del usuario
            max_attempts: Número máximo de intentos
        
        Returns:
            Username disponible
        
        Raises:
            UsernameNotAvailableError: Si no se encuentra username disponible
        """
        logger.info(f"Buscando username disponible para: {user_data.nombre_completo}")
        
        usernames = user_data.obtener_todos_los_usernames(max_attempts)
        
        for i, username in enumerate(usernames):
            logger.debug(f"Intento {i+1}: Verificando '{username}'...")
            
            if not self.username_exists(username):
                logger.info(f"Username disponible encontrado: {username}")
                return username
            
            logger.debug(f"Username '{username}' ya existe")
        
        # Si llegamos aquí, ningún username está disponible
        raise UsernameNotAvailableError(
            f"No se encontró username disponible después de {max_attempts} intentos",
            {"user": user_data.nombre_completo, "attempts": max_attempts}
        )
    
    # ==================== CREACIÓN ====================
    
    def _navigate_to_create_user(self) -> None:
        """Navega a la página de creación de usuario"""
        logger.debug("Navegando a página de creación de usuario...")
        self.browser.navigate_to(settings.user_create_url)
        self.browser.wait_for_page_load()
    
    def _expand_optional_section(self) -> None:
        """Expande la sección 'Opcional' del formulario (donde está el teléfono)"""
        try:
            # Verificar si la sección está colapsada
            section = self.browser.find_element(
                By.ID,
                settings.selectors.section_optional,
                timeout=3
            )
            
            if "collapsed" in section.get_attribute("class"):
                logger.debug("Expandiendo sección Opcional...")
                expand_link = self.browser.find_element(
                    By.ID,
                    settings.selectors.section_optional_expand
                )
                expand_link.click()
                time.sleep(0.5)
                
        except ElementNotFoundError:
            logger.debug("Sección opcional no encontrada o ya expandida")
    
    def _fill_user_form(self, user_data: UserData) -> None:
        """
        Llena el formulario de creación de usuario.
        
        Args:
            user_data: Datos del usuario a crear
        """
        logger.debug("Llenando formulario de usuario...")
        
        # Campos principales
        self.browser.type_text(By.ID, settings.selectors.create_username, user_data.username)
        
        # Contraseña - El campo tiene un comportamiento especial
        # Primero hacer clic para habilitar edición
        try:
            password_edit = self.browser.find_element(
                By.CSS_SELECTOR,
                "a[data-passwordunmask='edit']",
                timeout=3
            )
            password_edit.click()
            time.sleep(0.3)
        except ElementNotFoundError:
            pass
        
        # Ahora escribir la contraseña
        self.browser.type_text(By.ID, settings.selectors.create_password, user_data.password)
        
        # Nombre y apellido
        self.browser.type_text(By.ID, settings.selectors.create_firstname, user_data.nombres)
        self.browser.type_text(By.ID, settings.selectors.create_lastname, user_data.apellidos)
        
        # Email
        self.browser.type_text(By.ID, settings.selectors.create_email, user_data.correo)
        
        # Ciudad
        self.browser.type_text(By.ID, settings.selectors.create_city, user_data.ciudad)
        
        # País - Colombia por defecto
        self.browser.select_option(
            By.ID,
            settings.selectors.create_country,
            "CO",
            select_by="value"
        )
        
        # Expandir sección opcional para el teléfono
        self._expand_optional_section()
        
        # Teléfono
        self.browser.type_text(By.ID, settings.selectors.create_phone, user_data.telefono)
    
    def _submit_user_form(self) -> bool:
        """
        Envía el formulario de creación de usuario.
        
        Returns:
            True si la creación fue exitosa
        
        Raises:
            UserCreationError: Si hay error en la creación
        """
        logger.debug("Enviando formulario...")
        
        self.browser.click(By.ID, settings.selectors.create_submit)
        self.browser.wait_for_page_load()
        
        # Verificar si hay errores en el formulario
        error_elements = self.browser.find_elements(
            By.CSS_SELECTOR,
            ".invalid-feedback:not(:empty), .alert-danger",
            timeout=2
        )
        
        if error_elements:
            errors = []
            for elem in error_elements:
                text = elem.text.strip()
                if text:
                    errors.append(text)
            
            if errors:
                error_msg = "; ".join(errors)
                logger.error(f"Errores en formulario: {error_msg}")
                raise UserCreationError(
                    "Error al crear usuario",
                    {"form_errors": errors}
                )
        
        # Verificar que no seguimos en la página de creación
        current_url = self.browser.current_url
        if "editadvanced.php" in current_url and "id=-1" in current_url:
            # Seguimos en la página de creación, algo falló
            self.browser.take_screenshot("user_creation_error")
            raise UserCreationError("El formulario no se envió correctamente")
        
        logger.info("Usuario creado exitosamente")
        return True
    
    def create_user(
        self,
        user_data: UserData,
        auto_username: bool = True,
        verify_email: bool = True
    ) -> UserData:
        """
        Crea un nuevo usuario en Moodle.
        
        Args:
            user_data: Datos del usuario a crear
            auto_username: Si buscar username disponible automáticamente
            verify_email: Si verificar que el email no existe
        
        Returns:
            UserData actualizado con el username final
        
        Raises:
            UserAlreadyExistsError: Si el email ya existe
            UsernameNotAvailableError: Si no se encuentra username disponible
            UserCreationError: Si hay error en la creación
        """
        logger.info(f"Iniciando creación de usuario: {user_data.nombre_completo}")
        
        # Verificar que el email no existe
        if verify_email:
            if self.email_exists(user_data.correo):
                raise UserAlreadyExistsError(
                    f"Ya existe un usuario con el email: {user_data.correo}",
                    {"email": user_data.correo}
                )
        
        # Obtener lista de usernames candidatos
        usernames_candidatos = user_data.obtener_todos_los_usernames(15)
        
        # Intentar crear con cada username hasta que uno funcione
        for i, username in enumerate(usernames_candidatos):
            logger.info(f"Intento {i+1}: Probando username '{username}'")
            user_data.actualizar_username(username)
            
            # Navegar al formulario de creación
            self._navigate_to_create_user()
            
            # Llenar formulario
            self._fill_user_form(user_data)
            
            # Tomar screenshot antes de enviar (para debug)
            if i == 0:  # Solo en el primer intento
                self.browser.take_screenshot("user_form_filled")
            
            # Intentar enviar formulario
            try:
                self._submit_user_form()
                # Si llegamos aquí, el usuario se creó exitosamente
                logger.info(f"Usuario creado: {user_data.username} ({user_data.correo})")
                return user_data
                
            except UserCreationError as e:
                # Verificar si el error es por username duplicado
                error_msg = str(e).lower()
                if "nombre de usuario ya existe" in error_msg or "username" in error_msg:
                    logger.warning(f"Username '{username}' ya existe, probando siguiente...")
                    continue
                else:
                    # Otro tipo de error, no reintentar
                    raise
        
        # Si llegamos aquí, ningún username funcionó
        raise UsernameNotAvailableError(
            f"No se pudo crear usuario después de {len(usernames_candidatos)} intentos",
            {"user": user_data.nombre_completo, "attempts": len(usernames_candidatos)}
        )
    
    def get_user_by_email_or_create(
        self,
        user_data: UserData
    ) -> tuple[UserSearchResult | None, UserData | None, bool]:
        """
        Obtiene un usuario existente o lo crea si no existe.
        
        Args:
            user_data: Datos del usuario
        
        Returns:
            Tupla de (usuario_existente, usuario_creado, fue_creado)
            - Si el usuario existía: (UserSearchResult, None, False)
            - Si se creó: (None, UserData, True)
        """
        logger.info(f"Verificando usuario: {user_data.correo}")
        
        # Buscar por email
        existing = self.search_by_email(user_data.correo)
        
        if existing.found:
            logger.info(f"Usuario ya existe: {existing.full_name}")
            return (existing, None, False)
        
        # Crear nuevo usuario
        created = self.create_user(user_data)
        return (None, created, True)
    
    # ==================== GENERACIÓN DE CONTRASEÑA ====================
    
    @staticmethod
    def _generate_password(length: int = 10) -> str:
        """
        Genera una contraseña segura aleatoria.
        
        La contraseña incluye:
        - Letras mayúsculas y minúsculas
        - Números
        - Al menos un carácter especial
        
        Args:
            length: Longitud de la contraseña (mínimo 8)
            
        Returns:
            Contraseña generada
        """
        if length < 8:
            length = 8
        
        # Caracteres disponibles
        letters = string.ascii_letters
        digits = string.digits
        special = "!@#$%&*"
        
        # Asegurar al menos uno de cada tipo
        password_chars = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(digits),
            secrets.choice(special),
        ]
        
        # Completar el resto
        all_chars = letters + digits + special
        password_chars += [secrets.choice(all_chars) for _ in range(length - 4)]
        
        # Mezclar
        secrets.SystemRandom().shuffle(password_chars)
        
        return ''.join(password_chars)
    
    # ==================== ACTUALIZACIÓN DE USUARIO ====================
    
    def _click_edit_user(self) -> bool:
        """
        Hace clic en el icono de editar usuario desde la tabla de resultados.
        
        Returns:
            True si se pudo hacer clic, False si no se encontró
        """
        try:
            # Buscar el enlace de edición en la fila del usuario
            edit_link = self.browser.driver.find_element(
                By.CSS_SELECTOR,
                self.EDIT_SELECTORS["edit_link"]
            )
            
            # Usar JavaScript para hacer clic (más confiable)
            self.browser.driver.execute_script("arguments[0].click();", edit_link)
            time.sleep(1)
            self.browser.wait_for_page_load()
            return True
            
        except NoSuchElementException:
            logger.error("No se encontró el enlace de edición del usuario")
            return False
    
    def _expand_optional_section_edit(self) -> None:
        """Expande la sección opcional en el formulario de edición."""
        try:
            # Buscar sección opcional
            section = self.browser.driver.find_element(
                By.CSS_SELECTOR,
                self.EDIT_SELECTORS["optional_section"]
            )
            
            # Verificar si está colapsada
            if "collapsed" in section.get_attribute("class"):
                # Buscar el enlace para expandir
                try:
                    expand_link = self.browser.driver.find_element(
                        By.CSS_SELECTOR,
                        self.EDIT_SELECTORS["optional_section_link"]
                    )
                    expand_link.click()
                    time.sleep(0.5)
                    logger.debug("Sección opcional expandida")
                except:
                    pass
        except:
            pass
    
    def _extract_user_data_from_form(self) -> dict:
        """
        Extrae los datos del usuario desde el formulario de edición.
        
        Incluye todos los campos relevantes: username, nombre, apellido,
        email, teléfono, ciudad.
        
        Returns:
            Diccionario con los datos del usuario
        """
        data = {}
        
        try:
            # Username
            username_field = self.browser.driver.find_element(
                By.CSS_SELECTOR, self.EDIT_SELECTORS["username_field"]
            )
            data["username"] = username_field.get_attribute("value")
            
            # Nombre
            firstname_field = self.browser.driver.find_element(
                By.CSS_SELECTOR, self.EDIT_SELECTORS["firstname_field"]
            )
            data["firstname"] = firstname_field.get_attribute("value")
            
            # Apellido
            lastname_field = self.browser.driver.find_element(
                By.CSS_SELECTOR, self.EDIT_SELECTORS["lastname_field"]
            )
            data["lastname"] = lastname_field.get_attribute("value")
            
            # Email
            email_field = self.browser.driver.find_element(
                By.CSS_SELECTOR, self.EDIT_SELECTORS["email_field"]
            )
            data["email"] = email_field.get_attribute("value")
            
            # Expandir sección opcional para acceder al teléfono
            self._expand_optional_section_edit()
            
            # Teléfono
            try:
                phone_field = self.browser.driver.find_element(
                    By.CSS_SELECTOR, self.EDIT_SELECTORS["phone_field"]
                )
                data["phone"] = phone_field.get_attribute("value") or ""
            except NoSuchElementException:
                data["phone"] = ""
            
            # Ciudad
            try:
                city_field = self.browser.driver.find_element(
                    By.CSS_SELECTOR, self.EDIT_SELECTORS["city_field"]
                )
                data["city"] = city_field.get_attribute("value") or ""
            except NoSuchElementException:
                data["city"] = ""
            
            # Extraer user_id de la URL
            current_url = self.browser.current_url
            user_id_match = re.search(r"id=(\d+)", current_url)
            data["user_id"] = user_id_match.group(1) if user_id_match else ""
            
            logger.debug(f"Datos extraídos del formulario: {data}")
            
        except NoSuchElementException as e:
            logger.error(f"Error extrayendo datos del formulario: {e}")
        
        return data
    
    def _set_new_password(self, new_password: str) -> bool:
        """
        Establece una nueva contraseña en el formulario de edición.
        
        Args:
            new_password: Nueva contraseña a establecer
            
        Returns:
            True si se pudo establecer la contraseña
        """
        try:
            # Primero hacer clic en el enlace para habilitar edición de contraseña
            try:
                password_edit = self.browser.driver.find_element(
                    By.CSS_SELECTOR, self.EDIT_SELECTORS["password_edit_link"]
                )
                self.browser.driver.execute_script("arguments[0].click();", password_edit)
                time.sleep(0.5)
            except NoSuchElementException:
                logger.debug("Enlace de edición de contraseña no encontrado, intentando campo directo")
            
            # Escribir la nueva contraseña
            password_field = self.browser.driver.find_element(
                By.CSS_SELECTOR, self.EDIT_SELECTORS["password_field"]
            )
            
            # Limpiar y escribir
            password_field.clear()
            password_field.send_keys(new_password)
            
            logger.debug("Nueva contraseña establecida")
            return True
            
        except NoSuchElementException as e:
            logger.error(f"Error estableciendo contraseña: {e}")
            return False
    
    def _submit_update_form(self) -> bool:
        """
        Envía el formulario de actualización de usuario.
        
        Returns:
            True si se envió correctamente
        """
        try:
            # Buscar el botón de actualizar
            update_btn = self.browser.driver.find_element(
                By.CSS_SELECTOR, self.EDIT_SELECTORS["update_button"]
            )
            
            # Scroll al botón para asegurarnos que sea visible
            self.browser.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                update_btn
            )
            time.sleep(0.5)
            
            # Intentar click normal primero
            try:
                update_btn.click()
            except Exception:
                # Si falla, usar JavaScript
                self.browser.driver.execute_script("arguments[0].click();", update_btn)
            
            # Esperar a que se procese
            time.sleep(2)
            
            # Esperar a que la página cargue (con timeout más largo)
            try:
                self.browser.wait_for_page_load()
            except Exception:
                # Si hay timeout, verificar si de todas formas funcionó
                pass
            
            # Verificar si seguimos en la página de edición (indica error)
            current_url = self.browser.current_url
            if "editadvanced.php" in current_url:
                # Verificar si hay errores en el formulario
                error_elements = self.browser.driver.find_elements(
                    By.CSS_SELECTOR,
                    ".invalid-feedback:not(:empty), .alert-danger"
                )
                
                for elem in error_elements:
                    text = elem.text.strip()
                    if text:
                        logger.error(f"Error en formulario: {text}")
                        return False
            
            logger.debug("Formulario enviado correctamente")
            return True
            
        except NoSuchElementException as e:
            logger.error(f"Error enviando formulario - botón no encontrado: {e}")
            return False
        except Exception as e:
            logger.error(f"Error enviando formulario: {e}")
            # Puede que el formulario se haya enviado pero hubo timeout
            # Verificar si la URL cambió
            time.sleep(1)
            current_url = self.browser.current_url
            if "editadvanced.php" not in current_url:
                logger.info("El formulario parece haberse enviado a pesar del error")
                return True
            return False
    
    def update_user_password(
        self,
        email: str,
        new_password: Optional[str] = None,
        search_result: Optional[UserSearchResult] = None
    ) -> Optional[UserUpdateResult]:
        """
        Actualiza la contraseña de un usuario existente.
        
        Flujo:
        1. Si no se pasa search_result, buscar usuario por email
        2. Hacer clic en icono de editar
        3. Extraer datos actuales del usuario (username, nombre, apellido, teléfono, ciudad)
        4. Establecer nueva contraseña
        5. Guardar cambios
        6. Retornar todos los datos del usuario
        
        Args:
            email: Email del usuario a actualizar
            new_password: Nueva contraseña (si None, genera una automáticamente)
            search_result: Resultado de búsqueda previo (opcional, evita búsqueda duplicada)
            
        Returns:
            UserUpdateResult con los datos del usuario y la nueva contraseña,
            o None si el usuario no existe o hubo error
        """
        logger.info(f"Actualizando contraseña para: {email}")
        
        # Solo buscar si no se pasó un resultado previo
        if search_result is None:
            search_result = self.search_by_email(email)
        
        if not search_result.found:
            logger.warning(f"Usuario no encontrado: {email}")
            return None
        
        # Hacer clic en editar
        if not self._click_edit_user():
            logger.error("No se pudo acceder al formulario de edición")
            return None
        
        # Esperar a que cargue el formulario
        time.sleep(1)
        
        # Extraer datos actuales del formulario
        user_data = self._extract_user_data_from_form()
        
        if not user_data.get("username"):
            logger.error("No se pudieron extraer los datos del usuario")
            return None
        
        # Generar contraseña si no se proporcionó
        if new_password is None:
            new_password = self._generate_password()
            logger.debug("Contraseña generada automáticamente")
        
        # Establecer nueva contraseña
        if not self._set_new_password(new_password):
            logger.error("No se pudo establecer la nueva contraseña")
            return None
        
        # Guardar cambios
        if not self._submit_update_form():
            logger.error("No se pudo guardar los cambios")
            return None
        
        logger.info(f"Contraseña actualizada para: {user_data.get('username')}")
        
        return UserUpdateResult(
            success=True,
            user_id=user_data.get("user_id", ""),
            username=user_data.get("username", ""),
            password=new_password,
            firstname=user_data.get("firstname", ""),
            lastname=user_data.get("lastname", ""),
            email=email,
            phone=user_data.get("phone", ""),
            city=user_data.get("city", ""),
            message="Contraseña actualizada exitosamente"
        )
    
    def find_user(self, email: str) -> Optional[UserSearchResult]:
        """
        Busca un usuario por email y retorna el resultado.
        
        Método de conveniencia que retorna None si no se encuentra.
        
        Args:
            email: Email a buscar
            
        Returns:
            UserSearchResult si se encuentra, None si no
        """
        result = self.search_by_email(email)
        return result if result.found else None