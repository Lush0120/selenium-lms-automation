"""
models/course.py
Modelos de datos para cursos/pruebas con validación Pydantic.

ACTUALIZADO v2:
- Agregado método get_table_data() para generar datos de tabla del documento
- Soporte para múltiples niveles y pruebas técnicas

Estos modelos representan los cursos de Moodle y sus características,
permitiendo serialización a JSON para persistencia local.

Estructura:
- CourseCharacteristic: Un par clave-valor de característica
- CourseData: Datos completos de un curso/prueba
- CourseCatalog: Colección de cursos con métodos de búsqueda
"""

import re
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from pydantic import BaseModel, Field, computed_field

from core.logger import get_logger

logger = get_logger(__name__)


class CourseCategory(str, Enum):
    """
    Categorías de cursos disponibles.
    
    Cada categoría tiene un ID fijo en Moodle que no cambia.
    """
    PRUEBAS_TECNICAS = "50"
    PRUEBAS_DIAGNOSTICAS = "35"
    
    @property
    def display_name(self) -> str:
        """Nombre legible de la categoría."""
        names = {
            "50": "Pruebas Técnicas",
            "35": "Pruebas Diagnósticas"
        }
        return names.get(self.value, self.value)


class CourseCharacteristic(BaseModel):
    """
    Una característica individual del curso.
    
    Representa un par clave-valor como:
    - "Nivel Básico": "10 Preguntas"
    - "Duración por cuestionario": "15 Minutos"
    
    Attributes:
        name: Nombre de la característica
        value: Valor de la característica
    """
    name: str = Field(..., description="Nombre de la característica")
    value: str = Field(..., description="Valor de la característica")
    
    def __str__(self) -> str:
        return f"{self.name}: {self.value}"


@dataclass
class TableData:
    """
    Datos estructurados para la tabla del documento Word.
    
    Attributes:
        nombre: Nombre de la prueba
        url: URL de acceso
        niveles: Lista de dicts con {"nivel": str, "tiempo": str}
        lenguaje: Idioma de la prueba
        monitorizacion: Si tiene monitorización
    """
    nombre: str
    url: str
    niveles: List[Dict[str, str]]
    lenguaje: str
    monitorizacion: str


