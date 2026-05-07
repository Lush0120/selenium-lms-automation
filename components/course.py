"""
components/course.py
Componente para gestionar cursos/pruebas en Moodle.

OPTIMIZADO v2:
- Usa esperas por elemento en lugar de wait_for_page_load()
- Navegación con navigate_and_wait()
- Extracción de quizzes más eficiente

VERSIÓN v2.1:
- NUEVO: Cierre automático del modal SMOWL al navegar a cursos

Este componente interactúa con Moodle para:
- Listar cursos de una categoría
- Extraer características de cada curso
- Sincronizar el catálogo local con Moodle
- Extraer quizzes de un curso

Uso:
    from core.browser import BrowserManager
    from components.course import CourseComponent
    
    with BrowserManager() as browser:
        # ... login ...
        
        courses = CourseComponent(browser)
        
        # Sincronizar catálogo completo
        courses.sync_catalog()
        
        # Obtener quizzes de un curso
        quizzes = courses.get_course_quizzes("616")
"""

import re
import time
from typing import Optional, List
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from core.browser import BrowserManager
from core.config import settings
from core.logger import get_logger
from models.course import (
    CourseData, 
    CourseCategory, 
    CourseCharacteristic,
    CourseCatalog,
    QuizData
)
from services.course_cache import CourseCache

logger = get_logger(__name__)

# Timeout para esperas de elementos
ELEMENT_TIMEOUT = 10


