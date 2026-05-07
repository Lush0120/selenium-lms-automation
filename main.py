#!/usr/bin/env python3
"""
main.py
Punto de entrada principal del Gestor Q-Vision.

VERSIÓN 5.0:
- NUEVO: Procesar solicitudes desde Excel (modo batch)
- NUEVO: Generar/actualizar plantilla Excel
- NUEVO: Sincronización actualiza automáticamente el Excel
- Loop para procesar múltiples candidatos sin cerrar sesión
- Generación de documento Word

Uso:
    python main.py
"""

import sys
import os
import getpass
from datetime import datetime
from typing import Optional, List

# Asegurar que el directorio raíz está en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ruta por defecto de la plantilla Excel
DEFAULT_EXCEL_PATH = "./plantilla_solicitudes.xlsx"


# ==================== Utilidades de impresión ====================

def print_header(text: str) -> None:
    """Imprime un encabezado formateado."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_step(step: int, text: str) -> None:
    """Imprime un paso del flujo."""
    print(f"\n[Paso {step}] {text}")
    print("-" * 40)


def print_success(text: str) -> None:
    print(f"✅ {text}")


def print_error(text: str) -> None:
    print(f"❌ {text}")


def print_info(text: str) -> None:
    print(f"ℹ️  {text}")


def print_warning(text: str) -> None:
    print(f"⚠️  {text}")


def input_required(prompt: str) -> str:
    """Solicita input requerido (no puede estar vacío)."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print_error("Este campo es requerido")


def input_optional(prompt: str, default: str = "") -> str:
    """Solicita input opcional con valor por defecto."""
    value = input(prompt).strip()
    return value if value else default


# ==================== Verificaciones ====================

def check_imports() -> bool:
    """Verifica que todos los imports funcionen."""
    print_info("Verificando módulos...")
    
    try:
        from core.browser import BrowserManager
        from core.config import settings
        from components.auth import AuthComponent
        from components.user import UserComponent
        from components.course import CourseComponent
        from components.enrollment import EnrollmentComponent
        from components.quiz import QuizComponent
        from models.user import UserData
        from models.enrollment import EnrollmentConfig, EnrollmentDuration
        from services.course_cache import CourseCache
        print_success("Todos los módulos cargados correctamente")
        return True
    except ImportError as e:
        print_error(f"Error de importación: {e}")
        print_info("Asegúrate de ejecutar desde la carpeta del proyecto")
        return False


def check_cache() -> bool:
    """Verifica que el cache de cursos tenga datos."""
    from services.course_cache import CourseCache
    
    cache = CourseCache()
    
    if cache.is_empty:
        print_warning("El cache de cursos está vacío")
        return False
    
    print_success(f"Cache OK: {cache.total_courses} cursos disponibles")
    return True


# ==================== Procesamiento de un Candidato ====================