class CourseData(BaseModel):
    """
    Datos completos de un curso/prueba en Moodle.
    
    Almacena toda la información necesaria para:
    - Identificar el curso
    - Acceder directamente a sus secciones (sin navegar)
    - Mostrar sus características en reportes
    
    Attributes:
        course_id: ID único del curso en Moodle
        name: Nombre completo del curso
        category: Categoría (técnica o diagnóstica)
        visible: Si el curso está visible para estudiantes
        characteristics: Lista de características del curso
        updated_at: Fecha de última actualización del cache
        quizzes: Lista de quizzes del curso
    """
    course_id: str = Field(..., description="ID del curso en Moodle")
    name: str = Field(..., description="Nombre del curso")
    category: CourseCategory = Field(..., description="Categoría del curso")
    visible: bool = Field(default=True, description="Si está visible")
    characteristics: list[CourseCharacteristic] = Field(
        default_factory=list,
        description="Características del curso"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Última actualización"
    )
    quizzes: list["QuizData"] = Field(
        default_factory=list,
        description="Quizzes del curso"
    )
    
    # ==================== URLs computadas ====================
    
    @computed_field
    @property
    def url_course(self) -> str:
        """URL para ver el curso."""
        return f"https://campusvirtual.izyacademy.com/course/view.php?id={self.course_id}"
    
    @computed_field
    @property
    def url_grades(self) -> str:
        """URL para ver calificaciones."""
        return f"https://campusvirtual.izyacademy.com/grade/report/grader/index.php?id={self.course_id}"
    
    @computed_field
    @property
    def url_enroll(self) -> str:
        """URL para matricular usuarios."""
        return f"https://campusvirtual.izyacademy.com/enrol/manual/manage.php?enrolid={self.course_id}"
    
    # ==================== Métodos de utilidad ====================
    
    def get_characteristic(self, name: str) -> Optional[str]:
        """
        Obtiene el valor de una característica por nombre.
        
        Args:
            name: Nombre de la característica (parcial, case-insensitive)
            
        Returns:
            Valor de la característica o None si no existe
        """
        name_lower = name.lower()
        for char in self.characteristics:
            if name_lower in char.name.lower():
                return char.value
        return None
    
    def get_duration(self) -> Optional[str]:
        """Obtiene la duración del cuestionario."""
        return self.get_characteristic("duración")
    
    def get_total_questions(self) -> int:
        """
        Calcula el total de preguntas sumando todos los niveles.
        
        Returns:
            Total de preguntas o 0 si no hay niveles definidos
        """
        total = 0
        for char in self.characteristics:
            if "nivel" in char.name.lower() and "pregunta" in char.value.lower():
                # Extraer número de "10 Preguntas" -> 10
                try:
                    num = int(''.join(filter(str.isdigit, char.value)))
                    total += num
                except ValueError:
                    pass
        return total
    
    def get_table_data(self) -> TableData:
        """
        Genera datos estructurados para la tabla del documento Word.
        
        Analiza las características y determina:
        - Si es una prueba por niveles (Básico, Intermedio, Avanzado)
        - Si es una prueba técnica con un solo nivel
        - El tiempo/duración correspondiente a cada nivel
        - Idioma y monitorización
        
        Returns:
            TableData con la información estructurada
        """
        niveles = []
        duracion = None
        lenguaje = "N/A"
        monitorizacion = "N/A"
        
        # Patrones para detectar niveles
        nivel_pattern = re.compile(r'^nivel\s+(.+)$', re.IGNORECASE)
        
        # Primera pasada: identificar características
        for char in self.characteristics:
            name_lower = char.name.lower().strip()
            value = char.value.strip()
            
            # Detectar niveles explícitos (Nivel Básico, Nivel Intermedio, etc.)
            match = nivel_pattern.match(char.name.strip())
            if match:
                nivel_nombre = match.group(1).strip()
                # Solo agregar si el valor contiene "preguntas" (es un nivel real)
                if "pregunta" in value.lower():
                    niveles.append({
                        "nivel": nivel_nombre.capitalize(),
                        "tiempo": ""  # Se llenará después
                    })
                continue
            
            # Detectar "Nivel de la prueba" (formato de pruebas técnicas)
            if name_lower == "nivel de la prueba":
                # Este es el formato de pruebas técnicas
                niveles.append({
                    "nivel": value,
                    "tiempo": ""
                })
                continue
            
            # Detectar duración (múltiples variantes)
            if any(keyword in name_lower for keyword in [
                "duración", "duracion", "tiempo"
            ]):
                duracion = value
                continue
            
            # Detectar disponibilidad (para pruebas técnicas)
            if "disponibilidad" in name_lower:
                duracion = value
                continue
            
            # Detectar idioma/lenguaje
            if name_lower in ["idioma", "lenguaje"]:
                lenguaje = value
                continue
            
            # Detectar monitorización (múltiples variantes)
            if any(keyword in name_lower for keyword in [
                "monitorización", "monitorizacion", "monitorizado", 
                "supervisión", "supervision"
            ]):
                monitorizacion = value
                continue
        
        # Si no encontramos niveles, crear uno genérico
        if not niveles:
            niveles.append({
                "nivel": "General",
                "tiempo": duracion or "N/A"
            })
        else:
            # Asignar la duración a todos los niveles
            for nivel in niveles:
                nivel["tiempo"] = duracion or "N/A"
        
        return TableData(
            nombre=self.name,
            url=self.url_course,
            niveles=niveles,
            lenguaje=lenguaje,
            monitorizacion=monitorizacion
        )
    
    def to_email_table(self) -> str:
        """
        Genera una tabla HTML con las características para emails.
        
        Returns:
            String HTML con la tabla de características
        """
        rows = []
        for char in self.characteristics:
            rows.append(f"<tr><td>{char.name}</td><td>{char.value}</td></tr>")
        
        return f"""
        <table border="1" cellpadding="5" cellspacing="0">
            <thead>
                <tr><th colspan="2">{self.name}</th></tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        """
    
    def __str__(self) -> str:
        return f"{self.name} (ID: {self.course_id})"


class QuizData(BaseModel):
    """Modelo para un quiz/cuestionario de Moodle."""
    
    quiz_id: str
    name: str
    course_id: str
    url: str = ""
    results_url: str = ""
    
    def model_post_init(self, __context) -> None:
        """Genera URLs después de inicializar."""
        base = "https://campusvirtual.izyacademy.com"
        if not self.url:
            self.url = f"{base}/mod/quiz/view.php?id={self.quiz_id}"
        if not self.results_url:
            self.results_url = f"{base}/mod/quiz/report.php?id={self.quiz_id}&mode=overview"
    
    def get_filtered_results_url(self, first_initial: str, last_initial: str) -> str:
        """Genera URL de resultados filtrada por iniciales."""
        return f"{self.results_url}&tifirst={first_initial}&tilast={last_initial}"


