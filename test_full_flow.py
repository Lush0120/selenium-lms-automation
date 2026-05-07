"""
test_full_flow.py
Script de prueba integral para el flujo completo de asignación de pruebas.

Flujo interactivo:
1. Solicitar credenciales de Moodle
2. Login en la plataforma
3. Solicitar email del candidato
4. Buscar usuario por email
5. Si existe → mostrar datos y actualizar contraseña
   Si no existe → solicitar datos y crear usuario
6. Solicitar tiempo de habilitación de pruebas
7. Mostrar pruebas disponibles y solicitar selección
8. Por cada prueba: limpiar intentos → matricular/reactivar
9. Mostrar resumen con datos para el correo

Uso:
    python test_full_flow.py
"""

import sys
import getpass
from datetime import datetime
from typing import Optional

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
    """Imprime mensaje de éxito."""
    print(f"✅ {text}")

def print_error(text: str) -> None:
    """Imprime mensaje de error."""
    print(f"❌ {text}")

def print_info(text: str) -> None:
    """Imprime mensaje informativo."""
    print(f"ℹ️  {text}")

def print_warning(text: str) -> None:
    """Imprime mensaje de advertencia."""
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


# ==================== Verificaciones iniciales ====================

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
        print_error("El cache de cursos está vacío")
        print_info("Ejecuta primero la sincronización de cursos")
        return False
    
    print_success(f"Cache OK: {cache.total_courses} cursos disponibles")
    return True


# ==================== Flujo Principal ====================