def procesar_candidato(
    browser,
    cache,
    user_comp,
    enrollment_comp,
    quiz_comp,
    course_comp
) -> bool:
    """
    Procesa un solo candidato (sin login/logout).
    
    Returns:
        True si se procesó correctamente, False si hubo error
    """
    from models.user import UserData
    from models.enrollment import EnrollmentConfig, EnrollmentDuration
    
    # ==================== Datos del candidato ====================
    print_header("NUEVO CANDIDATO")
    
    candidate_email = input_required("Email del candidato: ").lower()
    
    # ==================== Buscar usuario ====================
    print_info("Verificando si el usuario existe...")
    
    search_result = user_comp.search_by_email(candidate_email)
    
    # Variables para almacenar datos del usuario
    username = ""
    password = ""
    firstname = ""
    lastname = ""
    user_created = False
    
    if search_result.found:
        # ==================== Usuario existe ====================
        print_success(f"Usuario encontrado: {search_result.full_name}")
        print_info(f"  ID: {search_result.user_id}")
        print_info(f"  Email: {search_result.email}")
        
        # Actualizar contraseña
        print_info("Actualizando contraseña...")
        update_result = user_comp.update_user_password(
            candidate_email, 
            search_result=search_result
        )
        
        if update_result and update_result.success:
            username = update_result.username
            password = update_result.password
            firstname = update_result.firstname
            lastname = update_result.lastname
            print_success(f"Contraseña actualizada")
            print_info(f"  Usuario: {username}")
            print_info(f"  Nueva contraseña: {password}")
        else:
            print_error("No se pudo actualizar la contraseña")
            return False
    else:
        # ==================== Usuario no existe - Crear ====================
        print_warning("Usuario no encontrado, se creará uno nuevo")
        print_info("\nIngresa los datos del nuevo usuario:")
        
        firstname = input_required("Primer nombre: ")
        segundo_nombre = input_optional("Segundo nombre (opcional): ")
        lastname = input_required("Primer apellido: ")
        segundo_apellido = input_optional("Segundo apellido (opcional): ")
        phone = input_required("Teléfono: ")
        city = input_optional("Ciudad [Medellín]: ", "Medellín")
        
        # Crear objeto UserData
        new_user = UserData(
            primer_nombre=firstname,
            segundo_nombre=segundo_nombre if segundo_nombre else None,
            primer_apellido=lastname,
            segundo_apellido=segundo_apellido if segundo_apellido else None,
            correo=candidate_email,
            telefono=phone,
            ciudad=city
        )
        
        print_info(f"\nUsername generado: {new_user.username}")
        print_info(f"Contraseña generada: {new_user.password}")
        
        confirm = input("\n¿Crear usuario con estos datos? (s/n) [s]: ").strip().lower()
        if confirm == 'n':
            print_warning("Operación cancelada")
            return False
        
        # Crear usuario
        print_info("Creando usuario...")
        try:
            created = user_comp.create_user(new_user, verify_email=False)
            if created:
                username = created.username
                password = created.password
                firstname = created.nombres
                lastname = created.apellidos
                user_created = True
                print_success(f"Usuario creado: {username}")
            else:
                print_error("No se pudo crear el usuario")
                return False
        except Exception as e:
            print_error(f"Error creando usuario: {e}")
            return False
    
    # ==================== Tiempo de habilitación ====================
    print("\n⏱️  DURACIÓN DE HABILITACIÓN:")
    print("  1. 1 día (24 horas)")
    print("  2. 2 días (48 horas)")
    print("  3. 3 días (72 horas)")
    
    while True:
        duration_input = input("\nSelecciona duración (1-3) [1]: ").strip()
        if duration_input == "" or duration_input == "1":
            duration_days = 1
            duration = EnrollmentDuration.UN_DIA
            break
        elif duration_input == "2":
            duration_days = 2
            duration = EnrollmentDuration.DOS_DIAS
            break
        elif duration_input == "3":
            duration_days = 3
            duration = EnrollmentDuration.TRES_DIAS
            break
        else:
            print_error("Opción no válida")
    
    print_success(f"Duración seleccionada: {duration_days} día(s)")
    
    # ==================== Seleccionar pruebas ====================
    print("\n📚 SELECCIÓN DE PRUEBAS:")
    
    # Separar por categoría
    diagnosticas = cache.get_diagnosticas()
    tecnicas = cache.get_tecnicas()
    
    print(f"\n🔬 PRUEBAS DIAGNÓSTICAS ({len(diagnosticas)}):")
    for i, course in enumerate(diagnosticas, 1):
        print(f"  [{i:2}] {course.name}")
    
    print(f"\n🔧 PRUEBAS TÉCNICAS ({len(tecnicas)}):")
    for i, course in enumerate(tecnicas, len(diagnosticas) + 1):
        print(f"  [{i:2}] {course.name}")
    
    all_courses = diagnosticas + tecnicas
    
    print("\n" + "-" * 50)
    print("Ingresa los números separados por coma (ej: 1,3,5)")
    print("O 'todas' para seleccionar todas")
    print("-" * 50)
    
    while True:
        selection = input("\nPruebas a asignar: ").strip().lower()
        
        if selection == 'todas':
            selected_courses = all_courses
            break
        
        try:
            indices = [int(x.strip()) for x in selection.split(",")]
            selected_courses = []
            
            for idx in indices:
                if 1 <= idx <= len(all_courses):
                    selected_courses.append(all_courses[idx - 1])
                    print_info(f"  Seleccionado: {all_courses[idx - 1].name}")
                else:
                    print_warning(f"Índice {idx} fuera de rango")
            
            if selected_courses:
                break
            else:
                print_error("No se seleccionó ninguna prueba válida")
        except ValueError:
            print_error("Formato inválido. Usa números separados por coma")
    
    print_success(f"\nPruebas seleccionadas: {len(selected_courses)}")
    
    confirm = input("\n¿Continuar con la asignación? (s/n) [s]: ").strip().lower()
    if confirm == 'n':
        print_warning("Operación cancelada")
        return False
    
    # ==================== Procesar cada prueba ====================
    print_header("ASIGNANDO PRUEBAS")
    
    from models.enrollment import EnrollmentConfig
    
    results = []
    total_attempts_deleted = 0
    
    for i, course in enumerate(selected_courses, 1):
        print(f"\n--- Prueba {i}/{len(selected_courses)}: {course.name} ---")
        
        # Limpiar intentos anteriores
        print_info("Limpiando intentos anteriores...")
        
        try:
            quizzes = course_comp.get_course_quizzes(course.course_id)
            attempts_deleted = 0
            
            for quiz in quizzes:
                result = quiz_comp.delete_user_attempts(
                    quiz_id=quiz.quiz_id,
                    user_email=candidate_email,
                    user_firstname=firstname.split()[0] if firstname else "",
                    user_lastname=lastname.split()[0] if lastname else ""
                )
                attempts_deleted += result.attempts_deleted
            
            total_attempts_deleted += attempts_deleted
            
            if attempts_deleted > 0:
                print_info(f"  Intentos eliminados: {attempts_deleted}")
            else:
                print_info("  No había intentos previos")
                
        except Exception as e:
            print_warning(f"  Error limpiando intentos: {e}")
            attempts_deleted = 0
        
        # Matricular o reactivar
        print_info("Matriculando usuario...")
        
        try:
            config = EnrollmentConfig(duration=duration)
            enroll_result = enrollment_comp.enroll_user(
                course_id=course.course_id,
                user_email=candidate_email,
                config=config
            )
            
            if enroll_result.success:
                action_text = {
                    "created": "Nueva matrícula creada",
                    "updated": "Matrícula reactivada",
                    "already_active": "Ya estaba activo"
                }.get(enroll_result.action, enroll_result.action)
                
                print_success(f"  {action_text}")
                
                results.append({
                    "course": course,
                    "success": True,
                    "action": enroll_result.action,
                    "attempts_deleted": attempts_deleted,
                })
            else:
                print_error(f"  Error: {enroll_result.message}")
                results.append({
                    "course": course,
                    "success": False,
                    "error": enroll_result.message
                })
                
        except Exception as e:
            print_error(f"  Error en matrícula: {e}")
            results.append({
                "course": course,
                "success": False,
                "error": str(e)
            })
    
    # ==================== Resumen ====================
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    
    print(f"\n{'='*60}")
    print("  DATOS PARA EL CORREO")
    print(f"{'='*60}")
    
    print(f"\n👤 CANDIDATO:")
    print(f"   Nombre completo: {firstname} {lastname}")
    print(f"   Email: {candidate_email}")
    print(f"   Usuario: {username}")
    print(f"   Contraseña: {password}")
    print(f"   Estado: {'Nuevo usuario' if user_created else 'Usuario existente'}")
    
    print(f"\n⏱️  TIEMPO DE HABILITACIÓN:")
    print(f"   Duración: {duration_days} día(s) ({duration_days * 24} horas)")
    
    print(f"\n📚 PRUEBAS ASIGNADAS ({len(successful)}/{len(results)}):")
    
    for r in successful:
        course = r["course"]
        print(f"\n   ✅ {course.name}")
        print(f"      URL: {course.url_course}")
        print(f"      Estado: {r['action']}")
        
        if r.get("attempts_deleted", 0) > 0:
            print(f"      Intentos eliminados: {r['attempts_deleted']}")
    
    if failed:
        print(f"\n❌ PRUEBAS CON ERROR ({len(failed)}):")
        for r in failed:
            print(f"   - {r['course'].name}: {r.get('error', 'Error desconocido')}")
    
    print(f"\n📊 RESUMEN:")
    print(f"   Total pruebas procesadas: {len(results)}")
    print(f"   Exitosas: {len(successful)}")
    print(f"   Fallidas: {len(failed)}")
    print(f"   Intentos eliminados: {total_attempts_deleted}")
    
    print(f"\n{'='*60}")
    
    # ==================== Generar documento Word ====================
    if successful:
        print_info("\nGenerando documento Word...")
        
        try:
            from services.document_generator import DocumentGenerator, PruebaInfo
            
            pruebas = []
            for r in successful:
                course = r["course"]
                
                # Extraer niveles de las características
                niveles = []
                duracion_prueba = "N/A"
                lenguaje = "Español"
                monitorizacion = "N/A"
                
                for char in course.characteristics:
                    name_lower = char.name.lower()
                    
                    if name_lower.startswith("nivel") and "pregunta" in char.value.lower():
                        nivel_nombre = char.name.replace("Nivel", "").replace("nivel", "").strip()
                        niveles.append({"nivel": nivel_nombre or "General", "tiempo": ""})
                    elif name_lower == "nivel de la prueba":
                        niveles.append({"nivel": char.value, "tiempo": ""})
                    
                    if any(kw in name_lower for kw in ["duración", "duracion", "disponibilidad"]):
                        duracion_prueba = char.value
                    
                    if name_lower in ["idioma", "lenguaje"]:
                        lenguaje = char.value
                    
                    if any(kw in name_lower for kw in ["monitorización", "monitorizado", "supervisión"]):
                        monitorizacion = char.value
                
                if not niveles:
                    niveles = [{"nivel": "General", "tiempo": duracion_prueba}]
                else:
                    for nivel in niveles:
                        nivel["tiempo"] = duracion_prueba
                
                pruebas.append(PruebaInfo(
                    nombre=course.name,
                    url=course.url_course,
                    niveles=niveles,
                    lenguaje=lenguaje,
                    monitorizacion=monitorizacion
                ))
            
            os.makedirs("output", exist_ok=True)
            
            generator = DocumentGenerator(output_dir="./output")
            doc_path = generator.generate(
                nombre_candidato=f"{firstname} {lastname}",
                email=candidate_email,
                usuario=username,
                contrasena=password,
                pruebas=pruebas,
                duracion_dias=duration_days,
                es_usuario_nuevo=user_created
            )
            
            print_success(f"Documento generado: {doc_path}")
            
            abrir = input("\n¿Abrir el documento? (s/n) [s]: ").strip().lower()
            if abrir != 'n':
                try:
                    os.startfile(doc_path)
                except Exception:
                    print_info(f"Abre manualmente: {doc_path}")
                    
        except ImportError:
            print_warning("No se pudo generar documento (falta python-docx)")
        except Exception as e:
            print_warning(f"Error generando documento: {e}")
    
    return len(failed) == 0