class CourseComponent:
    """
    Componente para extraer y gestionar cursos desde Moodle.
    
    OPTIMIZADO: Usa esperas por elemento para mayor velocidad.
    """
    
    # URLs base
    URL_MANAGEMENT = f"{settings.moodle_base_url}/course/management.php"
    URL_COURSE_VIEW = f"{settings.moodle_base_url}/course/view.php"
    
    # Selectores
    SELECTORS = {
        # Lista de cursos en management.php
        "course_list": "ul.course-list",
        "course_item": "li.listitem-course",
        "course_link": "a.coursename",
        
        # Características del curso (en course/view.php)
        "characteristics_container": "div.feature_course_widget",
        "characteristics_items": "div.feature_course_widget ul.list-group li",
        
        # Quizzes en el curso
        "quiz_link": "li.modtype_quiz a[href*='/mod/quiz/view.php']",
        "quiz_name_span": "span.instancename",
        
        # Contenido del curso (indica que cargó)
        "course_content": "div.course-content, #region-main",
        
        # Modal SMOWL
        "smowl_modal_btn": "#btn-smowl-entendido",
    }
    
    def __init__(self, browser: BrowserManager, cache: Optional[CourseCache] = None):
        """
        Inicializa el componente.
        
        Args:
            browser: Instancia del BrowserManager (debe estar logueado)
            cache: Servicio de cache (opcional, se crea uno si no se pasa)
        """
        self.browser = browser
        self.cache = cache or CourseCache()
    
    # ==================== Modal SMOWL ====================
    
    def _close_smowl_modal(self) -> bool:
        """
        Cierra el modal de SMOWL si está presente.
        
        Este modal aparece en pruebas con monitorización activa
        y bloquea cualquier interacción con la página.
        
        Returns:
            True si se cerró el modal, False si no estaba presente
        """
        try:
            smowl_btn = self.browser.driver.find_element(
                By.ID, "btn-smowl-entendido"
            )
            
            if smowl_btn.is_displayed():
                logger.debug("Modal SMOWL detectado en curso, cerrando...")
                self.browser.driver.execute_script("arguments[0].click();", smowl_btn)
                time.sleep(0.3)
                return True
                
        except NoSuchElementException:
            pass
        except Exception as e:
            logger.debug(f"Error cerrando modal SMOWL: {e}")
        
        return False
    
    # ==================== Sincronización completa ====================
    
    def sync_catalog(self, categories: Optional[List[CourseCategory]] = None) -> CourseCatalog:
        """
        Sincroniza el catálogo local con Moodle.
        
        Extrae todos los cursos de las categorías especificadas,
        incluyendo sus características, y actualiza el cache.
        
        Args:
            categories: Lista de categorías a sincronizar.
                       Si no se especifica, sincroniza ambas.
        
        Returns:
            CourseCatalog actualizado
        """
        if categories is None:
            categories = [
                CourseCategory.PRUEBAS_DIAGNOSTICAS,
                CourseCategory.PRUEBAS_TECNICAS
            ]
        
        logger.info(f"Iniciando sincronización de {len(categories)} categoría(s)")
        
        all_courses = []
        
        for category in categories:
            logger.info(f"Sincronizando: {category.display_name}")
            courses = self.fetch_category(category)
            all_courses.extend(courses)
            logger.info(f"  → {len(courses)} cursos extraídos")
        
        # Actualizar cache
        self.cache.add_many(all_courses, auto_save=False)
        self.cache.update_sync_time(auto_save=False)
        self.cache.save()
        
        logger.info(f"Sincronización completa: {len(all_courses)} cursos")
        return self.cache.catalog
    
    # ==================== Extracción por categoría ====================
    
    def fetch_category(self, category: CourseCategory) -> List[CourseData]:
        """
        Extrae todos los cursos de una categoría.
        
        OPTIMIZADO: Usa navigate_and_wait() en lugar de wait_for_page_load()
        
        Args:
            category: Categoría a extraer
            
        Returns:
            Lista de CourseData con características
        """
        # Navegar a la categoría con todos los cursos visibles
        url = f"{self.URL_MANAGEMENT}?categoryid={category.value}&perpage=999"
        
        # OPTIMIZADO: Esperar lista de cursos en lugar de toda la página
        self.browser.navigate_and_wait(
            url,
            wait_for=(By.CSS_SELECTOR, self.SELECTORS["course_list"]),
            timeout=ELEMENT_TIMEOUT
        )
        
        # Extraer lista básica de cursos
        courses_basic = self._extract_course_list(category)
        logger.info(f"Encontrados {len(courses_basic)} cursos en {category.display_name}")
        
        # Para cada curso, extraer características
        courses_complete = []
        for i, course in enumerate(courses_basic):
            logger.debug(f"Extrayendo características ({i+1}/{len(courses_basic)}): {course.name}")
            
            try:
                characteristics = self._fetch_course_characteristics(course.course_id)
                course.characteristics = characteristics
                course.updated_at = datetime.now()
                courses_complete.append(course)
            except Exception as e:
                logger.warning(f"Error extrayendo características de {course.name}: {e}")
                # Agregar sin características
                courses_complete.append(course)
        
        return courses_complete
    
    def _extract_course_list(self, category: CourseCategory) -> List[CourseData]:
        """
        Extrae la lista básica de cursos (sin características).
        
        Solo extrae cursos visibles (data-visible="1").
        """
        courses = []
        
        try:
            # Buscar todos los items de curso
            items = self.browser.driver.find_elements(
                By.CSS_SELECTOR, 
                self.SELECTORS["course_item"]
            )
            
            for item in items:
                try:
                    # Extraer visibilidad - saltar ocultos
                    visible = item.get_attribute("data-visible") == "1"
                    if not visible:
                        continue
                    
                    # Extraer ID
                    course_id = item.get_attribute("data-id")
                    if not course_id:
                        continue
                    
                    # Extraer nombre del enlace
                    link = item.find_element(By.CSS_SELECTOR, self.SELECTORS["course_link"])
                    name = link.text.strip()
                    
                    if not name:
                        continue
                    
                    course = CourseData(
                        course_id=course_id,
                        name=name,
                        category=category,
                        visible=True,
                        characteristics=[],
                        updated_at=datetime.now()
                    )
                    courses.append(course)
                    
                except NoSuchElementException:
                    continue
                except Exception as e:
                    logger.debug(f"Error extrayendo curso: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error extrayendo lista de cursos: {e}")
        
        return courses
    
    # ==================== Extracción de características ====================
    
    def _fetch_course_characteristics(self, course_id: str) -> List[CourseCharacteristic]:
        """
        Navega a un curso y extrae sus características.
        
        OPTIMIZADO: Usa navigate_and_wait() con selector de contenido
        ACTUALIZADO v2.1: Cierra modal SMOWL si aparece
        """
        url = f"{self.URL_COURSE_VIEW}?id={course_id}"
        
        # OPTIMIZADO: Esperar contenido del curso en lugar de toda la página
        self.browser.navigate_and_wait(
            url,
            wait_for=(By.CSS_SELECTOR, self.SELECTORS["course_content"]),
            timeout=ELEMENT_TIMEOUT
        )
        
        # NUEVO v2.1: Cerrar modal SMOWL si aparece
        self._close_smowl_modal()
        
        return self._extract_characteristics()
    
    def _extract_characteristics(self) -> List[CourseCharacteristic]:
        """
        Extrae las características del curso actual.
        
        Parsea el widget de características que tiene formato:
        <li>Nombre <span>Valor</span></li>
        """
        characteristics = []
        
        try:
            # Verificar si existe el contenedor
            containers = self.browser.driver.find_elements(
                By.CSS_SELECTOR,
                self.SELECTORS["characteristics_container"]
            )
            
            if not containers:
                logger.debug("No se encontró widget de características")
                return characteristics
            
            # Extraer cada item
            items = self.browser.driver.find_elements(
                By.CSS_SELECTOR,
                self.SELECTORS["characteristics_items"]
            )
            
            for item in items:
                try:
                    full_text = item.text.strip()
                    
                    # Intentar extraer el valor del span
                    try:
                        span = item.find_element(By.CSS_SELECTOR, "span")
                        value = span.text.strip()
                        name = full_text.replace(value, "").strip()
                    except NoSuchElementException:
                        # Si no hay span, parsear manualmente
                        parts = full_text.split()
                        if len(parts) >= 2:
                            value = " ".join(parts[-2:])
                            name = " ".join(parts[:-2])
                        else:
                            name = full_text
                            value = ""
                    
                    if name and value:
                        char = CourseCharacteristic(name=name, value=value)
                        characteristics.append(char)
                        
                except Exception as e:
                    logger.debug(f"Error extrayendo característica: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"Error buscando características: {e}")
        
        return characteristics
    
    # ==================== Extracción de Quizzes ====================
    
    def get_course_quizzes(self, course_id: str) -> List[QuizData]:
        """
        Extrae los quizzes de un curso.
        
        OPTIMIZADO: 
        - Usa navigate_and_wait() en lugar de wait_for_page_load()
        - Espera solo el contenido del curso, no toda la página
        
        ACTUALIZADO v2.1: Cierra modal SMOWL si aparece
        
        Args:
            course_id: ID del curso
            
        Returns:
            Lista de QuizData
        """
        url = f"{self.URL_COURSE_VIEW}?id={course_id}"
        logger.debug(f"Extrayendo quizzes del curso: {course_id}")
        
        # OPTIMIZADO: Esperar contenido del curso
        self.browser.navigate_and_wait(
            url,
            wait_for=(By.CSS_SELECTOR, self.SELECTORS["course_content"]),
            timeout=ELEMENT_TIMEOUT
        )
        
        # NUEVO v2.1: Cerrar modal SMOWL si aparece
        self._close_smowl_modal()
        
        quizzes = []
        seen_quiz_ids = set()  # Para evitar duplicados
        
        try:
            # Buscar todos los quizzes en el contenido del curso
            quiz_elements = self.browser.driver.find_elements(
                By.CSS_SELECTOR,
                self.SELECTORS["quiz_link"]
            )
            
            for element in quiz_elements:
                try:
                    href = element.get_attribute("href")
                    if not href or "id=" not in href:
                        continue
                    
                    # Extraer ID del quiz
                    match = re.search(r'id=(\d+)', href)
                    if not match:
                        continue
                    quiz_id = match.group(1)
                    
                    # EVITAR DUPLICADOS
                    if quiz_id in seen_quiz_ids:
                        continue
                    seen_quiz_ids.add(quiz_id)
                    
                    # Obtener nombre del quiz
                    try:
                        name_span = element.find_element(
                            By.CSS_SELECTOR, 
                            self.SELECTORS["quiz_name_span"]
                        )
                        name = name_span.text.strip()
                    except NoSuchElementException:
                        name = element.text.strip()
                    
                    # Limpiar nombre (quitar texto oculto como "Cuestionario")
                    if "\n" in name:
                        name = name.split("\n")[0].strip()
                    
                    quiz = QuizData(
                        quiz_id=quiz_id,
                        name=name,
                        course_id=course_id
                    )
                    quizzes.append(quiz)
                    logger.debug(f"Quiz encontrado: {name} (ID: {quiz_id})")
                    
                except Exception as e:
                    logger.debug(f"Error extrayendo quiz: {e}")
                    continue
            
            logger.info(f"Quizzes encontrados en curso {course_id}: {len(quizzes)}")
            
        except Exception as e:
            logger.error(f"Error buscando quizzes: {e}")
        
        return quizzes
    
    # ==================== Métodos públicos de características ====================
    
    def get_course_characteristics(self, course_id: str) -> List[CourseCharacteristic]:
        """
        Obtiene las características de un curso específico.
        
        Args:
            course_id: ID del curso
            
        Returns:
            Lista de CourseCharacteristic
        """
        logger.info(f"Obteniendo características del curso: {course_id}")
        return self._fetch_course_characteristics(course_id)
    
    def get_course_characteristics_dict(self, course_id: str) -> dict:
        """
        Obtiene las características de un curso como diccionario.
        
        Args:
            course_id: ID del curso
            
        Returns:
            Diccionario con {nombre_característica: valor}
        """
        characteristics = self._fetch_course_characteristics(course_id)
        return {char.name: char.value for char in characteristics}
    
    def get_course_name(self, course_id: str) -> str:
        """
        Obtiene el nombre de un curso por su ID.
        
        Primero intenta desde el cache, si no navega al curso.
        
        ACTUALIZADO v2.1: Cierra modal SMOWL si aparece
        """
        # Intentar desde cache primero
        cached = self.cache.find_by_id(course_id)
        if cached:
            return cached.name
        
        # Navegar al curso
        try:
            url = f"{self.URL_COURSE_VIEW}?id={course_id}"
            
            self.browser.navigate_and_wait(
                url,
                wait_for=(By.CSS_SELECTOR, self.SELECTORS["course_content"]),
                timeout=ELEMENT_TIMEOUT
            )
            
            # NUEVO v2.1: Cerrar modal SMOWL si aparece
            self._close_smowl_modal()
            
            title = self.browser.driver.title
            name = title.split(":")[0].strip() if ":" in title else title.strip()
            return name
        except Exception as e:
            logger.error(f"Error obteniendo nombre del curso {course_id}: {e}")
            return ""
    
    # ==================== Métodos de utilidad ====================
    
    def fetch_single_course(self, course_id: str, category: CourseCategory) -> Optional[CourseData]:
        """
        Extrae un único curso por ID.
        
        ACTUALIZADO v2.1: Cierra modal SMOWL si aparece
        """
        try:
            url = f"{self.URL_COURSE_VIEW}?id={course_id}"
            
            self.browser.navigate_and_wait(
                url,
                wait_for=(By.CSS_SELECTOR, self.SELECTORS["course_content"]),
                timeout=ELEMENT_TIMEOUT
            )
            
            # NUEVO v2.1: Cerrar modal SMOWL si aparece
            self._close_smowl_modal()
            
            # Extraer nombre del título de la página
            try:
                title = self.browser.driver.title
                name = title.split(":")[0].strip() if ":" in title else title.strip()
            except:
                name = f"Curso {course_id}"
            
            # Extraer características
            characteristics = self._extract_characteristics()
            
            course = CourseData(
                course_id=course_id,
                name=name,
                category=category,
                visible=True,
                characteristics=characteristics,
                updated_at=datetime.now()
            )
            
            return course
            
        except Exception as e:
            logger.error(f"Error extrayendo curso {course_id}: {e}")
            return None
    
    def get_course_count(self, category: CourseCategory) -> int:
        """
        Obtiene el número de cursos en una categoría sin extraer detalles.
        """
        url = f"{self.URL_MANAGEMENT}?categoryid={category.value}"
        
        self.browser.navigate_and_wait(
            url,
            wait_for=(By.CSS_SELECTOR, self.SELECTORS["course_list"]),
            timeout=ELEMENT_TIMEOUT
        )
        
        items = self.browser.driver.find_elements(
            By.CSS_SELECTOR,
            self.SELECTORS["course_item"]
        )
        
        return len(items)
    
    # ==================== Acceso al cache ====================
    
    def get_cached_course(self, name: str) -> Optional[CourseData]:
        """Busca un curso en el cache local."""
        return self.cache.find_one_by_name(name)
    
    def get_cached_courses(self, category: Optional[CourseCategory] = None) -> List[CourseData]:
        """Obtiene cursos del cache local."""
        if category:
            return self.cache.catalog.filter_by_category(category)
        return self.cache.get_all()
    
    def is_cache_empty(self) -> bool:
        """Verifica si el cache está vacío."""
        return self.cache.is_empty
    
    def print_cache_summary(self) -> None:
        """Imprime resumen del cache."""
        self.cache.print_summary()