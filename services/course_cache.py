"""
services/course_cache.py
Servicio para gestionar el cache local de cursos.

Este servicio maneja:
- Cargar/guardar el catálogo desde/hacia JSON
- Proporcionar acceso rápido a los cursos sin navegar Moodle
- Mantener sincronizado el cache cuando sea necesario

¿Por qué un servicio separado del componente?
- components/ → Interactúa con Moodle (Selenium)
- services/ → Lógica de negocio y persistencia (sin Selenium)

Esto permite usar el cache sin abrir el navegador.

Uso:
    from services.course_cache import CourseCache
    
    cache = CourseCache()
    
    # Buscar curso (sin abrir navegador)
    curso = cache.find_by_name("SQL")
    print(curso.url_grades)  # URL directa a calificaciones
    
    # Listar todas las diagnósticas
    for curso in cache.get_diagnosticas():
        print(curso.name)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from models.course import CourseCatalog, CourseData, CourseCategory
from core.logger import get_logger

logger = get_logger(__name__)


# Ruta por defecto del archivo de cache
DEFAULT_CACHE_PATH = Path(__file__).parent.parent / "data" / "courses.json"


class CourseCache:
    """
    Gestiona el cache local de cursos.
    
    Carga el catálogo desde JSON al inicializar y proporciona
    métodos para buscar cursos sin necesidad de conectar a Moodle.
    
    Attributes:
        catalog: El catálogo de cursos cargado
        cache_path: Ruta al archivo JSON
    """
    
    def __init__(self, cache_path: Optional[Path] = None):
        """
        Inicializa el cache.
        
        Args:
            cache_path: Ruta al archivo JSON. Si no se proporciona,
                       usa data/courses.json
        """
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self.catalog: CourseCatalog = self._load_or_create()
    
    # ==================== Carga y guardado ====================
    
    def _load_or_create(self) -> CourseCatalog:
        """
        Carga el catálogo desde JSON o crea uno vacío.
        
        Returns:
            CourseCatalog cargado o vacío
        """
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                catalog = CourseCatalog.model_validate(data)
                logger.info(f"Cache cargado: {catalog.total_courses} cursos")
                return catalog
            except Exception as e:
                logger.error(f"Error cargando cache: {e}")
                logger.info("Creando catálogo vacío")
                return CourseCatalog()
        else:
            logger.info("No existe cache, creando catálogo vacío")
            return CourseCatalog()
    
    def save(self) -> bool:
        """
        Guarda el catálogo en JSON.
        
        Returns:
            True si se guardó correctamente
        """
        try:
            # Crear directorio si no existe
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Serializar con fechas en formato ISO
            data = self.catalog.model_dump(mode='json')
            
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Cache guardado: {self.catalog.total_courses} cursos")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando cache: {e}")
            return False
    
    def reload(self) -> None:
        """Recarga el catálogo desde el archivo."""
        self.catalog = self._load_or_create()
    
    # ==================== Búsqueda (delegada al catálogo) ====================
    
    def find_by_id(self, course_id: str) -> Optional[CourseData]:
        """Busca un curso por ID."""
        return self.catalog.find_by_id(course_id)
    
    def find_by_name(self, name: str, exact: bool = False) -> list[CourseData]:
        """Busca cursos por nombre."""
        return self.catalog.find_by_name(name, exact)
    
    def find_one_by_name(self, name: str) -> Optional[CourseData]:
        """Busca un único curso por nombre."""
        return self.catalog.find_one_by_name(name)
    
    # ==================== Filtros (delegados al catálogo) ====================
    
    def get_tecnicas(self) -> list[CourseData]:
        """Obtiene todas las pruebas técnicas."""
        return self.catalog.get_tecnicas()
    
    def get_diagnosticas(self) -> list[CourseData]:
        """Obtiene todas las pruebas diagnósticas."""
        return self.catalog.get_diagnosticas()
    
    def get_all(self) -> list[CourseData]:
        """Obtiene todos los cursos."""
        return self.catalog.courses
    
    def get_visible(self) -> list[CourseData]:
        """Obtiene solo cursos visibles."""
        return self.catalog.get_visible()
    
    # ==================== Gestión ====================
    
    def add_or_update(self, course: CourseData, auto_save: bool = True) -> None:
        """
        Agrega o actualiza un curso.
        
        Args:
            course: Curso a agregar/actualizar
            auto_save: Si guardar automáticamente después
        """
        self.catalog.add_or_update(course)
        if auto_save:
            self.save()
    
    def add_many(self, courses: list[CourseData], auto_save: bool = True) -> None:
        """
        Agrega o actualiza múltiples cursos.
        
        Args:
            courses: Lista de cursos
            auto_save: Si guardar al final
        """
        for course in courses:
            self.catalog.add_or_update(course)
        
        if auto_save:
            self.save()
    
    def remove(self, course_id: str, auto_save: bool = True) -> bool:
        """
        Elimina un curso por ID.
        
        Returns:
            True si se eliminó
        """
        result = self.catalog.remove(course_id)
        if result and auto_save:
            self.save()
        return result
    
    def clear(self, auto_save: bool = True) -> None:
        """Elimina todos los cursos del catálogo."""
        self.catalog.courses = []
        self.catalog.last_sync = None
        if auto_save:
            self.save()
        logger.info("Cache limpiado")
    
    def update_sync_time(self, auto_save: bool = True) -> None:
        """Actualiza la fecha de última sincronización."""
        self.catalog.last_sync = datetime.now()
        if auto_save:
            self.save()
    
    # ==================== Información ====================
    
    @property
    def is_empty(self) -> bool:
        """Si el cache está vacío."""
        return self.catalog.total_courses == 0
    
    @property
    def total_courses(self) -> int:
        """Total de cursos."""
        return self.catalog.total_courses
    
    @property
    def last_sync(self) -> Optional[datetime]:
        """Fecha de última sincronización."""
        return self.catalog.last_sync
    
    def summary(self) -> str:
        """Resumen del cache."""
        return self.catalog.summary()
    
    def print_summary(self) -> None:
        """Imprime el resumen del cache."""
        print(self.summary())
    
    # ==================== Utilidades ====================
    
    def list_names(self, category: Optional[CourseCategory] = None) -> list[str]:
        """
        Lista los nombres de los cursos.
        
        Args:
            category: Filtrar por categoría (opcional)
            
        Returns:
            Lista de nombres
        """
        if category:
            courses = self.catalog.filter_by_category(category)
        else:
            courses = self.catalog.courses
        
        return [c.name for c in courses]
    
    def export_to_dict(self) -> dict:
        """
        Exporta el catálogo como diccionario.
        
        Útil para integración con otros sistemas.
        """
        return self.catalog.model_dump(mode='json')
