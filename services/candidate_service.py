"""
services/candidate_service.py
Servicio para procesar candidatos con flujo completo.

ACTUALIZADO v2:
- Integración con DocumentGenerator para generar documento Word
- Método generate_document() en CandidateResult
- Soporte para conversión automática de CourseData a PruebaInfo

Este servicio orquesta el flujo completo de un candidato:
1. Verificar/crear usuario (o actualizar contraseña si existe)
2. Por cada prueba seleccionada (secuencial):
   a. Limpiar intentos anteriores
   b. Matricular o reactivar matrícula
3. Generar documento Word con datos para el correo
4. Retornar datos listos para envío

Uso:
    from services.candidate_service import CandidateService, CandidateInput
    
    with BrowserManager() as browser:
        auth = AuthComponent(browser)
        auth.login(username, password)
        
        service = CandidateService(browser)
        
        candidate = CandidateInput(
            email="usuario@ejemplo.com",
            firstname="Juan",
            lastname="García",
            phone="123456789",
            course_ids=["616", "617"]
        )
        
        result = service.process_candidate(candidate)
        
        if result.success:
            # Generar documento Word
            doc_path = result.generate_document(output_dir="./output")
            print(f"Documento generado: {doc_path}")
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

from core.browser import BrowserManager
from core.logger import get_logger
from components.user import UserComponent
from components.course import CourseComponent
from components.enrollment import EnrollmentComponent
from components.quiz import QuizComponent
from models.user import UserData
from models.course import CourseData
from models.enrollment import EnrollmentConfig, EnrollmentDuration
from services.course_cache import CourseCache

logger = get_logger(__name__)


@dataclass
class CandidateInput:
    """Datos de entrada para procesar un candidato."""
    email: str
    firstname: str
    lastname: str
    phone: str = ""
    course_ids: list[str] = field(default_factory=list)
    duration_days: int = 1
    
    def get_duration(self) -> EnrollmentDuration:
        """Convierte días a EnrollmentDuration."""
        if self.duration_days == 2:
            return EnrollmentDuration.DOS_DIAS
        elif self.duration_days == 3:
            return EnrollmentDuration.TRES_DIAS
        return EnrollmentDuration.UN_DIA
    
    @property
    def full_name(self) -> str:
        """Nombre completo del candidato."""
        return f"{self.firstname} {self.lastname}"


@dataclass
class EnrollmentInfo:
    """Información de una matrícula para el correo."""
    course_id: str
    course_name: str
    course_url: str
    characteristics: dict[str, str]  # {"Nivel": "Intermedio", "Duración": "4 horas"}
    attempts_deleted: int = 0
    enrollment_status: str = ""  # "created", "reactivated", "already_active"
    course_data: Optional[CourseData] = None  # Referencia al CourseData original
    
    def to_dict(self) -> dict:
        """Convierte a diccionario para el correo."""
        return {
            "course_id": self.course_id,
            "course_name": self.course_name,
            "course_url": self.course_url,
            "characteristics": self.characteristics,
            "attempts_deleted": self.attempts_deleted,
            "enrollment_status": self.enrollment_status,
        }


@dataclass
class CandidateResult:
    """Resultado del procesamiento de un candidato."""
    success: bool
    message: str
    
    # Usuario
    user_created: bool = False
    user_existed: bool = False
    username: str = ""
    password: str = ""
    firstname: str = ""
    lastname: str = ""
    email: str = ""
    
    # Configuración
    duration_days: int = 1
    
    # Matrículas (lista de EnrollmentInfo)
    enrollments: list[EnrollmentInfo] = field(default_factory=list)
    
    # Resumen
    total_attempts_deleted: int = 0
    
    # Metadatos
    timestamp: datetime = field(default_factory=datetime.now)
    errors: list[str] = field(default_factory=list)
    
    @property
    def full_name(self) -> str:
        """Nombre completo del usuario."""
        return f"{self.firstname} {self.lastname}"
    
    @property
    def duration_text(self) -> str:
        """Texto de duración para el correo."""
        return f"{self.duration_days * 24} horas"
    
    def to_email_data(self) -> dict:
        """
        Genera diccionario con datos para la plantilla de correo.
        
        Returns:
            Diccionario con las variables de la plantilla:
            - nombre_completo: Nombre del candidato
            - usuario: Username
            - contrasena: Contraseña
            - dias_habilitada: Días que estarán habilitadas las pruebas
            - duracion_texto: Texto de duración (ej: "24 horas")
            - pruebas: Lista de pruebas matriculadas con características
        """
        return {
            "nombre_completo": self.full_name,
            "usuario": self.username,
            "contrasena": self.password,
            "dias_habilitada": self.duration_days,
            "duracion_texto": self.duration_text,
            "pruebas": [e.to_dict() for e in self.enrollments],
        }
    
    def generate_document(self, output_dir: str = ".") -> Optional[str]:
        """
        Genera el documento Word con los datos del correo.
        
        Args:
            output_dir: Directorio donde guardar el documento
            
        Returns:
            Ruta del archivo generado o None si falla
        """
        try:
            from services.document_generator import DocumentGenerator, pruebas_from_course_data
            
            # Obtener CourseData de los enrollments
            courses = []
            for enrollment in self.enrollments:
                if enrollment.course_data:
                    courses.append(enrollment.course_data)
            
            # Convertir a PruebaInfo
            pruebas = pruebas_from_course_data(courses)
            
            # Generar documento
            generator = DocumentGenerator(output_dir=output_dir)
            filepath = generator.generate(
                nombre_candidato=self.full_name,
                email=self.email,
                usuario=self.username,
                contrasena=self.password,
                pruebas=pruebas,
                duracion_dias=self.duration_days,
                es_usuario_nuevo=self.user_created,
                fecha_inicio=self.timestamp
            )
            
            logger.info(f"📄 Documento generado: {filepath}")
            return filepath
            
        except ImportError:
            logger.error("No se pudo importar DocumentGenerator. ¿Está instalado python-docx?")
            return None
        except Exception as e:
            logger.error(f"Error generando documento: {e}")
            return None
    
    def generate_document_base64(self, output_dir: str = ".") -> Optional[tuple]:
        """
        Genera el documento Word y retorna como base64 para envío por API.
        
        Args:
            output_dir: Directorio donde guardar el documento
            
        Returns:
            Tupla (nombre_archivo, contenido_base64) o None si falla
        """
        try:
            from services.document_generator import DocumentGenerator, pruebas_from_course_data
            
            # Obtener CourseData de los enrollments
            courses = []
            for enrollment in self.enrollments:
                if enrollment.course_data:
                    courses.append(enrollment.course_data)
            
            # Convertir a PruebaInfo
            pruebas = pruebas_from_course_data(courses)
            
            # Generar documento
            generator = DocumentGenerator(output_dir=output_dir)
            filename, content_base64 = generator.generate_base64(
                nombre_candidato=self.full_name,
                email=self.email,
                usuario=self.username,
                contrasena=self.password,
                pruebas=pruebas,
                duracion_dias=self.duration_days,
                es_usuario_nuevo=self.user_created,
                fecha_inicio=self.timestamp
            )
            
            logger.info(f"📄 Documento generado (base64): {filename}")
            return filename, content_base64
            
        except ImportError:
            logger.error("No se pudo importar DocumentGenerator. ¿Está instalado python-docx?")
            return None
        except Exception as e:
            logger.error(f"Error generando documento base64: {e}")
            return None
    
    def to_summary(self) -> str:
        """Genera resumen legible."""
        status = "✅" if self.success else "❌"
        user_type = "nuevo" if self.user_created else "existente"
        
        lines = [
            f"{status} {self.message}",
            f"   Usuario: {self.username} ({user_type})",
            f"   Nombre: {self.full_name}",
            f"   Email: {self.email}",
        ]
        
        if self.password:
            lines.append(f"   Contraseña: {self.password}")
        
        lines.append(f"   Duración: {self.duration_text}")
        
        if self.enrollments:
            lines.append(f"   Pruebas matriculadas: {len(self.enrollments)}")
            for e in self.enrollments:
                lines.append(f"      - {e.course_name} ({e.enrollment_status})")
                if e.attempts_deleted > 0:
                    lines.append(f"        Intentos eliminados: {e.attempts_deleted}")
        
        if self.total_attempts_deleted > 0:
            lines.append(f"   Total intentos eliminados: {self.total_attempts_deleted}")
        
        if self.errors:
            lines.append(f"   ⚠️ Errores: {len(self.errors)}")
            for err in self.errors:
                lines.append(f"      - {err}")
        
        return "\n".join(lines)


class CandidateService:
    """
    Servicio para procesar candidatos con flujo completo.
    
    Orquesta: Usuario → (Por cada prueba: Limpieza → Matrícula) → Documento Word → Datos para correo
    
    Las características de las pruebas se leen del cache para optimizar.
    """
    
    def __init__(self, browser: BrowserManager, cache: Optional[CourseCache] = None):
        """
        Inicializa el servicio.
        
        Args:
            browser: Instancia del BrowserManager (debe estar logueado)
            cache: Cache de cursos (opcional, se crea uno si no se pasa)
        """
        self.browser = browser
        self.cache = cache or CourseCache()
        self.user_component = UserComponent(browser)
        self.course_component = CourseComponent(browser, cache=self.cache)
        self.enrollment_component = EnrollmentComponent(browser)
        self.quiz_component = QuizComponent(browser)
    
    def process_candidate(self, candidate: CandidateInput) -> CandidateResult:
        """
        Procesa un candidato con el flujo completo.
        
        Flujo:
        1. Verificar si el usuario existe
           - Si existe: actualizar contraseña y extraer datos
           - Si no existe: crear usuario nuevo
        2. Por cada curso seleccionado (secuencial):
           a. Limpiar intentos anteriores en todos los quizzes
           b. Matricular o reactivar matrícula (actualiza fechas)
        3. Obtener características de las pruebas desde cache
        4. Retornar datos completos para generar correo/documento
        
        Args:
            candidate: Datos del candidato
            
        Returns:
            CandidateResult con el resultado completo
        """
        logger.info(f"Procesando candidato: {candidate.email}")
        
        result = CandidateResult(
            success=False,
            message="",
            email=candidate.email,
            firstname=candidate.firstname,
            lastname=candidate.lastname,
            duration_days=candidate.duration_days,
        )
        
        try:
            # ==================================================
            # PASO 1: Gestión de usuario
            # ==================================================
            logger.info("Paso 1: Verificando/creando usuario...")
            
            # Buscar usuario existente
            search_result = self.user_component.search_by_email(candidate.email)
            
            if search_result and search_result.found:
                # Usuario existe - actualizar contraseña
                logger.info(f"   Usuario encontrado: {search_result.full_name}")
                result.user_existed = True
                result.username = search_result.username
                
                # Extraer nombre y apellido del full_name
                if search_result.full_name:
                    name_parts = search_result.full_name.split()
                    if len(name_parts) >= 2:
                        result.firstname = name_parts[0]
                        result.lastname = " ".join(name_parts[1:])
                    else:
                        result.firstname = search_result.full_name
                        result.lastname = ""
                else:
                    result.firstname = candidate.firstname
                    result.lastname = candidate.lastname
                
                # Actualizar contraseña
                update_result = self.user_component.update_user_password(candidate.email)
                
                if update_result and update_result.success:
                    result.password = update_result.password
                    # Actualizar nombre/apellido desde el resultado si están disponibles
                    if hasattr(update_result, 'firstname') and update_result.firstname:
                        result.firstname = update_result.firstname
                    if hasattr(update_result, 'lastname') and update_result.lastname:
                        result.lastname = update_result.lastname
                    logger.info(f"   Contraseña actualizada: {result.password}")
                else:
                    result.errors.append("No se pudo actualizar la contraseña")
                    logger.warning("   ⚠️ No se pudo actualizar la contraseña")
            else:
                # Usuario no existe - crear nuevo
                logger.info("   Usuario no encontrado, creando nuevo...")
                result.user_created = True
                
                create_result = self.user_component.create_user(
                    email=candidate.email,
                    firstname=candidate.firstname,
                    lastname=candidate.lastname,
                    phone=candidate.phone
                )
                
                if create_result and create_result.success:
                    result.username = create_result.username
                    result.password = create_result.password
                    result.firstname = candidate.firstname
                    result.lastname = candidate.lastname
                    logger.info(f"   Usuario creado: {result.username}")
                else:
                    result.message = "Error al crear usuario"
                    result.errors.append("No se pudo crear el usuario")
                    return result
            
            # ==================================================
            # PASO 2: Procesar cada curso
            # ==================================================
            if not candidate.course_ids:
                result.success = True
                result.message = "Usuario procesado (sin cursos seleccionados)"
                return result
            
            logger.info(f"Paso 2: Procesando {len(candidate.course_ids)} curso(s)...")
            
            enrollment_config = EnrollmentConfig(duration=candidate.get_duration())
            
            for i, course_id in enumerate(candidate.course_ids, 1):
                logger.info(f"   Curso {i}/{len(candidate.course_ids)}: {course_id}")
                
                # Obtener datos del curso desde cache
                course_data = self._get_course_from_cache(course_id)
                course_name = course_data.name if course_data else f"Curso {course_id}"
                course_url = course_data.url_course if course_data else ""
                
                # Crear registro de matrícula
                enrollment_info = EnrollmentInfo(
                    course_id=course_id,
                    course_name=course_name,
                    course_url=course_url,
                    characteristics={},
                    course_data=course_data  # Guardar referencia para el documento
                )
                
                # Extraer características si hay datos de cache
                if course_data:
                    enrollment_info.characteristics = {
                        char.name: char.value for char in course_data.characteristics
                    }
                
                try:
                    # ==================================================
                    # PASO 2a: Limpiar intentos anteriores
                    # ==================================================
                    logger.info(f"      2a. Limpiando intentos anteriores...")
                    
                    attempts_deleted = self._clean_course_attempts(
                        course_id=course_id,
                        email=candidate.email,
                        firstname=result.firstname,
                        lastname=result.lastname
                    )
                    
                    enrollment_info.attempts_deleted = attempts_deleted
                    result.total_attempts_deleted += attempts_deleted
                    
                    if attempts_deleted > 0:
                        logger.info(f"      Intentos eliminados: {attempts_deleted}")
                    else:
                        logger.info(f"      Sin intentos anteriores")
                    
                    # ==================================================
                    # PASO 2b: Matricular o reactivar
                    # ==================================================
                    logger.info(f"      2b. Matriculando/reactivando...")
                    
                    enroll_result = self.enrollment_component.enroll_or_reactivate(
                        course_id=course_id,
                        keyword=candidate.email,
                        config=enrollment_config
                    )
                    
                    if enroll_result.success:
                        enrollment_info.enrollment_status = enroll_result.status
                        logger.info(f"      Estado: {enroll_result.status}")
                    else:
                        enrollment_info.enrollment_status = "error"
                        result.errors.append(f"Error en {course_name}: {enroll_result.message}")
                        logger.warning(f"      ⚠️ Error: {enroll_result.message}")
                    
                except Exception as e:
                    enrollment_info.enrollment_status = "error"
                    result.errors.append(f"Error en {course_name}: {str(e)}")
                    logger.error(f"      ❌ Error procesando curso: {e}")
                
                # Agregar al resultado
                result.enrollments.append(enrollment_info)
            
            # ==================================================
            # RESULTADO FINAL
            # ==================================================
            successful_enrollments = sum(
                1 for e in result.enrollments if e.enrollment_status != "error"
            )
            
            result.success = successful_enrollments > 0
            result.message = (
                f"Procesado: {successful_enrollments}/{len(candidate.course_ids)} "
                f"matrículas exitosas"
            )
            
            if result.errors:
                result.message += f" ({len(result.errors)} errores)"
            
            logger.info(f"✅ {result.message}")
            
        except Exception as e:
            result.success = False
            result.message = f"Error general: {str(e)}"
            result.errors.append(str(e))
            logger.error(f"❌ Error procesando candidato: {e}")
        
        return result
    
    def _get_course_from_cache(self, course_id: str) -> Optional[CourseData]:
        """
        Obtiene un curso del cache.
        
        Args:
            course_id: ID del curso
            
        Returns:
            CourseData o None si no está en cache
        """
        return self.cache.find_by_id(course_id)
    
    def _clean_course_attempts(
        self,
        course_id: str,
        email: str,
        firstname: str,
        lastname: str
    ) -> int:
        """
        Limpia los intentos de un usuario en todos los quizzes de un curso.
        
        Returns:
            Número total de intentos eliminados
        """
        total_deleted = 0
        
        try:
            # Obtener quizzes del curso
            quizzes = self.course_component.get_course_quizzes(course_id)
            
            if not quizzes:
                logger.debug(f"       No hay quizzes en el curso {course_id}")
                return 0
            
            logger.debug(f"       Encontrados {len(quizzes)} quizzes")
            
            # Eliminar intentos en cada quiz
            for quiz in quizzes:
                try:
                    delete_result = self.quiz_component.delete_user_attempts(
                        quiz_id=quiz.quiz_id,
                        user_email=email,
                        user_firstname=firstname,
                        user_lastname=lastname
                    )
                    
                    if delete_result.success:
                        total_deleted += delete_result.attempts_deleted
                        
                except Exception as e:
                    logger.debug(f"       Error eliminando intentos de quiz {quiz.quiz_id}: {e}")
                    continue
            
        except Exception as e:
            logger.warning(f"       Error obteniendo quizzes del curso {course_id}: {e}")
        
        return total_deleted
    
    def process_batch(self, candidates: list[CandidateInput]) -> list[CandidateResult]:
        """
        Procesa múltiples candidatos.
        
        Args:
            candidates: Lista de candidatos a procesar
            
        Returns:
            Lista de resultados
        """
        logger.info(f"Procesando lote de {len(candidates)} candidatos...")
        
        results = []
        
        for i, candidate in enumerate(candidates, 1):
            logger.info(f"Candidato {i}/{len(candidates)}: {candidate.email}")
            result = self.process_candidate(candidate)
            results.append(result)
        
        # Resumen
        successful = sum(1 for r in results if r.success)
        total_enrollments = sum(len(r.enrollments) for r in results)
        total_attempts = sum(r.total_attempts_deleted for r in results)
        
        logger.info(f"Lote completado: {successful}/{len(candidates)} exitosos")
        logger.info(f"  Total matrículas: {total_enrollments}")
        logger.info(f"  Total intentos eliminados: {total_attempts}")
        
        return results