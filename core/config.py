"""
core/config.py
Configuración centralizada del proyecto usando Pydantic Settings.

¿Por qué Pydantic Settings?
1. Permite cargar configuración desde variables de entorno o archivo .env
2. Valida los tipos automáticamente
3. Centraliza todas las constantes en un solo lugar
4. Facilita cambiar entre entornos (desarrollo/producción)
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel


class MoodleSelectors(BaseModel):
    """Selectores CSS/IDs para elementos de Moodle"""
    # Login
    username: str = "username"
    password: str = "password"
    login_button: str = "loginbtn"
    
    # Cookies
    accept_cookies: str = "acceptCookies"
    cookie_banner: str = "cookie-banner"
    
    # Búsqueda de usuarios (admin/user.php)
    # Nota: Primero hay que hacer clic en "Mostrar más..." para ver campos avanzados
    search_show_more: str = "a.moreless-toggler"  # CSS selector para expandir
    search_realname: str = "id_realname"  # Nombre completo
    search_realname_op: str = "id_realname_op"  # Operador (contiene, es igual a, etc.)
    search_username: str = "id_username"  # Username (búsqueda)
    search_username_op: str = "id_username_op"
    search_email: str = "id_email"  # Email (búsqueda)
    search_email_op: str = "id_email_op"
    search_firstname: str = "id_firstname"  # Nombre (búsqueda)
    search_firstname_op: str = "id_firstname_op"
    search_lastname: str = "id_lastname"  # Apellido (búsqueda)
    search_lastname_op: str = "id_lastname_op"
    search_submit: str = "id_addfilter"  # Botón "Añadir filtro"
    
    # Creación/Edición de usuarios (user/editadvanced.php)
    create_username: str = "id_username"  # Nombre de usuario
    create_password: str = "id_newpassword"  # Nueva contraseña
    create_firstname: str = "id_firstname"  # Nombre
    create_lastname: str = "id_lastname"  # Apellido(s)
    create_email: str = "id_email"  # Dirección de correo
    create_city: str = "id_city"  # Ciudad/Pueblo
    create_country: str = "id_country"  # País (select)
    create_phone: str = "id_phone1"  # Teléfono (en sección Opcional)
    create_submit: str = "id_submitbutton"  # Botón "Crear usuario"
    create_cancel: str = "id_cancel"  # Botón "Cancelar"
    
    # Secciones colapsables del formulario de creación
    section_optional: str = "id_moodle_optional"  # Sección "Opcional" (contiene teléfono)
    section_optional_expand: str = "collapseElement-4"  # Link para expandir sección Opcional
    
    # Tabla de resultados de búsqueda
    users_table: str = "users"  # ID de la tabla de usuarios
    no_results_message: str = ".alert-info"  # Mensaje cuando no hay resultados


class BrowserSettings(BaseModel):
    """Configuración del navegador"""
    headless: bool = True
    window_size: tuple[int, int] = (1920, 1080)
    implicit_wait: int = 10
    page_load_timeout: int = 30
    script_timeout: int = 30


class Settings(BaseSettings):
    """Configuración principal de la aplicación"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # URLs de Moodle
    moodle_base_url: str = "https://campusvirtual.izyacademy.com"
    moodle_login_path: str = "/login/index.php"
    moodle_course_management_path: str = "/course/management.php"
    moodle_user_admin_path: str = "/admin/user.php"
    moodle_user_create_path: str = "/user/editadvanced.php?id=-1"
    
    # Credenciales (desde .env)
    moodle_username: str = Field(default="", description="Usuario administrador de Moodle")
    moodle_password: str = Field(default="", description="Contraseña del administrador")
    
    # Configuraciones anidadas
    selectors: MoodleSelectors = MoodleSelectors()
    browser: BrowserSettings = BrowserSettings()
    
    # Rutas de archivos
    logs_dir: str = "logs"
    screenshots_dir: str = "screenshots"
    templates_dir: str = "templates"
    
    @property
    def login_url(self) -> str:
        return f"{self.moodle_base_url}{self.moodle_login_path}"
    
    @property
    def course_management_url(self) -> str:
        return f"{self.moodle_base_url}{self.moodle_course_management_path}"
    
    @property
    def user_admin_url(self) -> str:
        return f"{self.moodle_base_url}{self.moodle_user_admin_path}"
    
    @property
    def user_create_url(self) -> str:
        return f"{self.moodle_base_url}{self.moodle_user_create_path}"


# Singleton de configuración
settings = Settings()