# ==================== Procesar Solicitud desde Excel ====================

def procesar_solicitud_excel(
    solicitud,
    browser,
    cache,
    user_comp,
    enrollment_comp,
    quiz_comp,
    course_comp,
    excel_reader
) -> dict:
    """
    Procesa una solicitud individual desde el Excel.
    
    Args:
        solicitud: SolicitudPrueba del Excel
        browser, cache, etc.: Componentes ya inicializados
        excel_reader: Para actualizar el estado
        
    Returns:
        dict con resultados del procesamiento
    """
    from models.user import UserData
    from models.enrollment import EnrollmentConfig, EnrollmentDuration
    
    print(f"\n{'='*60}")
    print(f"  Procesando: {solicitud.identificador}")
    print(f"  Candidato: {solicitud.nombres} {solicitud.apellidos}")
    print(f"  Email: {solicitud.email}")
    print(f"  Pruebas: {len(solicitud.pruebas)}")
    print(f"{'='*60}")
    
    # Actualizar estado a "Procesando"
    excel_reader.update_request_status(
        solicitud.row_number,
        estado="Procesando",
        observaciones="Iniciando procesamiento..."
    )
    
    resultado = {
        "codigo": solicitud.identificador,
        "email": solicitud.email,
        "success": False,
        "username": "",
        "password": "",
        "pruebas_exitosas": [],
        "pruebas_fallidas": [],
        "documento": "",
        "error": ""
    }
    
    try:
        # ==================== Buscar/Crear Usuario ====================
        print_info("Verificando usuario...")
        search_result = user_comp.search_by_email(solicitud.email)
        
        user_created = False
        
        if search_result.found:
            print_success(f"Usuario encontrado: {search_result.full_name}")
            
            # Actualizar contraseña
            update_result = user_comp.update_user_password(
                solicitud.email,
                search_result=search_result
            )
            
            if update_result and update_result.success:
                resultado["username"] = update_result.username
                resultado["password"] = update_result.password
                firstname = update_result.firstname
                lastname = update_result.lastname
            else:
                raise Exception("No se pudo actualizar la contraseña")
        else:
            print_info("Usuario no existe, creando...")
            
            # Separar nombres y apellidos
            nombres_parts = solicitud.nombres.split()
            apellidos_parts = solicitud.apellidos.split()
            
            new_user = UserData(
                primer_nombre=nombres_parts[0] if nombres_parts else solicitud.nombres,
                segundo_nombre=nombres_parts[1] if len(nombres_parts) > 1 else None,
                primer_apellido=apellidos_parts[0] if apellidos_parts else solicitud.apellidos,
                segundo_apellido=apellidos_parts[1] if len(apellidos_parts) > 1 else None,
                correo=solicitud.email,
                telefono=solicitud.telefono or "0000000000",
                ciudad=solicitud.ciudad or "Medellín"
            )
            
            created = user_comp.create_user(new_user, verify_email=False)
            if created:
                resultado["username"] = created.username
                resultado["password"] = created.password
                firstname = created.nombres
                lastname = created.apellidos
                user_created = True
                print_success(f"Usuario creado: {created.username}")
            else:
                raise Exception("No se pudo crear el usuario")
        
        # ==================== Configurar Duración ====================
        duration_map = {
            1: EnrollmentDuration.UN_DIA,
            2: EnrollmentDuration.DOS_DIAS,
            3: EnrollmentDuration.TRES_DIAS
        }
        duration = duration_map.get(solicitud.duracion_dias, EnrollmentDuration.UN_DIA)
        
        # ==================== Procesar Pruebas ====================
        total_attempts_deleted = 0
        
        for course in solicitud.pruebas:
            print(f"\n--- {course.name} ---")
            
            try:
                # Limpiar intentos
                quizzes = course_comp.get_course_quizzes(course.course_id)
                attempts_deleted = 0
                
                for quiz in quizzes:
                    result = quiz_comp.delete_user_attempts(
                        quiz_id=quiz.quiz_id,
                        user_email=solicitud.email,
                        user_firstname=firstname.split()[0] if firstname else "",
                        user_lastname=lastname.split()[0] if lastname else ""
                    )
                    attempts_deleted += result.attempts_deleted
                
                total_attempts_deleted += attempts_deleted
                
                # Matricular
                config = EnrollmentConfig(duration=duration)
                enroll_result = enrollment_comp.enroll_user(
                    course_id=course.course_id,
                    user_email=solicitud.email,
                    config=config
                )
                
                if enroll_result.success:
                    print_success(f"Matrícula exitosa")
                    resultado["pruebas_exitosas"].append(course.name)
                else:
                    print_error(f"Error: {enroll_result.message}")
                    resultado["pruebas_fallidas"].append(f"{course.name}: {enroll_result.message}")
                    
            except Exception as e:
                print_error(f"Error: {e}")
                resultado["pruebas_fallidas"].append(f"{course.name}: {str(e)}")
        
        # ==================== Generar Documento ====================
        if resultado["pruebas_exitosas"]:
            try:
                from services.document_generator import DocumentGenerator, PruebaInfo
                
                pruebas_info = []
                for course in solicitud.pruebas:
                    if course.name in resultado["pruebas_exitosas"]:
                        # Usar get_table_data() del modelo
                        table_data = course.get_table_data()
                        pruebas_info.append(PruebaInfo(
                            nombre=table_data.nombre,
                            url=table_data.url,
                            niveles=table_data.niveles,
                            lenguaje=table_data.lenguaje,
                            monitorizacion=table_data.monitorizacion
                        ))
                
                os.makedirs("output", exist_ok=True)
                generator = DocumentGenerator(output_dir="./output")
                doc_path = generator.generate(
                    nombre_candidato=f"{firstname} {lastname}",
                    email=solicitud.email,
                    usuario=resultado["username"],
                    contrasena=resultado["password"],
                    pruebas=pruebas_info,
                    duracion_dias=solicitud.duracion_dias,
                    es_usuario_nuevo=user_created
                )
                resultado["documento"] = doc_path
                print_success(f"Documento: {doc_path}")
                
            except Exception as e:
                print_warning(f"Error generando documento: {e}")
        
        # ==================== Determinar Estado Final ====================
        if not resultado["pruebas_fallidas"]:
            resultado["success"] = True
            estado_final = "Completado"
            observaciones = f"Exitoso. Usuario: {resultado['username']}"
        elif resultado["pruebas_exitosas"]:
            resultado["success"] = True  # Parcialmente exitoso
            estado_final = "Completado"
            observaciones = f"Parcial. Exitosas: {len(resultado['pruebas_exitosas'])}, Fallidas: {len(resultado['pruebas_fallidas'])}"
        else:
            estado_final = "Error"
            observaciones = f"Falló. {resultado['pruebas_fallidas'][0] if resultado['pruebas_fallidas'] else 'Error desconocido'}"
        
        # Actualizar Excel
        excel_reader.update_request_status(
            solicitud.row_number,
            estado=estado_final,
            observaciones=observaciones
        )
        
        # Agregar a hoja de procesados
        excel_reader.add_to_processed(
            solicitud=solicitud,
            usuario_moodle=resultado["username"],
            password=resultado["password"],
            pruebas_asignadas=resultado["pruebas_exitosas"],
            documento=resultado["documento"],
            estado=estado_final
        )
        
    except Exception as e:
        resultado["error"] = str(e)
        print_error(f"Error general: {e}")
        
        excel_reader.update_request_status(
            solicitud.row_number,
            estado="Error",
            observaciones=str(e)[:100]
        )
    
    return resultado


