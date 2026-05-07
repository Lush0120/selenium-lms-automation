"""
components/enrollment.py
Componente para gestionar matrículas en Moodle.

OPTIMIZADO v3.1:
- CORREGIDO: Agregar ENTER después de escribir en filtro para confirmar texto
- Selector correcto para campo de texto dinámico
- Sin llamada a close_cookie_banner (ya se cerró en login)
- Polling rápido

VERSIÓN 3.4:
- NUEVO: Cerrar modal SMOWL de monitorización que bloquea clics
"""

import re
import time
from typing import Optional
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from core.browser import BrowserManager
from core.config import settings
from core.logger import get_logger
from models.enrollment import (
    EnrollmentData,
    EnrollmentResult,
    EnrollmentConfig,
    EnrollmentStatus,
    EnrollmentDuration,
)

logger = get_logger(__name__)

ELEMENT_TIMEOUT = 10


class EnrollmentComponent:
    """Componente para gestionar matrículas de usuarios en cursos."""
    
    URL_PARTICIPANTS = "{base}/user/index.php?id={course_id}"
    
    SELECTORS = {
        "participants_table": "table#participants",
        "participant_row": "table#participants tbody tr",
        "enroll_button": "input[value='Matricular usuarios']",
        "user_search_input": "input[placeholder='Buscar']",
        "user_suggestion": "ul.form-autocomplete-suggestions li",
        "show_more_link": "a.moreless-toggler",
        "duration_select": "#id_duration",
        "submit_enroll_btn": "button[data-action='save']",
        "edit_enrollment_icon": "i[aria-label='Editar matrícula']",
        "edit_status_select": "#id_status",
        "edit_save_btn": "button[data-action='save']",
        "close_modal_btn": "button.close[data-action='hide']",
        # Modal SMOWL
        "smowl_modal_overlay": "#popup-smowl",
        "smowl_modal_btn": "#btn-smowl-entendido",
    }
    
    def __init__(self, browser: BrowserManager):
        self.browser = browser
        self.base_url = settings.moodle_base_url
    
    def _close_smowl_modal(self) -> bool:
        """
        Cierra el modal de SMOWL si está presente.
        
        Este modal aparece en pruebas con monitorización activa
        y bloquea cualquier interacción con la página.
        
        Returns:
            True si se cerró el modal, False si no estaba presente
        """
        try:
            # Buscar el botón "Entendido" del modal SMOWL
            smowl_btn = self.browser.driver.find_element(
                By.ID, "btn-smowl-entendido"
            )
            
            if smowl_btn.is_displayed():
                logger.info("Modal SMOWL detectado, cerrando...")
                self.browser.driver.execute_script("arguments[0].click();", smowl_btn)
                time.sleep(0.5)
                logger.info("Modal SMOWL cerrado")
                return True
                
        except NoSuchElementException:
            pass
        except Exception as e:
            logger.debug(f"Error cerrando modal SMOWL: {e}")
        
        return False
    
    def enroll_user(
        self,
        course_id: str,
        user_email: str,
        config: Optional[EnrollmentConfig] = None
    ) -> EnrollmentResult:
        """Matricula un usuario en un curso."""
        config = config or EnrollmentConfig()
        
        logger.info(f"Iniciando matrícula: {user_email} en curso {course_id}")
        
        try:
            # Navegar a participantes
            self._navigate_to_participants(course_id)
            
            # NUEVO: Cerrar modal SMOWL si aparece
            self._close_smowl_modal()
            
            # Aplicar filtro por palabra clave
            logger.info(f"Aplicando filtro por: {user_email}")
            filter_applied = self._apply_keyword_filter(user_email)
            
            if not filter_applied:
                logger.warning("No se pudo aplicar filtro, buscando directamente...")
            
            # Verificar si está matriculado
            is_enrolled, enrollment_data = self._check_user_enrolled(user_email)
            
            if is_enrolled:
                logger.info(f"Usuario ya matriculado, estado: {enrollment_data.status.value}")
                logger.info("Actualizando matrícula (estado y fechas)...")
                return self._reactivate_enrollment(user_email, course_id, config)
            else:
                return self._create_enrollment(course_id, user_email, config)
                
        except Exception as e:
            logger.error(f"Error en matrícula: {e}")
            self._close_modal()
            return EnrollmentResult.failed(str(e))
    
    def _navigate_to_participants(self, course_id: str) -> None:
        """Navega a la página de participantes del curso."""
        url = self.URL_PARTICIPANTS.format(base=self.base_url, course_id=course_id)
        logger.debug(f"Navegando a participantes: {url}")
        
        self.browser.driver.get(url)
        
        # NUEVO: Cerrar modal SMOWL si aparece al cargar la página
        time.sleep(0.5)
        self._close_smowl_modal()
        
        # Polling rápido: esperar tabla o filtro
        start_time = time.time()
        while time.time() - start_time < 20:
            try:
                # NUEVO: Verificar y cerrar modal SMOWL en cada iteración
                self._close_smowl_modal()
                
                # Verificar tabla
                table = self.browser.driver.find_elements(By.CSS_SELECTOR, "table#participants")
                if table and table[0].is_displayed():
                    logger.debug(f"Tabla encontrada en {time.time() - start_time:.1f}s")
                    return
                
                # Verificar filtro
                filter_el = self.browser.driver.find_elements(By.CSS_SELECTOR, "select[data-filterfield='type']")
                if filter_el:
                    logger.debug(f"Filtro encontrado en {time.time() - start_time:.1f}s")
                    return
            except:
                pass
            time.sleep(0.3)
        
        logger.warning("Timeout esperando página de participantes")
    
    def _apply_keyword_filter(self, keyword: str) -> bool:
        """
        Aplica el filtro de palabra clave para buscar usuarios.
        
        CORREGIDO v3.1: Agregar ENTER después de escribir para confirmar el texto
        CORREGIDO v3.2: Esperar a que el contenedor del filtro cargue antes de seleccionar
        CORREGIDO v3.3: Manejar cuando la ventana no tiene foco (re-seleccionar si es necesario)
        """
        try:
            # 0. NUEVO: Forzar foco en la ventana del navegador
            try:
                self.browser.driver.switch_to.window(self.browser.driver.current_window_handle)
                # Ejecutar un scroll mínimo para "despertar" la página
                self.browser.driver.execute_script("window.scrollBy(0, 1); window.scrollBy(0, -1);")
            except:
                pass
            
            # 1. Esperar a que el contenedor del filtro esté completamente cargado
            filter_select = None
            for attempt in range(20):
                try:
                    selects = self.browser.driver.find_elements(
                        By.CSS_SELECTOR,
                        "select[data-filterfield='type']"
                    )
                    for sel in selects:
                        if sel.is_displayed() and sel.is_enabled():
                            filter_select = sel
                            break
                    if filter_select:
                        break
                except:
                    pass
                time.sleep(0.3)
            
            if not filter_select:
                logger.warning("No se encontró el selector de filtro")
                return False
            
            self.browser.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", 
                filter_select
            )
            time.sleep(0.3)
            
            # 2. Función auxiliar para intentar seleccionar y obtener el input
            def seleccionar_y_esperar_input(max_intentos=3):
                """Intenta seleccionar 'Palabra clave' y espera el input."""
                for intento in range(max_intentos):
                    select = Select(filter_select)
                    
                    # Si no es el primer intento, primero volver a la opción por defecto
                    if intento > 0:
                        logger.debug(f"Reintento {intento + 1}: Re-seleccionando filtro...")
                        try:
                            # Volver a una opción diferente primero (simula lo que haces manual)
                            select.select_by_index(0)
                            time.sleep(0.5)
                        except:
                            pass
                    
                    select.select_by_value("keywords")
                    logger.debug("Seleccionado: Palabra clave")
                    
                    # Esperar campo de texto dinámico
                    text_input = None
                    for attempt in range(15):
                        try:
                            inputs = self.browser.driver.find_elements(
                                By.CSS_SELECTOR,
                                "input[id^='form_autocomplete_input'], input[placeholder='Escriba...']"
                            )
                            for inp in inputs:
                                if inp.is_displayed() and inp.is_enabled():
                                    try:
                                        inp.get_attribute("value")
                                        text_input = inp
                                        break
                                    except:
                                        continue
                            if text_input:
                                return text_input
                        except:
                            pass
                        time.sleep(0.3)
                    
                    # Si no encontramos el input, intentar de nuevo
                    if not text_input and intento < max_intentos - 1:
                        logger.warning("Input no apareció, reintentando selección...")
                
                return None
            
            # 3. Intentar obtener el input (con reintentos si es necesario)
            text_input = seleccionar_y_esperar_input(max_intentos=3)
            
            if not text_input:
                logger.warning("No se encontró campo de texto del filtro después de varios intentos")
                return False
            
            # 4. Hacer clic en el campo y escribir keyword
            self.browser.driver.execute_script("arguments[0].click();", text_input)
            time.sleep(0.3)
            text_input.clear()
            text_input.send_keys(keyword)
            
            # 5. Presionar ENTER para confirmar el texto
            text_input.send_keys(Keys.ENTER)
            time.sleep(0.5)
            
            # 6. Click en "Aplicar filtros"
            apply_btn = None
            for attempt in range(10):
                try:
                    btns = self.browser.driver.find_elements(
                        By.CSS_SELECTOR,
                        "button[data-filteraction='apply']"
                    )
                    for btn in btns:
                        if btn.is_displayed() and btn.is_enabled():
                            apply_btn = btn
                            break
                    if apply_btn:
                        break
                except:
                    pass
                time.sleep(0.2)
            
            if not apply_btn:
                logger.warning("No se encontró botón de aplicar filtro")
                return False
            
            self.browser.driver.execute_script("arguments[0].click();", apply_btn)
            
            # 7. Esperar a que se actualice la tabla
            time.sleep(1)
            logger.info("Filtro aplicado correctamente")
            return True
            
        except Exception as e:
            logger.error(f"Error aplicando filtro: {e}")
            return False
    
    def _check_user_enrolled(self, email: str) -> tuple[bool, Optional[EnrollmentData]]:
        """Verifica si un usuario está matriculado en el curso."""
        try:
            xpath = f"//table[@id='participants']//tbody/tr[.//td[contains(., '{email}')]]"
            
            try:
                user_row = WebDriverWait(self.browser.driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                logger.info(f"Usuario {email} encontrado en lista de participantes")
                enrollment_data = self._extract_enrollment_from_row(user_row, email)
                return True, enrollment_data
                
            except TimeoutException:
                rows = self.browser.driver.find_elements(By.CSS_SELECTOR, self.SELECTORS["participant_row"])
                for row in rows:
                    if email.lower() in row.text.lower():
                        logger.info(f"Usuario {email} encontrado (búsqueda por texto)")
                        enrollment_data = self._extract_enrollment_from_row(row, email)
                        return True, enrollment_data
                
                logger.debug(f"Usuario {email} no está matriculado")
                return False, None
                
        except Exception as e:
            logger.error(f"Error verificando matrícula: {e}")
            return False, None
    
    def _extract_enrollment_from_row(self, row, user_email: str) -> EnrollmentData:
        """Extrae datos de matrícula desde una fila de la tabla."""
        user_id = ""
        try:
            checkbox = row.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
            checkbox_name = checkbox.get_attribute("name") or ""
            user_id = checkbox_name.replace("user", "")
        except:
            try:
                link = row.find_element(By.CSS_SELECTOR, "a[href*='user/view.php']")
                href = link.get_attribute("href") or ""
                match = re.search(r'id=(\d+)', href)
                if match:
                    user_id = match.group(1)
            except:
                pass
        
        fullname = ""
        try:
            name_link = row.find_element(By.CSS_SELECTOR, "th a, td a[href*='user/view.php']")
            fullname = name_link.text.strip()
        except:
            pass
        
        status = EnrollmentStatus.NO_ACTIVO
        try:
            badge = row.find_element(By.CSS_SELECTOR, ".badge")
            status = EnrollmentStatus.from_text(badge.text)
        except:
            pass
        
        course_id = ""
        match = re.search(r'id=(\d+)', self.browser.current_url)
        if match:
            course_id = match.group(1)
        
        return EnrollmentData(
            user_id=user_id,
            user_fullname=fullname,
            user_email=user_email,
            course_id=course_id,
            course_name="",
            status=status
        )
    
    def _create_enrollment(self, course_id: str, user_email: str, config: EnrollmentConfig) -> EnrollmentResult:
        """Crea una nueva matrícula."""
        logger.info(f"Creando nueva matrícula para {user_email}")
        
        try:
            # NUEVO: Cerrar modal SMOWL si aparece
            self._close_smowl_modal()
            
            enroll_btn = self.browser.wait_for_element(
                By.CSS_SELECTOR, self.SELECTORS["enroll_button"],
                timeout=ELEMENT_TIMEOUT, condition="clickable"
            )
            
            if not enroll_btn:
                return EnrollmentResult.failed("No se encontró botón de matricular")
            
            self.browser.driver.execute_script("arguments[0].click();", enroll_btn)
            
            # NUEVO: Cerrar modal SMOWL si aparece después de abrir modal de matrícula
            time.sleep(0.3)
            self._close_smowl_modal()
            
            search_input = self.browser.wait_for_element(
                By.CSS_SELECTOR, self.SELECTORS["user_search_input"],
                timeout=ELEMENT_TIMEOUT
            )
            
            if not search_input:
                return EnrollmentResult.failed("No se abrió modal de matrícula")
            
            self._click_show_more()
            
            if not self._search_and_select_user(user_email):
                self._close_modal()
                return EnrollmentResult.failed(f"No se encontró usuario: {user_email}")
            
            self._select_duration(config.duration)
            
            # NUEVO: Cerrar modal SMOWL antes de hacer clic en guardar
            self._close_smowl_modal()
            
            save_btn = self.browser.wait_for_element(
                By.CSS_SELECTOR, self.SELECTORS["submit_enroll_btn"],
                timeout=ELEMENT_TIMEOUT, condition="clickable"
            )
            
            if save_btn:
                # Usar JavaScript para el clic (más confiable)
                self.browser.driver.execute_script("arguments[0].click();", save_btn)
            else:
                return EnrollmentResult.failed("No se encontró botón de guardar")
            
            time.sleep(1)
            
            # Verificar matrícula
            self._navigate_to_participants(course_id)
            self._apply_keyword_filter(user_email)
            
            is_enrolled, enrollment = self._check_user_enrolled(user_email)
            
            if is_enrolled and enrollment:
                return EnrollmentResult.created(enrollment)
            else:
                return EnrollmentResult.failed("Matrícula no verificada")
                
        except Exception as e:
            logger.error(f"Error creando matrícula: {e}")
            self._close_modal()
            return EnrollmentResult.failed(str(e))
    
    def _click_show_more(self) -> None:
        """Expande la sección 'Mostrar más' si existe."""
        try:
            link = self.browser.driver.find_element(By.CSS_SELECTOR, self.SELECTORS["show_more_link"])
            if link.is_displayed() and "Mostrar más" in link.text:
                link.click()
                time.sleep(0.3)
        except:
            pass
    
    def _search_and_select_user(self, user_email: str) -> bool:
        """Busca y selecciona un usuario en el autocomplete."""
        try:
            search_input = self.browser.driver.find_element(By.CSS_SELECTOR, self.SELECTORS["user_search_input"])
            search_input.clear()
            search_input.send_keys(user_email)
            
            suggestion = self.browser.wait_for_element(By.CSS_SELECTOR, self.SELECTORS["user_suggestion"], timeout=5)
            
            if suggestion:
                suggestions = self.browser.driver.find_elements(By.CSS_SELECTOR, self.SELECTORS["user_suggestion"])
                for sug in suggestions:
                    if sug.is_displayed() and user_email.lower() in sug.text.lower():
                        sug.click()
                        time.sleep(0.3)
                        return True
                
                for sug in suggestions:
                    if sug.is_displayed():
                        sug.click()
                        return True
            
            return False
        except Exception as e:
            logger.error(f"Error buscando usuario: {e}")
            return False
    
    def _select_duration(self, duration: EnrollmentDuration) -> None:
        """Selecciona la duración de la matrícula."""
        try:
            select_element = self.browser.driver.find_element(By.CSS_SELECTOR, self.SELECTORS["duration_select"])
            select = Select(select_element)
            select.select_by_value(str(duration.value))
        except:
            pass
    
    def _reactivate_enrollment(self, user_email: str, course_id: str, config: EnrollmentConfig) -> EnrollmentResult:
        """Reactiva una matrícula existente."""
        logger.info(f"Reactivando matrícula para {user_email}")
        
        try:
            # NUEVO: Cerrar modal SMOWL si aparece
            self._close_smowl_modal()
            
            xpath = f"//table[@id='participants']//tbody/tr[.//td[contains(., '{user_email}')]]"
            user_row = self.browser.wait_for_element(By.XPATH, xpath, timeout=ELEMENT_TIMEOUT)
            
            if not user_row:
                return EnrollmentResult.failed(f"No se encontró fila del usuario {user_email}")
            
            try:
                edit_icon = user_row.find_element(By.CSS_SELECTOR, self.SELECTORS["edit_enrollment_icon"])
                self.browser.driver.execute_script("arguments[0].click();", edit_icon)
            except:
                try:
                    edit_icon = user_row.find_element(By.XPATH, ".//a[@data-action='editenrolment']//i | .//i[@aria-label='Editar matrícula']")
                    self.browser.driver.execute_script("arguments[0].click();", edit_icon)
                except:
                    return EnrollmentResult.failed("No se encontró icono de editar matrícula")
            
            # NUEVO: Cerrar modal SMOWL si aparece después de abrir el modal de edición
            time.sleep(0.5)
            self._close_smowl_modal()
            
            status_select = self.browser.wait_for_element(By.CSS_SELECTOR, self.SELECTORS["edit_status_select"], timeout=ELEMENT_TIMEOUT)
            
            if not status_select:
                self._close_modal()
                return EnrollmentResult.failed("No se abrió modal de edición")
            
            select = Select(status_select)
            select.select_by_value("0")
            
            self._update_enrollment_dates(config.duration)
            
            # NUEVO: Cerrar modal SMOWL antes de hacer clic en guardar
            self._close_smowl_modal()
            
            save_btn = self.browser.wait_for_element(By.CSS_SELECTOR, self.SELECTORS["edit_save_btn"], timeout=ELEMENT_TIMEOUT, condition="clickable")
            
            if save_btn:
                # Usar JavaScript para el clic (más confiable)
                self.browser.driver.execute_script("arguments[0].click();", save_btn)
            else:
                self._close_modal()
                return EnrollmentResult.failed("No se encontró botón de guardar")
            
            time.sleep(0.5)
            
            # Verificar reactivación
            self._navigate_to_participants(course_id)
            
            # NUEVO: Cerrar modal SMOWL si aparece después de navegar
            self._close_smowl_modal()
            
            self._apply_keyword_filter(user_email)
            
            is_enrolled, enrollment = self._check_user_enrolled(user_email)
            
            if is_enrolled and enrollment:
                return EnrollmentResult.updated(enrollment)
            
            return EnrollmentResult.failed("No se pudo verificar reactivación")
            
        except Exception as e:
            logger.error(f"Error reactivando matrícula: {e}")
            self._close_modal()
            return EnrollmentResult.failed(str(e))
    
    def _update_enrollment_dates(self, duration: EnrollmentDuration) -> bool:
        """Actualiza las fechas de matrícula."""
        try:
            now = datetime.now()
            
            date_fields = {
                "id_timestart_day": str(now.day),
                "id_timestart_month": str(now.month),
                "id_timestart_year": str(now.year),
                "id_timestart_hour": str(now.hour),
                "id_timestart_minute": str(now.minute),
            }
            
            for field_id, value in date_fields.items():
                try:
                    select_el = self.browser.driver.find_element(By.ID, field_id)
                    if not select_el.get_attribute("disabled"):
                        select = Select(select_el)
                        select.select_by_value(value)
                except:
                    pass
            
            try:
                timeend_checkbox = self.browser.driver.find_element(By.ID, "id_timeend_enabled")
                if timeend_checkbox.is_selected():
                    self.browser.driver.execute_script("arguments[0].click();", timeend_checkbox)
                    time.sleep(0.2)
            except:
                pass
            
            try:
                duration_select = self.browser.driver.find_element(By.ID, "id_duration")
                if not duration_select.get_attribute("disabled"):
                    select = Select(duration_select)
                    select.select_by_value(str(duration.value))
            except:
                pass
            
            return True
        except Exception as e:
            logger.error(f"Error actualizando fechas: {e}")
            return False
    
    def _close_modal(self) -> None:
        """Cierra cualquier modal abierto."""
        try:
            close_buttons = self.browser.driver.find_elements(By.CSS_SELECTOR, self.SELECTORS["close_modal_btn"])
            for btn in close_buttons:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(0.2)
                    return
        except:
            pass
        
        try:
            self.browser.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except:
            pass
    
    def check_enrollment_status(self, course_id: str, user_email: str) -> Optional[EnrollmentData]:
        """Verifica el estado de matrícula de un usuario."""
        self._navigate_to_participants(course_id)
        self._apply_keyword_filter(user_email)
        is_enrolled, enrollment = self._check_user_enrolled(user_email)
        return enrollment if is_enrolled else None