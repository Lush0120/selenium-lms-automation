"""
core/browser.py
Gestión centralizada del navegador Selenium.

OPTIMIZADO v3:
- Métodos wait_for_element y navigate_and_wait
- page_load_strategy = "eager"
- close_cookie_banner rápido
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    WebDriverException
)

from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple, Union, Callable

from core.config import settings
from core.logger import get_logger
from core.exceptions import (
    BrowserInitError,
    BrowserNavigationError,
    ElementNotFoundError,
    ElementInteractionError
)

logger = get_logger(__name__)

SCREENSHOTS_DIR = Path("screenshots")
SCREENSHOTS_DIR.mkdir(exist_ok=True)

DEFAULT_ELEMENT_TIMEOUT = 10


class BrowserManager:
    """Gestor del navegador Chrome con Selenium."""
    
    def __init__(self, headless: Optional[bool] = None):
        self._driver: Optional[WebDriver] = None
        self._wait: Optional[WebDriverWait] = None
        self._headless = headless if headless is not None else settings.browser.headless
        logger.debug(f"BrowserManager inicializado (headless={self._headless})")
    
    # ==================== Context Manager ====================
    
    def __enter__(self) -> "BrowserManager":
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            logger.error(f"Excepción detectada: {exc_type.__name__}: {exc_val}")
            self.take_screenshot("error_on_exit")
        self.quit()
        return False
    
    # ==================== Ciclo de Vida ====================
    
    def start(self) -> None:
        if self._driver is not None:
            logger.warning("El navegador ya está iniciado")
            return
        
        logger.info("Iniciando navegador Chrome...")
        
        try:
            options = self._build_chrome_options()
            service = ChromeService()
            
            self._driver = webdriver.Chrome(service=service, options=options)
            self._driver.set_page_load_timeout(settings.browser.page_load_timeout)
            self._driver.implicitly_wait(settings.browser.implicit_wait)
            
            if not self._headless:
                width, height = settings.browser.window_size
                self._driver.set_window_size(width, height)
                self._driver.maximize_window()
            
            self._wait = WebDriverWait(self._driver, settings.browser.implicit_wait)
            logger.info("Navegador iniciado correctamente")
            
        except WebDriverException as e:
            logger.critical(f"No se pudo iniciar el navegador: {e}")
            raise BrowserInitError(details=str(e))
    
    def quit(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
                logger.info("Navegador cerrado correctamente")
            except Exception as e:
                logger.warning(f"Error al cerrar navegador: {e}")
            finally:
                self._driver = None
                self._wait = None
    
    def restart(self) -> None:
        logger.info("Reiniciando navegador...")
        self.quit()
        self.start()
    
    # ==================== Propiedades ====================
    
    @property
    def driver(self) -> WebDriver:
        if self._driver is None:
            raise BrowserInitError(details="El navegador no ha sido iniciado")
        return self._driver
    
    @property
    def wait(self) -> WebDriverWait:
        if self._wait is None:
            raise BrowserInitError(details="El navegador no ha sido iniciado")
        return self._wait
    
    @property
    def current_url(self) -> str:
        return self.driver.current_url
    
    @property
    def timeout(self) -> int:
        return settings.browser.implicit_wait
    
    # ==================== Navegación ====================
    
    def navigate_to(self, url: str) -> None:
        logger.info(f"Navegando a: {url}")
        try:
            self.driver.get(url)
            logger.debug(f"Página cargada: {self.current_url}")
        except TimeoutException:
            logger.error(f"Timeout al cargar: {url}")
            raise BrowserNavigationError(url, details="Timeout de carga excedido")
        except WebDriverException as e:
            logger.error(f"Error de navegación: {e}")
            raise BrowserNavigationError(url, details=str(e))
    
    # ==================== MÉTODOS DE ESPERA OPTIMIZADOS ====================
    
    def wait_for_element(
        self,
        by: By,
        value: str,
        timeout: int = DEFAULT_ELEMENT_TIMEOUT,
        condition: str = "presence"
    ) -> Optional[WebElement]:
        """Espera a que un elemento específico esté disponible."""
        wait = WebDriverWait(self.driver, timeout)
        
        conditions_map = {
            "presence": EC.presence_of_element_located,
            "clickable": EC.element_to_be_clickable,
            "visible": EC.visibility_of_element_located
        }
        
        condition_func = conditions_map.get(condition, EC.presence_of_element_located)
        
        try:
            element = wait.until(condition_func((by, value)))
            logger.debug(f"Elemento encontrado: {by}='{value}'")
            return element
        except TimeoutException:
            logger.warning(f"Timeout esperando elemento: {by}='{value}' ({timeout}s)")
            return None
    
    def wait_for_any_element(
        self,
        selectors: List[Tuple[By, str]],
        timeout: int = DEFAULT_ELEMENT_TIMEOUT
    ) -> Optional[WebElement]:
        """Espera a que CUALQUIERA de los elementos esté presente."""
        wait = WebDriverWait(self.driver, timeout)
        
        def any_element_present(driver):
            for by, value in selectors:
                try:
                    elements = driver.find_elements(by, value)
                    if elements and elements[0].is_displayed():
                        return elements[0]
                except (StaleElementReferenceException, NoSuchElementException):
                    continue
            return False
        
        try:
            element = wait.until(any_element_present)
            logger.debug(f"Elemento encontrado (uno de {len(selectors)} posibles)")
            return element
        except TimeoutException:
            logger.warning(f"Timeout: ninguno de los {len(selectors)} elementos apareció")
            return None
    
    def navigate_and_wait(
        self,
        url: str,
        wait_for: Optional[Tuple[By, str]] = None,
        timeout: int = DEFAULT_ELEMENT_TIMEOUT,
        condition: str = "presence"
    ) -> Optional[WebElement]:
        """Navega a una URL y espera un elemento específico."""
        logger.info(f"Navegando a: {url}")
        
        try:
            self.driver.get(url)
        except TimeoutException:
            logger.warning(f"Timeout parcial al cargar: {url} (continuando...)")
        except WebDriverException as e:
            logger.error(f"Error de navegación: {e}")
            raise BrowserNavigationError(url, details=str(e))
        
        if wait_for:
            by, value = wait_for
            return self.wait_for_element(by, value, timeout, condition)
        else:
            return self.wait_for_element(By.CSS_SELECTOR, "body", timeout=5)
    
    def wait_for_url_change(self, original_url: str, timeout: int = DEFAULT_ELEMENT_TIMEOUT) -> bool:
        """Espera a que la URL cambie."""
        wait = WebDriverWait(self.driver, timeout)
        try:
            wait.until(EC.url_changes(original_url))
            logger.debug(f"URL cambió de {original_url} a {self.current_url}")
            return True
        except TimeoutException:
            logger.warning(f"Timeout esperando cambio de URL")
            return False
    
    def wait_for_element_text(self, by: By, value: str, text: str, timeout: int = DEFAULT_ELEMENT_TIMEOUT) -> bool:
        """Espera a que un elemento contenga un texto específico."""
        wait = WebDriverWait(self.driver, timeout)
        try:
            wait.until(EC.text_to_be_present_in_element((by, value), text))
            logger.debug(f"Texto '{text}' encontrado en {by}='{value}'")
            return True
        except TimeoutException:
            logger.warning(f"Timeout esperando texto '{text}' en {by}='{value}'")
            return False
    
    # ==================== Búsqueda de Elementos ====================
    
    def find_element(
        self,
        by: By,
        value: str,
        timeout: Optional[int] = None,
        raise_exception: bool = True
    ) -> Optional[WebElement]:
        timeout = timeout or settings.browser.implicit_wait
        logger.debug(f"Buscando elemento: {by}='{value}' (timeout={timeout}s)")
        
        try:
            wait = WebDriverWait(self.driver, timeout)
            element = wait.until(EC.presence_of_element_located((by, value)))
            logger.debug(f"Elemento encontrado: {by}='{value}'")
            return element
        except TimeoutException:
            logger.warning(f"Elemento no encontrado: {by}='{value}'")
            if raise_exception:
                raise ElementNotFoundError(selector=value, by=str(by), details=f"Timeout de {timeout}s excedido")
            return None
    
    def find_elements(self, by: By, value: str, timeout: Optional[int] = None) -> List[WebElement]:
        timeout = timeout or 2
        try:
            wait = WebDriverWait(self.driver, timeout)
            wait.until(EC.presence_of_element_located((by, value)))
        except TimeoutException:
            pass
        return self.driver.find_elements(by, value)
    
    # ==================== Interacción ====================
    
    def click(self, by: By, value: str, timeout: Optional[int] = None, scroll_into_view: bool = True) -> None:
        logger.debug(f"Click en: {by}='{value}'")
        element = self.find_element(by, value, timeout)
        
        try:
            if scroll_into_view:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            try:
                element.click()
            except ElementClickInterceptedException:
                logger.debug("Click interceptado, usando JavaScript...")
                self.driver.execute_script("arguments[0].click();", element)
            logger.debug("Click exitoso")
        except Exception as e:
            raise ElementInteractionError(selector=value, action="click", details=str(e))
    
    def type_text(self, by: By, value: str, text: str, clear_first: bool = True, timeout: Optional[int] = None, use_js: bool = False) -> None:
        logger.debug(f"Escribiendo en: {by}='{value}'")
        element = self.find_element(by, value, timeout)
        
        try:
            if clear_first:
                element.clear()
            if use_js:
                self.driver.execute_script("arguments[0].value = arguments[1];", element, text)
                self.driver.execute_script("""
                    var el = arguments[0];
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                """, element)
            else:
                element.send_keys(text)
            logger.debug(f"Texto escrito correctamente")
        except Exception as e:
            raise ElementInteractionError(selector=value, action="escribir texto", details=str(e))
    
    def select_option(self, by: By, value: str, option_value: str, select_by: str = "value", timeout: Optional[int] = None) -> None:
        from selenium.webdriver.support.ui import Select
        logger.debug(f"Seleccionando opción '{option_value}' en: {by}='{value}'")
        element = self.find_element(by, value, timeout)
        select = Select(element)
        
        if select_by == "value":
            select.select_by_value(option_value)
        elif select_by == "text":
            select.select_by_visible_text(option_value)
        elif select_by == "index":
            select.select_by_index(int(option_value))
        else:
            raise ValueError(f"select_by inválido: {select_by}")
        logger.debug(f"Opción seleccionada correctamente")
    
    # ==================== Utilidades ====================
    
    def take_screenshot(self, name: str = "screenshot") -> Optional[Path]:
        if self._driver is None:
            logger.warning("No se puede capturar screenshot: navegador no iniciado")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = SCREENSHOTS_DIR / f"{name}_{timestamp}.png"
        
        try:
            self._driver.save_screenshot(str(filename))
            logger.info(f"Screenshot guardada: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Error al guardar screenshot: {e}")
            return None
    
    def execute_script(self, script: str, *args) -> any:
        return self.driver.execute_script(script, *args)
    
    def close_cookie_banner(self) -> bool:
        """Cierra el banner de cookies si está presente (rápido)."""
        cookie_selectors = [
            (By.ID, "acceptCookies"),
            (By.CSS_SELECTOR, "button[onclick*='acceptCookies']"),
            (By.CSS_SELECTOR, "#cookie-banner button"),
            (By.CSS_SELECTOR, ".cookie-banner button"),
        ]
        
        for by, value in cookie_selectors:
            try:
                btn = self.driver.find_element(by, value)
                if btn.is_displayed():
                    btn.click()
                    logger.info("Banner de cookies cerrado")
                    return True
            except (NoSuchElementException, ElementClickInterceptedException):
                continue
        
        try:
            self.driver.execute_script("""
                var banner = document.getElementById('cookie-banner');
                if (banner) banner.style.display = 'none';
            """)
        except:
            pass
        
        return False
    
    def accept_cookies_if_present(self) -> bool:
        """Alias de close_cookie_banner()."""
        return self.close_cookie_banner()
    
    def wait_for_page_load(self, timeout: Optional[int] = None) -> None:
        """Espera a que la página termine de cargar (LENTO - usar solo si es necesario)."""
        timeout = timeout or settings.browser.page_load_timeout
        logger.debug("Esperando carga completa de página...")
        try:
            wait = WebDriverWait(self.driver, timeout)
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            logger.debug("Página cargada completamente")
        except TimeoutException:
            logger.warning("Timeout esperando carga de página")
    
    def element_exists(self, value: str, by: By = By.ID, timeout: int = 2) -> bool:
        element = self.find_element(by, value, timeout=timeout, raise_exception=False)
        return element is not None
    
    def get_text(self, value: str, by: By = By.ID, timeout: Optional[int] = None) -> str:
        element = self.find_element(by, value, timeout)
        return element.text
    
    def get_attribute(self, by: By, value: str, attribute: str, timeout: Optional[int] = None) -> Optional[str]:
        element = self.find_element(by, value, timeout, raise_exception=False)
        if element:
            return element.get_attribute(attribute)
        return None
    
    # ==================== Gestión de Ventanas ====================
    
    def open_new_window(self, url: Optional[str] = None) -> str:
        self.driver.execute_script("window.open('');")
        new_window = self.driver.window_handles[-1]
        self.driver.switch_to.window(new_window)
        if url:
            self.navigate_to(url)
        logger.debug(f"Nueva ventana abierta: {new_window}")
        return new_window
    
    def switch_to_window(self, window_handle: str) -> None:
        self.driver.switch_to.window(window_handle)
        logger.debug(f"Cambiado a ventana: {window_handle}")
    
    def close_current_window(self) -> None:
        self.driver.close()
        if self.driver.window_handles:
            self.driver.switch_to.window(self.driver.window_handles[0])
            logger.debug("Ventana cerrada, volviendo a la principal")
    
    @property
    def current_window(self) -> str:
        return self.driver.current_window_handle
    
    # ==================== Métodos Privados ====================
    
    def _build_chrome_options(self) -> Options:
        options = Options()
        
        if self._headless:
            options.add_argument("--headless=new")
            logger.debug("Modo headless activado")
        
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--remote-allow-origins=*")
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        
        # OPTIMIZACIÓN: No esperar carga completa
        options.page_load_strategy = "eager"
        
        if self._headless:
            width, height = settings.browser.window_size
            options.add_argument(f"--window-size={width},{height}")
        
        return options