# ==================== Flujo de Procesamiento por Lotes ====================

def flujo_procesar_excel():
    """
    Procesa solicitudes desde archivo Excel.
    
    Lee el Excel, procesa cada solicitud pendiente y actualiza el estado.
    """
    from core.browser import BrowserManager
    from core.config import settings
    from components.auth import AuthComponent
    from components.user import UserComponent
    from components.course import CourseComponent
    from components.enrollment import EnrollmentComponent
    from components.quiz import QuizComponent
    from services.course_cache import CourseCache
    from services.excel_reader import ExcelReader
    
    print_header("PROCESAR SOLICITUDES DESDE EXCEL")
    
    # ==================== Verificar archivo Excel ====================
    excel_path = input(f"Ruta del archivo Excel [{DEFAULT_EXCEL_PATH}]: ").strip()
    if not excel_path:
        excel_path = DEFAULT_EXCEL_PATH
    
    if not os.path.exists(excel_path):
        print_error(f"Archivo no encontrado: {excel_path}")
        print_info("Usa la opción 6 para generar una plantilla nueva")
        return False
    
    # ==================== Cargar solicitudes ====================
    cache = CourseCache()
    
    if cache.is_empty:
        print_error("El cache de cursos está vacío")
        print_info("Usa la opción 2 para sincronizar el catálogo primero")
        return False
    
    excel_reader = ExcelReader(excel_path, cache)
    solicitudes = excel_reader.get_pending_requests()
    
    if not solicitudes:
        print_warning("No hay solicitudes pendientes en el Excel")
        return False
    
    print_success(f"Encontradas {len(solicitudes)} solicitudes pendientes")
    
    # Mostrar resumen detallado con validación
    print("\n" + "=" * 70)
    print("  📋 SOLICITUDES A PROCESAR - RESUMEN DETALLADO")
    print("=" * 70)
    
    solicitudes_validas = []
    solicitudes_con_errores = []
    
    for i, sol in enumerate(solicitudes, 1):
        errores = []
        
        # Verificar IDs de pruebas
        ids_invalidos = []
        for pid in sol.pruebas_ids:
            if not cache.find_by_id(pid):
                ids_invalidos.append(pid)
        
        if ids_invalidos:
            errores.append(f"IDs no existen: {', '.join(ids_invalidos)}")
        
        if not sol.pruebas:
            errores.append("Sin pruebas válidas")
        
        if not sol.generalista_email and sol.generalista_nombre:
            errores.append(f"Generalista '{sol.generalista_nombre}' no encontrada")
        
        # Mostrar info (usar identificador que puede ser código o email)
        print(f"\n  {i}. [{sol.identificador}] {sol.nombre_completo}")
        print(f"     📧 Email: {sol.email}")
        print(f"     ⏱️  Días: {sol.duracion_dias}")
        print(f"     👤 Generalista: {sol.generalista_nombre or 'No asignada'}")
        
        # Mostrar pruebas
        if sol.pruebas:
            print(f"     📚 Pruebas ({len(sol.pruebas)}):")
            for p in sol.pruebas:
                print(f"        ✓ [{p.course_id}] {p.name}")
        
        # Mostrar IDs inválidos
        if ids_invalidos:
            print(f"     ⚠️  IDs no encontrados: {', '.join(ids_invalidos)}")
        
        # Clasificar
        if errores:
            solicitudes_con_errores.append((sol, errores))
            print(f"     ❌ ERRORES: {'; '.join(errores)}")
        else:
            solicitudes_validas.append(sol)
    
    print("\n" + "=" * 70)
    print(f"  📊 RESUMEN: {len(solicitudes_validas)} válidas, {len(solicitudes_con_errores)} con errores")
    print("=" * 70)
    
    # Si hay errores, preguntar qué hacer
    if solicitudes_con_errores:
        print_warning(f"\n{len(solicitudes_con_errores)} solicitud(es) tienen errores")
        print("Opciones:")
        print("  1. Procesar solo las válidas")
        print("  2. Cancelar y corregir el Excel")
        
        opcion = input("\nSelecciona (1-2) [2]: ").strip()
        
        if opcion != "1":
            print_warning("Operación cancelada. Corrige los errores en el Excel.")
            return False
        
        if not solicitudes_validas:
            print_error("No hay solicitudes válidas para procesar")
            return False
        
        # Usar solo las válidas
        solicitudes = solicitudes_validas
        print_info(f"Procesando solo {len(solicitudes)} solicitudes válidas")
    
    confirm = input(f"\n¿Procesar {len(solicitudes)} solicitudes? (s/n) [s]: ").strip().lower()
    if confirm == 'n':
        print_warning("Operación cancelada")
        return False
    
    # ==================== Credenciales ====================
    print_step(1, "Credenciales de Moodle")
    
    if settings.moodle_username and settings.moodle_password:
        print_info(f"Usuario encontrado en .env: {settings.moodle_username}")
        use_env = input("¿Usar estas credenciales? (s/n) [s]: ").strip().lower()
        
        if use_env != 'n':
            moodle_user = settings.moodle_username
            moodle_pass = settings.moodle_password
        else:
            moodle_user = input_required("Usuario de Moodle: ")
            moodle_pass = getpass.getpass("Contraseña de Moodle: ")
    else:
        moodle_user = input_required("Usuario de Moodle: ")
        moodle_pass = getpass.getpass("Contraseña de Moodle: ")
    
    if not moodle_pass:
        print_error("Contraseña requerida")
        return False
    
    # ==================== Login ====================
    print_step(2, "Iniciando sesión en Moodle")
    
    headless_input = input("¿Ejecutar en modo headless (sin ventana)? (s/n) [n]: ").strip().lower()
    headless = headless_input == 's'
    
    try:
        browser = BrowserManager(headless=headless)
        browser.start()
        
        auth = AuthComponent(browser)
        auth.login(username=moodle_user, password=moodle_pass)
        print_success("Login exitoso")
        
    except Exception as e:
        print_error(f"Error en login: {e}")
        if 'browser' in locals():
            browser.quit()
        return False
    
    try:
        # Inicializar componentes
        user_comp = UserComponent(browser)
        enrollment_comp = EnrollmentComponent(browser)
        quiz_comp = QuizComponent(browser)
        course_comp = CourseComponent(browser, cache=cache)
        
        # ==================== Procesar cada solicitud ====================
        print_header(f"PROCESANDO {len(solicitudes)} SOLICITUDES")
        
        resultados = []
        
        for i, solicitud in enumerate(solicitudes, 1):
            print(f"\n{'#'*60}")
            print(f"  SOLICITUD {i}/{len(solicitudes)}")
            print(f"{'#'*60}")
            
            resultado = procesar_solicitud_excel(
                solicitud=solicitud,
                browser=browser,
                cache=cache,
                user_comp=user_comp,
                enrollment_comp=enrollment_comp,
                quiz_comp=quiz_comp,
                course_comp=course_comp,
                excel_reader=excel_reader
            )
            resultados.append(resultado)
        
        # ==================== Resumen Final ====================
        browser.quit()
        
        exitosos = [r for r in resultados if r["success"]]
        fallidos = [r for r in resultados if not r["success"]]
        
        print(f"\n{'='*60}")
        print("  RESUMEN FINAL DEL PROCESAMIENTO")
        print(f"{'='*60}")
        print(f"\n📊 ESTADÍSTICAS:")
        print(f"   Total procesadas: {len(resultados)}")
        print(f"   Exitosas: {len(exitosos)}")
        print(f"   Fallidas: {len(fallidos)}")
        
        if exitosos:
            print(f"\n✅ EXITOSAS ({len(exitosos)}):")
            for r in exitosos:
                print(f"   - {r['codigo']}: {r['email']} → {r['username']}")
        
        if fallidos:
            print(f"\n❌ FALLIDAS ({len(fallidos)}):")
            for r in fallidos:
                print(f"   - {r['codigo']}: {r['email']}")
                print(f"     Error: {r.get('error', 'Ver Excel para detalles')}")
        
        print(f"\n📁 Resultados guardados en: {excel_path}")
        print(f"   Revisa la hoja 'Procesados' para ver los detalles")
        
        return True
        
    except Exception as e:
        print_error(f"Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        
        if 'browser' in locals():
            browser.quit()
        
        return False


# ==================== Flujo Principal de Asignación (Manual) ====================

def flujo_asignar_pruebas():
    """
    Ejecuta el flujo de asignación de pruebas manual.
    
    Permite procesar múltiples candidatos sin cerrar sesión.
    """
    from core.browser import BrowserManager
    from core.config import settings
    from components.auth import AuthComponent
    from components.user import UserComponent
    from components.course import CourseComponent
    from components.enrollment import EnrollmentComponent
    from components.quiz import QuizComponent
    from services.course_cache import CourseCache
    
    print_header("ASIGNACIÓN DE PRUEBAS (MANUAL)")
    
    # ==================== Credenciales ====================
    print_step(1, "Credenciales de Moodle")
    
    if settings.moodle_username and settings.moodle_password:
        print_info(f"Usuario encontrado en .env: {settings.moodle_username}")
        use_env = input("¿Usar estas credenciales? (s/n) [s]: ").strip().lower()
        
        if use_env != 'n':
            moodle_user = settings.moodle_username
            moodle_pass = settings.moodle_password
        else:
            moodle_user = input_required("Usuario de Moodle: ")
            moodle_pass = getpass.getpass("Contraseña de Moodle: ")
    else:
        moodle_user = input_required("Usuario de Moodle: ")
        moodle_pass = getpass.getpass("Contraseña de Moodle: ")
    
    if not moodle_pass:
        print_error("Contraseña requerida")
        return False
    
    # ==================== Login ====================
    print_step(2, "Iniciando sesión en Moodle")
    
    headless_input = input("¿Ejecutar en modo headless (sin ventana)? (s/n) [n]: ").strip().lower()
    headless = headless_input == 's'
    
    try:
        browser = BrowserManager(headless=headless)
        browser.start()
        
        auth = AuthComponent(browser)
        auth.login(username=moodle_user, password=moodle_pass)
        print_success("Login exitoso")
        
    except Exception as e:
        print_error(f"Error en login: {e}")
        if 'browser' in locals():
            browser.take_screenshot("login_error")
            browser.quit()
        return False
    
    try:
        # Cargar cache
        cache = CourseCache()
        
        # Sincronizar si está vacío
        if cache.is_empty:
            print_warning("Cache vacío, sincronizando catálogo...")
            course_comp_sync = CourseComponent(browser, cache=cache)
            course_comp_sync.sync_catalog()
            print_success(f"Catálogo sincronizado: {cache.total_courses} cursos")
        
        # Inicializar componentes
        user_comp = UserComponent(browser)
        enrollment_comp = EnrollmentComponent(browser)
        quiz_comp = QuizComponent(browser)
        course_comp = CourseComponent(browser, cache=cache)
        
        # ==================== LOOP DE CANDIDATOS ====================
        while True:
            # Procesar un candidato
            procesar_candidato(
                browser=browser,
                cache=cache,
                user_comp=user_comp,
                enrollment_comp=enrollment_comp,
                quiz_comp=quiz_comp,
                course_comp=course_comp
            )
            
            # Preguntar si desea continuar con otro candidato
            print("\n" + "=" * 60)
            continuar = input("¿Asignar pruebas a otro candidato? (s/n) [n]: ").strip().lower()
            
            if continuar != 's':
                break
        
        # Cerrar navegador al salir del loop
        browser.quit()
        print_success("\nSesión cerrada correctamente")
        
        return True
        
    except Exception as e:
        print_error(f"Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        
        if 'browser' in locals():
            browser.take_screenshot("error_unexpected")
            browser.quit()
        
        return False


# ==================== Flujo de Sincronización ====================

def flujo_sincronizar_catalogo():
    """
    Sincroniza el catálogo de cursos desde Moodle.
    
    ACTUALIZADO v5.0: También actualiza la plantilla Excel automáticamente.
    """
    from core.browser import BrowserManager
    from core.config import settings
    from components.auth import AuthComponent
    from components.course import CourseComponent
    from services.course_cache import CourseCache
    from models.course import CourseCategory
    
    print_header("SINCRONIZAR CATÁLOGO DE CURSOS")
    
    print("Selecciona qué sincronizar:")
    print("  1. Todo (Diagnósticas + Técnicas)")
    print("  2. Solo Pruebas Diagnósticas")
    print("  3. Solo Pruebas Técnicas")
    
    opcion = input("\nSelecciona (1-3) [1]: ").strip()
    
    if opcion == "2":
        categories = [CourseCategory.PRUEBAS_DIAGNOSTICAS]
        cat_name = "Pruebas Diagnósticas"
    elif opcion == "3":
        categories = [CourseCategory.PRUEBAS_TECNICAS]
        cat_name = "Pruebas Técnicas"
    else:
        categories = None
        cat_name = "Todas las categorías"
    
    # Credenciales
    if settings.moodle_username and settings.moodle_password:
        print_info(f"Usuario: {settings.moodle_username}")
        use_env = input("¿Usar estas credenciales? (s/n) [s]: ").strip().lower()
        
        if use_env != 'n':
            moodle_user = settings.moodle_username
            moodle_pass = settings.moodle_password
        else:
            moodle_user = input_required("Usuario de Moodle: ")
            moodle_pass = getpass.getpass("Contraseña de Moodle: ")
    else:
        moodle_user = input_required("Usuario de Moodle: ")
        moodle_pass = getpass.getpass("Contraseña de Moodle: ")
    
    print_info(f"\nSincronizando: {cat_name}")
    print_info("Esto puede tardar unos minutos...")
    
    try:
        browser = BrowserManager(headless=False)
        browser.start()
        
        # Login
        auth = AuthComponent(browser)
        auth.login(username=moodle_user, password=moodle_pass)
        print_success("Login exitoso")
        
        # Sincronizar
        cache = CourseCache()
        course_comp = CourseComponent(browser, cache=cache)
        catalog = course_comp.sync_catalog(categories=categories)
        
        print_success("Sincronización completada")
        print(f"\n{cache.summary()}")
        
        browser.quit()
        
        # ==================== NUEVO v5.0: Actualizar Excel ====================
        try:
            from utils.excel_template import ExcelTemplateGenerator
            
            print_info("\nActualizando plantilla Excel...")
            generator = ExcelTemplateGenerator(cache)
            
            if os.path.exists(DEFAULT_EXCEL_PATH):
                generator.update_catalog(DEFAULT_EXCEL_PATH)
                print_success(f"Plantilla actualizada: {DEFAULT_EXCEL_PATH}")
            else:
                generator.create_template(DEFAULT_EXCEL_PATH)
                print_success(f"Plantilla creada: {DEFAULT_EXCEL_PATH}")
                
        except ImportError:
            print_warning("No se pudo actualizar Excel (falta openpyxl)")
        except Exception as e:
            print_warning(f"Error actualizando Excel: {e}")
        
    except Exception as e:
        print_error(f"Error: {e}")
        if 'browser' in locals():
            browser.quit()


# ==================== Ver Cursos ====================

def flujo_ver_cursos():
    """Muestra los cursos disponibles en el cache."""
    from services.course_cache import CourseCache
    
    print_header("CURSOS DISPONIBLES")
    
    cache = CourseCache()
    
    if cache.is_empty:
        print_warning("El cache está vacío")
        print_info("Usa la opción 2 para sincronizar desde Moodle")
        return
    
    print(f"\n{cache.summary()}")
    
    print(f"\n🔬 PRUEBAS DIAGNÓSTICAS ({len(cache.get_diagnosticas())}):")
    for course in cache.get_diagnosticas():
        print(f"   [{course.course_id}] {course.name}")
    
    print(f"\n🔧 PRUEBAS TÉCNICAS ({len(cache.get_tecnicas())}):")
    for course in cache.get_tecnicas():
        print(f"   [{course.course_id}] {course.name}")


# ==================== Generar Documento de Prueba ====================

def flujo_documento_prueba():
    """Genera un documento de prueba con datos de ejemplo."""
    print_header("GENERAR DOCUMENTO DE PRUEBA")
    
    try:
        from services.document_generator import DocumentGenerator, PruebaInfo
        
        pruebas = [
            PruebaInfo(
                nombre="Prueba Diagnóstica (DX) Python",
                url="https://campusvirtual.izyacademy.com/course/view.php?id=611",
                niveles=[
                    {"nivel": "Básico", "tiempo": "15 minutos"},
                    {"nivel": "Intermedio", "tiempo": "15 minutos"},
                    {"nivel": "Avanzado", "tiempo": "15 minutos"},
                ],
                lenguaje="Español",
                monitorizacion="Sí"
            ),
            PruebaInfo(
                nombre="Prueba Técnica (DT) SQL & Data Warehouse",
                url="https://campusvirtual.izyacademy.com/course/view.php?id=590",
                niveles=[
                    {"nivel": "Intermedio", "tiempo": "24 horas"},
                ],
                lenguaje="Español",
                monitorizacion="Sí"
            ),
        ]
        
        os.makedirs("output", exist_ok=True)
        
        generator = DocumentGenerator(output_dir="./output")
        filepath = generator.generate(
            nombre_candidato="Candidato de Prueba",
            email="prueba@ejemplo.com",
            usuario="cprueba",
            contrasena="Test123!@#",
            pruebas=pruebas,
            duracion_dias=2,
            es_usuario_nuevo=True
        )
        
        print_success(f"Documento generado: {filepath}")
        
        abrir = input("\n¿Abrir el documento? (s/n) [s]: ").strip().lower()
        if abrir != 'n':
            try:
                os.startfile(filepath)
            except Exception:
                print_info(f"Abre manualmente: {filepath}")
                
    except ImportError:
        print_error("No se pudo importar el generador de documentos.")
        print_info("Instala con: pip install python-docx")
    except Exception as e:
        print_error(f"Error: {e}")


# ==================== Generar/Actualizar Plantilla Excel ====================

def flujo_generar_plantilla():
    """Genera o actualiza la plantilla Excel para solicitudes."""
    print_header("GENERAR/ACTUALIZAR PLANTILLA EXCEL")
    
    try:
        from utils.excel_template import ExcelTemplateGenerator
        from services.course_cache import CourseCache
        
        cache = CourseCache()
        
        if cache.is_empty:
            print_warning("El cache de cursos está vacío")
            print_info("La plantilla se creará sin catálogo de pruebas")
            print_info("Sincroniza el catálogo (opción 2) para actualizar las pruebas")
        
        excel_path = input(f"Ruta del archivo Excel [{DEFAULT_EXCEL_PATH}]: ").strip()
        if not excel_path:
            excel_path = DEFAULT_EXCEL_PATH
        
        generator = ExcelTemplateGenerator(cache)
        
        if os.path.exists(excel_path):
            print_info(f"El archivo ya existe: {excel_path}")
            opcion = input("¿Qué deseas hacer?\n  1. Actualizar solo catálogo de pruebas\n  2. Crear archivo nuevo (sobreescribir)\n  0. Cancelar\nSelecciona [1]: ").strip()
            
            if opcion == "0":
                print_warning("Operación cancelada")
                return
            elif opcion == "2":
                generator.create_template(excel_path)
                print_success(f"Plantilla creada: {excel_path}")
            else:
                generator.update_catalog(excel_path)
                print_success(f"Catálogo actualizado en: {excel_path}")
        else:
            generator.create_template(excel_path)
            print_success(f"Plantilla creada: {excel_path}")
        
        print_info("\n📋 ESTRUCTURA DE LA PLANTILLA:")
        print("   • Hoja 'Solicitudes': Datos de candidatos y pruebas")
        print("   • Hoja 'Generalistas': Catálogo de generalistas")
        print("   • Hoja 'Catalogo_Pruebas': Lista de pruebas disponibles")
        print("   • Hoja 'Procesados': Registro de solicitudes procesadas")
        
        abrir = input("\n¿Abrir el archivo? (s/n) [s]: ").strip().lower()
        if abrir != 'n':
            try:
                os.startfile(excel_path)
            except Exception:
                print_info(f"Abre manualmente: {excel_path}")
                
    except ImportError:
        print_error("No se pudo importar el generador de plantillas.")
        print_info("Instala con: pip install openpyxl")
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()


# ==================== Gestión de Generalistas ====================

def flujo_gestionar_generalistas():
    """Gestiona el listado de generalistas en el Excel."""
    print_header("GESTIÓN DE GENERALISTAS")
    
    try:
        from utils.excel_template import GeneralistasManager
        from core.exceptions import (
            ExcelFileNotFoundError,
            ExcelSheetNotFoundError,
            GeneralistaNotFoundError,
            GeneralistaAlreadyExistsError,
            InvalidGeneralistaDataError
        )
        
        excel_path = input(f"Ruta del archivo Excel [{DEFAULT_EXCEL_PATH}]: ").strip()
        if not excel_path:
            excel_path = DEFAULT_EXCEL_PATH
        
        if not os.path.exists(excel_path):
            print_error(f"Archivo no encontrado: {excel_path}")
            print_info("Genera primero la plantilla con la opción 6")
            return
        
        try:
            manager = GeneralistasManager(excel_path)
        except ExcelFileNotFoundError as e:
            print_error(str(e))
            return
        
        while True:
            print("\n" + "-" * 40)
            print("  GESTIÓN DE GENERALISTAS")
            print("-" * 40)
            print("  1. Listar generalistas")
            print("  2. Agregar generalista")
            print("  3. Eliminar generalista")
            print("  4. Actualizar generalista")
            print("  0. Volver al menú principal")
            
            opcion = input("\nSelecciona una opción: ").strip()
            
            if opcion == "0":
                break
                
            elif opcion == "1":
                # Listar
                try:
                    generalistas = manager.list_generalistas()
                    if not generalistas:
                        print_warning("No hay generalistas registrados")
                    else:
                        print(f"\n📋 GENERALISTAS ({len(generalistas)}):")
                        print("-" * 60)
                        for g in generalistas:
                            print(f"  {g['id']:2}. {g['nombre']}")
                            print(f"      📧 {g['email']}")
                        print("-" * 60)
                except ExcelSheetNotFoundError as e:
                    print_error(str(e))
                    
            elif opcion == "2":
                # Agregar
                print("\n➕ AGREGAR GENERALISTA")
                nombre = input("Nombre completo: ").strip()
                email = input("Email: ").strip()
                
                try:
                    if manager.add_generalista(nombre, email):
                        print_success(f"Generalista agregado: {nombre}")
                except InvalidGeneralistaDataError as e:
                    print_error(str(e))
                except GeneralistaAlreadyExistsError as e:
                    print_error(str(e))
                except Exception as e:
                    print_error(f"Error inesperado: {e}")
                    
            elif opcion == "3":
                # Eliminar
                print("\n➖ ELIMINAR GENERALISTA")
                
                # Mostrar lista actual
                try:
                    generalistas = manager.list_generalistas()
                    if not generalistas:
                        print_warning("No hay generalistas para eliminar")
                        continue
                    
                    print("Generalistas actuales:")
                    for g in generalistas:
                        print(f"  {g['id']}. {g['nombre']} ({g['email']})")
                    
                    print("\n💡 Puedes usar el número (ID), nombre o email")
                    identifier = input("Identificador del generalista a eliminar: ").strip()
                    
                    if not identifier:
                        print_warning("Operación cancelada")
                        continue
                    
                    # Mostrar qué generalista se va a eliminar
                    gen_a_eliminar = manager.get_generalista(identifier)
                    if gen_a_eliminar:
                        confirm = input(f"¿Seguro que deseas eliminar a '{gen_a_eliminar['nombre']}'? (s/n) [n]: ").strip().lower()
                    else:
                        print_error(f"No se encontró generalista con: {identifier}")
                        continue
                    
                    if confirm != 's':
                        print_warning("Operación cancelada")
                        continue
                    
                    manager.remove_generalista(identifier)
                    print_success(f"Generalista eliminado: {gen_a_eliminar['nombre']}")
                    
                except GeneralistaNotFoundError as e:
                    print_error(str(e))
                except ExcelSheetNotFoundError as e:
                    print_error(str(e))
                except Exception as e:
                    print_error(f"Error inesperado: {e}")
                    
            elif opcion == "4":
                # Actualizar
                print("\n✏️  ACTUALIZAR GENERALISTA")
                
                # Mostrar lista actual
                try:
                    generalistas = manager.list_generalistas()
                    if not generalistas:
                        print_warning("No hay generalistas para actualizar")
                        continue
                    
                    print("Generalistas actuales:")
                    for g in generalistas:
                        print(f"  {g['id']}. {g['nombre']} ({g['email']})")
                    
                    print("\n💡 Puedes usar el número (ID), nombre o email")
                    identifier = input("Identificador del generalista a actualizar: ").strip()
                    
                    if not identifier:
                        print_warning("Operación cancelada")
                        continue
                    
                    # Verificar que existe
                    gen_actual = manager.get_generalista(identifier)
                    if not gen_actual:
                        print_error(f"No se encontró generalista con: {identifier}")
                        continue
                    
                    print(f"\nActualizando: {gen_actual['nombre']} ({gen_actual['email']})")
                    print("Deja en blanco para mantener el valor actual:")
                    nuevo_nombre = input(f"Nuevo nombre [{gen_actual['nombre']}]: ").strip()
                    nuevo_email = input(f"Nuevo email [{gen_actual['email']}]: ").strip()
                    
                    if not nuevo_nombre and not nuevo_email:
                        print_warning("No se realizaron cambios")
                        continue
                    
                    manager.update_generalista(identifier, nuevo_nombre or None, nuevo_email or None)
                    print_success(f"Generalista actualizado")
                    
                except GeneralistaNotFoundError as e:
                    print_error(str(e))
                except InvalidGeneralistaDataError as e:
                    print_error(str(e))
                except ExcelSheetNotFoundError as e:
                    print_error(str(e))
                except Exception as e:
                    print_error(f"Error inesperado: {e}")
            else:
                print_error("Opción no válida")
                
    except ImportError as e:
        print_error(f"No se pudo importar el módulo: {e}")
        print_info("Verifica que existan utils/excel_template.py y core/exceptions.py")
    except Exception as e:
        print_error(f"Error: {e}")


# ==================== Menú Principal ====================

def show_menu() -> str:
    """Muestra el menú de opciones."""
    print("\n" + "=" * 50)
    print("  🎓 GESTOR Q-VISION v5.1")
    print("=" * 50)
    print("\n📋 PROCESAMIENTO:")
    print("  1. Procesar solicitudes desde Excel (BATCH)")
    print("  2. Asignar pruebas manualmente (interactivo)")
    print("\n🔄 SINCRONIZACIÓN:")
    print("  3. Sincronizar catálogo de cursos")
    print("  4. Ver cursos disponibles")
    print("\n📄 DOCUMENTOS Y CONFIGURACIÓN:")
    print("  5. Generar documento de prueba")
    print("  6. Generar/actualizar plantilla Excel")
    print("  7. Gestionar generalistas")
    print("\n  0. Salir")
    print()
    
    return input("Selecciona una opción: ").strip()


def main():
    """Función principal."""
    print_header("🎓 GESTOR Q-VISION - AUTOMATIZACIÓN MOODLE")
    print("Versión 5.1 - Procesamiento por lotes desde Excel")
    
    # Verificar imports al inicio
    if not check_imports():
        sys.exit(1)
    
    while True:
        option = show_menu()
        
        if option == "0":
            print("\n👋 ¡Hasta luego!")
            break
            
        elif option == "1":
            flujo_procesar_excel()
            
        elif option == "2":
            flujo_asignar_pruebas()
            
        elif option == "3":
            flujo_sincronizar_catalogo()
            
        elif option == "4":
            flujo_ver_cursos()
            
        elif option == "5":
            flujo_documento_prueba()
            
        elif option == "6":
            flujo_generar_plantilla()
            
        elif option == "7":
            flujo_gestionar_generalistas()
            
        else:
            print_error("Opción no válida")
        
        input("\nPresiona Enter para continuar...")


if __name__ == "__main__":
    main()