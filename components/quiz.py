"""
components/quiz.py
Componente para gestionar quizzes y limpiar intentos en Moodle.

OPTIMIZADO v3:
- Selectores corregidos para botón eliminar y modal de confirmación
- Búsqueda rápida de intentos por email
- Sin esperas innecesarias
"""

import time
from typing import Optional, List
from dataclasses import dataclass

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from core.browser import BrowserManager
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

ELEMENT_TIMEOUT = 10


@dataclass
class DeleteAttemptResult:
    """Resultado de eliminar intentos."""
    success: bool
    quiz_id: str
    quiz_name: str
    attempts_deleted: int
    message: str
    error: Optional[str] = None


class QuizComponent:
    """Componente para gestionar quizzes y eliminar intentos."""
    
    URL_QUIZ_RESULTS_FILTERED = "{base}/mod/quiz/report.php?id={quiz_id}&mode=overview&tifirst={first}&tilast={last}"
    
    SELECTORS = {
        "attempts_table": "table#attempts",
        "attempt_checkbox": "input[name='attemptid[]']",
        # Botón eliminar - es un input[type="submit"] con id específico
        "delete_button": "input#deleteattemptsbutton",
        # Modal de confirmación de Moodle (YUI)
        "confirm_yes_btn": "input.btn-primary[value='Sí']",
        "confirm_dialog": ".moodle-dialogue-wrap",
    }
    
    def __init__(self, browser: BrowserManager):
        self.browser = browser
        self.base_url = settings.moodle_base_url
    
    def delete_user_attempts(
        self,
        quiz_id: str,
        user_email: str,
        user_firstname: str,
        user_lastname: str
    ) -> DeleteAttemptResult:
        """Elimina los intentos de un usuario en un quiz específico."""
        logger.info(f"Eliminando intentos de {user_email} en quiz {quiz_id}")
        
        try:
            # Obtener iniciales para filtro
            first_initial = user_firstname[0].upper() if user_firstname else ""
            last_initial = user_lastname[0].upper() if user_lastname else ""
            
            if not first_initial or not last_initial:
                return DeleteAttemptResult(
                    success=False, quiz_id=quiz_id, quiz_name="",
                    attempts_deleted=0, message="Se requiere nombre y apellido",
                    error="Nombre o apellido vacío"
                )
            
            # Construir URL con filtro de iniciales
            url = self.URL_QUIZ_RESULTS_FILTERED.format(
                base=self.base_url, quiz_id=quiz_id,
                first=first_initial, last=last_initial
            )
            
            logger.debug(f"Navegando a: {url}")
            
            # Navegar a la página
            self.browser.driver.get(url)
            
            # Esperar a que cargue la página (tabla o mensaje "Nada que mostrar")
            page_ready = self._wait_for_results_page()
            
            if not page_ready:
                return DeleteAttemptResult(
                    success=False, quiz_id=quiz_id, quiz_name="",
                    attempts_deleted=0, message="Timeout cargando página",
                    error="La página no cargó correctamente"
                )
            
            # Verificar si hay "Nada que mostrar"
            body_text = self.browser.driver.find_element(By.TAG_NAME, "body").text
            if "Nada que mostrar" in body_text:
                logger.info(f"No hay intentos de {user_email} (Nada que mostrar)")
                return DeleteAttemptResult(
                    success=True, quiz_id=quiz_id, quiz_name="",
                    attempts_deleted=0, message="No hay intentos para eliminar"
                )
            
            # Buscar intentos del usuario
            attempts_found = self._find_user_attempts(user_email)
            
            if not attempts_found:
                logger.info(f"No se encontraron intentos de {user_email}")
                return DeleteAttemptResult(
                    success=True, quiz_id=quiz_id, quiz_name="",
                    attempts_deleted=0, message="No hay intentos para eliminar"
                )
            
            # Seleccionar los checkboxes
            selected = self._select_user_attempts(user_email)
            
            if selected == 0:
                logger.warning("No se pudieron seleccionar intentos")
                return DeleteAttemptResult(
                    success=True, quiz_id=quiz_id, quiz_name="",
                    attempts_deleted=0, message="No se pudieron seleccionar intentos"
                )
            
            logger.info(f"Seleccionados {selected} intentos, procediendo a eliminar...")
            
            # Eliminar intentos
            if self._click_delete_and_confirm():
                logger.info(f"✓ Eliminados {selected} intentos de {user_email}")
                return DeleteAttemptResult(
                    success=True, quiz_id=quiz_id, quiz_name="",
                    attempts_deleted=selected, message=f"Eliminados {selected} intento(s)"
                )
            else:
                return DeleteAttemptResult(
                    success=False, quiz_id=quiz_id, quiz_name="",
                    attempts_deleted=0, message="Error al confirmar eliminación",
                    error="No se pudo completar la eliminación"
                )
                
        except Exception as e:
            logger.error(f"Error eliminando intentos: {e}")
            return DeleteAttemptResult(
                success=False, quiz_id=quiz_id, quiz_name="",
                attempts_deleted=0, message="Error inesperado", error=str(e)
            )
    
    def _wait_for_results_page(self, timeout: int = 15) -> bool:
        """Espera a que la página de resultados esté lista."""
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                # Verificar URL correcta
                if "report.php" not in self.browser.driver.current_url:
                    time.sleep(0.3)
                    continue
                
                body_text = self.browser.driver.find_element(By.TAG_NAME, "body").text
                
                # Página lista si tiene "Nada que mostrar" o tabla de intentos
                if "Nada que mostrar" in body_text:
                    return True
                
                tables = self.browser.driver.find_elements(By.CSS_SELECTOR, "table#attempts")
                if tables:
                    return True
                    
            except Exception as e:
                logger.debug(f"Esperando página: {e}")
            
            time.sleep(0.3)
        
        return False
    
    def _find_user_attempts(self, user_email: str) -> bool:
        """Verifica si existen intentos del usuario en la tabla."""
        try:
            # Buscar celda que contenga el email (columna c3)
            email_cells = self.browser.driver.find_elements(
                By.XPATH,
                f"//table[@id='attempts']//td[contains(@class, 'c3') and contains(text(), '{user_email}')]"
            )
            return len(email_cells) > 0
        except Exception as e:
            logger.debug(f"Error buscando intentos: {e}")
            return False
    
    def _select_user_attempts(self, user_email: str) -> int:
        """Selecciona los checkboxes de intentos del usuario."""
        selected = 0
        
        try:
            # Buscar celdas con el email
            email_cells = self.browser.driver.find_elements(
                By.XPATH,
                f"//table[@id='attempts']//td[contains(text(), '{user_email}')]"
            )
            
            for email_cell in email_cells:
                try:
                    # Obtener la fila padre
                    row = email_cell.find_element(By.XPATH, "./ancestor::tr")
                    
                    # Buscar checkbox en la fila
                    checkbox = row.find_element(By.CSS_SELECTOR, "input[name='attemptid[]']")
                    
                    if not checkbox.is_selected():
                        # Click con JavaScript para evitar problemas de visibilidad
                        self.browser.driver.execute_script("arguments[0].click();", checkbox)
                        selected += 1
                        logger.debug(f"Checkbox seleccionado para {user_email}")
                        
                except NoSuchElementException:
                    continue
                except Exception as e:
                    logger.debug(f"Error seleccionando checkbox: {e}")
                    continue
            
            logger.info(f"Total checkboxes seleccionados: {selected}")
            return selected
            
        except Exception as e:
            logger.error(f"Error seleccionando intentos: {e}")
            return 0
    
    def _click_delete_and_confirm(self) -> bool:
        """Hace click en eliminar y confirma la acción."""
        try:
            # 1. Buscar y hacer click en el botón de eliminar
            # Es un input[type="submit"] con id="deleteattemptsbutton"
            delete_btn = self.browser.driver.find_element(
                By.CSS_SELECTOR,
                "input#deleteattemptsbutton"
            )
            
            # Scroll al botón
            self.browser.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                delete_btn
            )
            time.sleep(0.3)
            
            # Click en eliminar
            logger.debug("Haciendo click en botón eliminar...")
            self.browser.driver.execute_script("arguments[0].click();", delete_btn)
            
            # 2. Esperar el modal de confirmación y confirmar
            time.sleep(0.5)  # Dar tiempo al modal para aparecer
            
            return self._confirm_deletion()
            
        except NoSuchElementException:
            logger.warning("No se encontró botón de eliminar")
            return False
        except Exception as e:
            logger.error(f"Error al eliminar: {e}")
            return False
    
    def _confirm_deletion(self) -> bool:
        """Confirma la eliminación en el diálogo modal de Moodle."""
        try:
            # Esperar a que aparezca el modal
            # El modal de Moodle usa YUI y tiene clase "moodle-dialogue-wrap"
            for attempt in range(20):  # 4 segundos máximo
                try:
                    # Buscar el botón "Sí" en el modal
                    # Selector: input con class="btn btn-primary" y value="Sí"
                    confirm_btn = self.browser.driver.find_element(
                        By.CSS_SELECTOR,
                        "input.btn-primary[value='Sí']"
                    )
                    
                    if confirm_btn.is_displayed():
                        logger.debug("Botón de confirmación encontrado, haciendo click...")
                        self.browser.driver.execute_script("arguments[0].click();", confirm_btn)
                        
                        # Esperar a que se procese la eliminación
                        time.sleep(1)
                        logger.debug("Confirmación enviada")
                        return True
                        
                except NoSuchElementException:
                    pass
                
                time.sleep(0.2)
            
            # Fallback: buscar por otros selectores
            fallback_selectors = [
                "input[value='Sí']",
                ".confirmation-buttons input.btn-primary",
                ".moodle-dialogue-bd input.btn-primary",
            ]
            
            for selector in fallback_selectors:
                try:
                    btn = self.browser.driver.find_element(By.CSS_SELECTOR, selector)
                    if btn.is_displayed():
                        self.browser.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1)
                        logger.debug(f"Confirmación enviada con selector: {selector}")
                        return True
                except:
                    continue
            
            logger.warning("No se encontró botón de confirmación después de esperar")
            return False
            
        except Exception as e:
            logger.error(f"Error confirmando eliminación: {e}")
            return False
    
    def delete_all_course_attempts(
        self,
        course_id: str,
        user_email: str,
        user_firstname: str,
        user_lastname: str,
        quizzes: List = None
    ) -> List[DeleteAttemptResult]:
        """Elimina los intentos de un usuario en todos los quizzes de un curso."""
        logger.info(f"Limpiando intentos de {user_email} en curso {course_id}")
        
        results = []
        
        if quizzes is None:
            from components.course import CourseComponent
            course_component = CourseComponent(self.browser)
            quizzes = course_component.get_course_quizzes(course_id)
        
        if not quizzes:
            logger.warning(f"No se encontraron quizzes en curso {course_id}")
            return results
        
        logger.info(f"Procesando {len(quizzes)} quizzes")
        
        for quiz in quizzes:
            quiz_id = quiz.quiz_id if hasattr(quiz, 'quiz_id') else quiz.get('quiz_id', '')
            
            result = self.delete_user_attempts(
                quiz_id=quiz_id,
                user_email=user_email,
                user_firstname=user_firstname,
                user_lastname=user_lastname
            )
            results.append(result)
        
        total_deleted = sum(r.attempts_deleted for r in results)
        successful = sum(1 for r in results if r.success)
        logger.info(f"Limpieza completada: {total_deleted} intentos eliminados en {successful}/{len(results)} quizzes")
        
        return results