def run_interactive_flow():
    """
    Ejecuta el flujo completo de forma interactiva.
    
    Solicita todos los datos necesarios paso a paso.
    """
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
    
    print_header("ASIGNACIÓN DE PRUEBAS - FLUJO COMPLETO")
    
    # ==================== Paso 1: Credenciales ====================
    print_step(1, "Credenciales de Moodle")
    
    # Verificar si hay credenciales en settings
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
    
    # ==================== Paso 2: Login ====================
    print_step(2, "Iniciando sesión en Moodle")
    
    # Preguntar modo headless
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
        # ==================== Paso 3: Email del candidato ====================
        print_step(3, "Datos del candidato")
        
        candidate_email = input_required("Email del candidato: ").lower()
        
        # ==================== Paso 4: Buscar usuario ====================
        print_step(4, "Verificando si el usuario existe")
        
        user_comp = UserComponent(browser)
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
            
            # Actualizar contraseña (pasando search_result para evitar búsqueda duplicada)
            print_info("\nActualizando contraseña...")
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
                browser.quit()
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
                browser.quit()
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
                    browser.quit()
                    return False
            except Exception as e:
                print_error(f"Error creando usuario: {e}")
                browser.quit()
                return False
        
        # ==================== Paso 5: Tiempo de habilitación ====================
        print_step(5, "Tiempo de habilitación de pruebas")
        
        print_info("Opciones disponibles:")
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
        
        # ==================== Paso 6: Seleccionar pruebas ====================
        print_step(6, "Selección de pruebas a asignar")
        
        cache = CourseCache()
        courses = cache.get_all()
        
        print_info(f"\nPruebas disponibles ({len(courses)}):\n")
        
        # Mostrar cursos con índice
        for i, course in enumerate(courses, 1):
            # Obtener duración si existe
            duration_info = ""
            for char in course.characteristics:
                if "duración" in char.name.lower():
                    duration_info = f" - {char.value}"
                    break
            print(f"  {i}. [{course.course_id}] {course.name}{duration_info}")
        
        print_info("\nIngresa los números de las pruebas separados por coma")
        print_info("Ejemplo: 1,3,5 para seleccionar las pruebas 1, 3 y 5")
        print_info("O ingresa 'todas' para seleccionar todas")
        
        while True:
            selection = input("\nPruebas a asignar: ").strip().lower()
            
            if selection == 'todas':
                selected_courses = courses
                break
            
            try:
                indices = [int(x.strip()) for x in selection.split(",")]
                selected_courses = []
                
                for idx in indices:
                    if 1 <= idx <= len(courses):
                        selected_courses.append(courses[idx - 1])
                    else:
                        print_warning(f"Índice {idx} fuera de rango")
                
                if selected_courses:
                    break
                else:
                    print_error("No se seleccionó ninguna prueba válida")
            except ValueError:
                print_error("Formato inválido. Usa números separados por coma")
        
        print_success(f"\nPruebas seleccionadas ({len(selected_courses)}):")
        for course in selected_courses:
            print(f"  - {course.name}")
        
        confirm = input("\n¿Continuar con la asignación? (s/n) [s]: ").strip().lower()
        if confirm == 'n':
            print_warning("Operación cancelada")
            browser.quit()
            return False
        
        # ==================== Paso 7: Procesar cada prueba ====================
        print_step(7, "Asignando pruebas")
        
        enrollment_comp = EnrollmentComponent(browser)
        quiz_comp = QuizComponent(browser)
        course_comp = CourseComponent(browser, cache=cache)
        
        results = []
        total_attempts_deleted = 0
        
        for i, course in enumerate(selected_courses, 1):
            print(f"\n--- Prueba {i}/{len(selected_courses)}: {course.name} ---")
            
            # 7a: Limpiar intentos anteriores
            print_info("Limpiando intentos anteriores...")
            
            try:
                quizzes = course_comp.get_course_quizzes(course.course_id)
                attempts_deleted = 0
                
                for quiz in quizzes:
                    result = quiz_comp.delete_user_attempts(
                        quiz_id=quiz.quiz_id,
                        user_email=candidate_email,
                        user_firstname=firstname.split()[0],  # Primer nombre
                        user_lastname=lastname.split()[0]     # Primer apellido
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
            
            # 7b: Matricular o reactivar
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
                        "enrollment": enroll_result.enrollment
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
        
        # ==================== Paso 8: Resumen final ====================
        print_step(8, "Resumen de la asignación")
        
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
            
            if course.characteristics:
                print(f"      Características:")
                for char in course.characteristics:
                    print(f"        - {char.name}: {char.value}")
        
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
        
        # Cerrar navegador
        browser.quit()
        print_success("\nProceso completado")
        
        return len(failed) == 0
        
    except Exception as e:
        print_error(f"Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        
        if 'browser' in locals():
            browser.take_screenshot("error_unexpected")
            browser.quit()
        
        return False


# ==================== Menú Principal ====================

def show_menu() -> str:
    """Muestra el menú de opciones."""
    print("\n" + "=" * 50)
    print("  GESTOR Q-VISION - ASIGNACIÓN DE PRUEBAS")
    print("=" * 50)
    print("\nOpciones:")
    print("  1. Verificar sistema (imports y cache)")
    print("  2. Ejecutar asignación de pruebas")
    print("  3. Ver cursos disponibles")
    print("  0. Salir")
    print()
    
    return input("Selecciona una opción: ").strip()


def show_courses():
    """Muestra los cursos disponibles en el cache."""
    from services.course_cache import CourseCache
    
    print_header("CURSOS DISPONIBLES")
    
    cache = CourseCache()
    
    if cache.is_empty:
        print_warning("El cache está vacío")
        return
    
    print_info(f"Total: {cache.total_courses} cursos")
    print_info(f"Última sincronización: {cache.last_sync}")
    
    print("\n--- Pruebas Técnicas ---")
    for course in cache.get_tecnicas():
        print(f"  [{course.course_id}] {course.name}")
    
    print("\n--- Pruebas Diagnósticas ---")
    for course in cache.get_diagnosticas():
        print(f"  [{course.course_id}] {course.name}")


def main():
    """Función principal."""
    print_header("GESTOR Q-VISION")
    
    # Verificar imports al inicio
    if not check_imports():
        sys.exit(1)
    
    while True:
        option = show_menu()
        
        if option == "0":
            print("\n¡Hasta luego!")
            break
            
        elif option == "1":
            print_header("VERIFICACIÓN DEL SISTEMA")
            check_imports()
            check_cache()
            
        elif option == "2":
            if not check_cache():
                print_info("Primero sincroniza el catálogo de cursos")
                continue
            
            run_interactive_flow()
            
        elif option == "3":
            show_courses()
            
        else:
            print_error("Opción no válida")


if __name__ == "__main__":
    main()