class CourseCatalog(BaseModel):
    """
    Catálogo completo de cursos con métodos de búsqueda.
    
    Representa el archivo courses.json y provee métodos para:
    - Buscar cursos por nombre o ID
    - Filtrar por categoría
    - Serializar/deserializar desde JSON
    
    Attributes:
        courses: Lista de todos los cursos
        last_sync: Fecha de última sincronización con Moodle
    """
    courses: list[CourseData] = Field(default_factory=list)
    last_sync: Optional[datetime] = Field(
        default=None,
        description="Última sincronización con Moodle"
    )
    
    # ==================== Búsqueda ====================
    
    def find_by_id(self, course_id: str) -> Optional[CourseData]:
        """Busca un curso por su ID exacto."""
        for course in self.courses:
            if course.course_id == course_id:
                return course
        return None
    
    def find_by_name(self, name: str, exact: bool = False) -> list[CourseData]:
        """
        Busca cursos por nombre.
        
        Args:
            name: Texto a buscar
            exact: Si True, busca coincidencia exacta
            
        Returns:
            Lista de cursos que coinciden
        """
        name_lower = name.lower()
        results = []
        
        for course in self.courses:
            if exact:
                if course.name.lower() == name_lower:
                    results.append(course)
            else:
                if name_lower in course.name.lower():
                    results.append(course)
        
        return results
    
    def find_one_by_name(self, name: str) -> Optional[CourseData]:
        """
        Busca un único curso por nombre.
        
        Returns:
            El curso si hay exactamente uno, None si hay 0 o más de 1
        """
        results = self.find_by_name(name)
        if len(results) == 1:
            return results[0]
        return None
    
    # ==================== Filtros ====================
    
    def filter_by_category(self, category: CourseCategory) -> list[CourseData]:
        """Filtra cursos por categoría."""
        return [c for c in self.courses if c.category == category]
    
    def get_tecnicas(self) -> list[CourseData]:
        """Obtiene todas las pruebas técnicas."""
        return self.filter_by_category(CourseCategory.PRUEBAS_TECNICAS)
    
    def get_diagnosticas(self) -> list[CourseData]:
        """Obtiene todas las pruebas diagnósticas."""
        return self.filter_by_category(CourseCategory.PRUEBAS_DIAGNOSTICAS)
    
    def get_visible(self) -> list[CourseData]:
        """Obtiene solo cursos visibles."""
        return [c for c in self.courses if c.visible]
    
    # ==================== Gestión ====================
    
    def add_or_update(self, course: CourseData) -> None:
        """
        Agrega un curso o actualiza si ya existe.
        
        Args:
            course: Curso a agregar/actualizar
        """
        existing = self.find_by_id(course.course_id)
        if existing:
            # Actualizar
            idx = self.courses.index(existing)
            self.courses[idx] = course
            logger.debug(f"Curso actualizado: {course.name}")
        else:
            # Agregar
            self.courses.append(course)
            logger.debug(f"Curso agregado: {course.name}")
    
    def remove(self, course_id: str) -> bool:
        """
        Elimina un curso por ID.
        
        Returns:
            True si se eliminó, False si no existía
        """
        course = self.find_by_id(course_id)
        if course:
            self.courses.remove(course)
            logger.debug(f"Curso eliminado: {course.name}")
            return True
        return False
    
    # ==================== Estadísticas ====================
    
    @property
    def total_courses(self) -> int:
        """Total de cursos en el catálogo."""
        return len(self.courses)
    
    @property
    def total_tecnicas(self) -> int:
        """Total de pruebas técnicas."""
        return len(self.get_tecnicas())
    
    @property
    def total_diagnosticas(self) -> int:
        """Total de pruebas diagnósticas."""
        return len(self.get_diagnosticas())
    
    def summary(self) -> str:
        """Resumen del catálogo."""
        sync_str = self.last_sync.strftime("%Y-%m-%d %H:%M") if self.last_sync else "Nunca"
        return (
            f"Catálogo de Cursos\n"
            f"  Total: {self.total_courses}\n"
            f"  Técnicas: {self.total_tecnicas}\n"
            f"  Diagnósticas: {self.total_diagnosticas}\n"
            f"  Última sync: {sync_str}"
        )