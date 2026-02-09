# Gestor Q-Vision - Automatización Moodle

Automatizador de procesos para la plataforma académica Moodle de IZY Academy.

**v4.1** – Aplicación principal con menú interactivo, procesamiento de múltiples candidatos, sincronización de catálogo, y preparación para procesamiento por lotes desde Excel.

## Descripción

Este proyecto automatiza:
- ✅ Creación y gestión de usuarios
- ✅ Sincronización de catálogo de cursos (desde menú: Diagnósticas, Técnicas o todo)
- ✅ Matrículas y reactivaciones
- ✅ Asignación de pruebas técnicas y diagnósticas
- ✅ Limpieza de intentos anteriores en quizzes
- ✅ Generación de documento Word para correo
- ✅ Múltiples candidatos sin cerrar sesión
- ✅ Cierre automático de modal SMOWL
- ✅ Limpieza de filtros de búsqueda entre candidatos
- 🔄 **Procesamiento por lotes desde Excel** (en desarrollo)
- 🔄 Envío automático de correos via n8n (pendiente)
- 🔄 Exportación de resultados de pruebas (pendiente)
- 🔄 Interfaz gráfica (GUI) (pendiente)

## Flujo Principal de Asignación de Pruebas

```
┌─────────────────────────────────────────────────────────────┐
│                    FLUJO DE ASIGNACIÓN v4                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │  1. Login en Moodle   │  (~5s)
                │  (credenciales admin) │
                └───────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ 2. Ingresar email del │
                │      candidato        │
                └───────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ 3. Buscar usuario por │  (~7s)
                │        email          │
                └───────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐
    │  Usuario existe │         │ Usuario NO existe│
    └─────────────────┘         └─────────────────┘
              │                           │
              ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐
    │ Actualizar      │  (~11s) │  Crear usuario  │
    │ contraseña      │         │  (genera user + │
    └─────────────────┘         │   contraseña)   │
              │                 └─────────────────┘
              └─────────────┬─────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ 4. Seleccionar tiempo │
                │    de habilitación    │
                │   (1, 2 o 3 días)     │
                └───────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ 5. Seleccionar pruebas│
                │     a asignar         │
                └───────────────────────┘
                            │
                            ▼
            ┌───────────────────────────────┐
            │  6. Por cada prueba:          │
            │  ┌─────────────────────────┐  │
            │  │ a) Limpiar intentos     │  │  (~2-3s por quiz)
            │  │    anteriores (quizzes) │  │
            │  └─────────────────────────┘  │
            │              │                │
            │              ▼                │
            │  ┌─────────────────────────┐  │
            │  │ b) Matricular usuario   │  │  (~8s)
            │  │    o reactivar matrícula│  │
            │  └─────────────────────────┘  │
            └───────────────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ 7. Generar documento  │
                │    Word con datos     │  (~1s)
                │    para el correo     │
                └───────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ 8. (Futuro) Enviar    │
                │    correo via n8n     │
                └───────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ 9. ¿Otro candidato?   │
                │    → Volver al paso 2 │
                └───────────────────────┘
```

## Arquitectura

El proyecto sigue el patrón **Atomic Design** adaptado para backend:

```
Gestor_Qvision/
│
├── core/                     # ÁTOMOS: Componentes básicos
│   ├── __init__.py
│   ├── config.py             ✅ Configuración centralizada
│   ├── exceptions.py         ✅ Excepciones personalizadas
│   ├── logger.py             ✅ Logging con colores y rotación
│   └── browser.py            ✅ Gestión del navegador (OPTIMIZADO v3)
│
├── components/               # MOLÉCULAS: Operaciones específicas
│   ├── auth.py               ✅ Autenticación (login/logout)
│   ├── user.py               ✅ Gestión de usuarios (v2 - limpieza filtros)
│   ├── course.py             ✅ Gestión de cursos (OPTIMIZADO)
│   ├── enrollment.py         ✅ Gestión de matrículas (v3.4 - modal SMOWL)
│   └── quiz.py               ✅ Limpieza de intentos (OPTIMIZADO v3)
│
├── services/                 # ORGANISMOS: Flujos de negocio
│   ├── __init__.py
│   ├── course_cache.py       ✅ Cache local de cursos
│   ├── candidate_service.py  ✅ Orquestador del flujo completo (v2)
│   ├── document_generator.py ✅ Generador de documentos Word
│   └── excel_reader.py       🔄 Lector de solicitudes desde Excel (EN DESARROLLO)
│
├── models/                   # Estructuras de datos (Pydantic)
│   ├── user.py               ✅ UserData, UserSearchResult, UserCredentials
│   ├── course.py             ✅ CourseData, CourseCatalog, QuizData (v2 con get_table_data)
│   └── enrollment.py         ✅ EnrollmentData, EnrollmentResult, EnrollmentConfig
│
├── utils/                    # Utilidades auxiliares
│   ├── __init__.py           🔄 EN DESARROLLO
│   └── excel_template.py     🔄 Generador de plantilla Excel (EN DESARROLLO)
│
├── assets/                   # Recursos estáticos
│   ├── firma_qvision.png     ✅ Imagen de firma (PNG)
│   └── firma_qvision.jfif    ✅ Imagen de firma (alternativa JFIF)
│
├── data/                     # Datos persistentes
│   └── courses.json          ✅ Cache de cursos (generado)
│
├── output/                   # Documentos generados
│   └── *.docx                ✅ Documentos de asignación (generados)
│
├── logs/                     # Archivos de log (generados)
├── screenshots/              # Capturas de errores (generadas)
│
├── main.py                   ✅ Punto de entrada principal (v4.0)
├── test_full_flow.py         ✅ Script de prueba interactivo (alternativo)
├── .env                      # Variables de entorno (opcional)
└── README.md                 ✅ Este archivo
```

## 🆕 Correcciones Recientes (v4.1)

### Modal SMOWL (enrollment.py v3.4)
La plataforma agregó un modal informativo para pruebas con monitorización que bloqueaba los clics.

**Solución:** Método `_close_smowl_modal()` que detecta y cierra automáticamente el modal:
```python
# El modal tiene: id="btn-smowl-entendido"
def _close_smowl_modal(self) -> bool:
    smowl_btn = self.browser.driver.find_element(By.ID, "btn-smowl-entendido")
    if smowl_btn.is_displayed():
        self.browser.driver.execute_script("arguments[0].click();", smowl_btn)
        return True
    return False
```

### Limpieza de Filtros de Búsqueda (user.py v2)
Al procesar múltiples candidatos, los filtros de búsqueda se acumulaban impidiendo encontrar usuarios.

**Solución:** Método `_clear_search_filters()` que limpia filtros antes de cada búsqueda:
```python
# Selector verificado: id="id_removeall"
def _clear_search_filters(self) -> None:
    clear_btn = self.browser.driver.find_element(By.ID, "id_removeall")
    if clear_btn.is_displayed():
        self.browser.driver.execute_script("arguments[0].click();", clear_btn)
```

### Filtro de Participantes (enrollment.py v3.3)
El campo de texto del filtro no aparecía cuando la ventana del navegador no tenía el foco.

**Solución:** Forzar foco de ventana y re-seleccionar el filtro si el input no aparece:
```python
# Forzar foco
self.browser.driver.switch_to.window(self.browser.driver.current_window_handle)
# Re-seleccionar si es necesario (hasta 3 intentos)
```

## 📄 Generación de Documentos Word

### Características

El sistema genera documentos Word profesionales con:
- Saludo personalizado al candidato
- **Tabla dinámica de pruebas** con celdas combinadas para múltiples niveles
- Credenciales de acceso (usuario/contraseña)
- Fechas de habilitación calculadas automáticamente
- Instrucciones de instalación de SMOWL
- Firma corporativa (imagen)

### Estructura de la Tabla

La tabla soporta dos tipos de pruebas:

**Pruebas Diagnósticas (múltiples niveles):**
| Nombre | Link | Nivel | Tiempo | Lenguaje | Monitorización |
|--------|------|-------|--------|----------|----------------|
| Prueba DX Python | https://... | Básico | 15 min | Español | Sí |
| _(combinada)_ | _(combinada)_ | Intermedio | 15 min | _(combinada)_ | _(combinada)_ |
| _(combinada)_ | _(combinada)_ | Avanzado | 15 min | _(combinada)_ | _(combinada)_ |

**Pruebas Técnicas (nivel único):**
| Nombre | Link | Nivel | Tiempo | Lenguaje | Monitorización |
|--------|------|-------|--------|----------|----------------|
| Prueba Técnica SQL | https://... | Intermedio | 24 horas | Español | Sí |

## 🚀 Optimización de Rendimiento (v3)

### Métricas de Rendimiento

| Operación | Antes (v1) | Después (v3) | Mejora |
|-----------|------------|--------------|--------|
| Login + Cookies | ~25s | ~5s | 80% |
| Búsqueda usuario | ~30s | ~7s | 77% |
| Actualización contraseña | ~40s | ~11s | 72% |
| Eliminación intentos (sin intentos) | ~60s | ~2s | 97% |
| Eliminación intentos (con intentos) | ~90s | ~5s | 94% |
| Filtro participantes | ~100s | ~3s | 97% |
| Matrícula/Reactivación | ~84s | ~8s | 90% |
| Generación documento | N/A | ~1s | ✨ |
| **TOTAL (1 prueba, 2 quizzes)** | **~7 min** | **~25-30s** | **~93%** |

## Progreso del Desarrollo

### Fase 1-4: Core, Modelos, Componentes, Servicios ✅ COMPLETADO

### Fase 5: Aplicación Principal ✅ COMPLETADO
- [x] `main.py` - v4.0: Punto de entrada con menú completo
- [x] Loop para múltiples candidatos sin cerrar sesión
- [x] Sincronización de catálogo desde menú

### Fase 6: Procesamiento por Lotes 🔄 EN DESARROLLO
- [x] Diseño de estructura Excel (Solicitudes, Generalistas, Catálogo)
- [x] `utils/excel_template.py` - Generador de plantilla Excel
- [x] `services/excel_reader.py` - Lector de solicitudes
- [ ] Integración con `main.py` (opción de menú)
- [ ] Actualización automática de Excel en sincronización

### Fase 7: Integración Email 🔄 PENDIENTE
- [x] Generación de documento Word
- [ ] `services/email_service.py` - Integración con n8n
- [ ] Workflow n8n para envío de correos

### Fase 8: Extracción de Resultados 🔄 PENDIENTE
- [ ] Usar URL de calificaciones del cache (`url_grades`)
- [ ] Descargar resultados a Excel/CSV
- [ ] Actualizar Excel de solicitudes con calificaciones

### Fase 9: Interfaz Gráfica 🔄 PENDIENTE
- [ ] GUI con Tkinter/PyQt

## Instalación

```bash
# Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install selenium pydantic pydantic-settings python-dotenv colorama "pydantic[email]" python-docx openpyxl
```

## Configuración

### Opción 1: Archivo .env (opcional)
```env
MOODLE_BASE_URL=https://campusvirtual.izyacademy.com
MOODLE_USERNAME=tu_usuario_admin
MOODLE_PASSWORD=tu_contraseña
```

### Opción 2: Ingreso manual
El script solicitará las credenciales al ejecutar (recomendado por seguridad).

## Uso

### Aplicación principal

```bash
python main.py
```

**Menú v4.0:**
1. **Asignar pruebas (múltiples candidatos)** – Loop para procesar varios candidatos sin cerrar sesión
2. **Sincronizar catálogo de cursos** – Descargar desde Moodle (Diagnósticas, Técnicas o todo)
3. **Ver cursos disponibles** – Listar cursos del cache local
4. **Generar documento de prueba** – Crear documento Word con datos de ejemplo
0. Salir

## Selectores de Moodle (Referencia)

### Login
| Elemento | Selector |
|----------|----------|
| Usuario | `#username` |
| Contraseña | `#password` |
| Botón | `#loginbtn` |
| Cookies | `#acceptCookies` |

### Administración de Usuarios
| Elemento | Selector |
|----------|----------|
| Limpiar filtros | `#id_removeall` |
| Mostrar más | `a[aria-controls*='filters']` |

### Participantes (Filtro)
| Elemento | Selector |
|----------|----------|
| Tipo de filtro | `select[data-filterfield='type']` |
| Campo texto | `input[id^='form_autocomplete_input']` |
| Aplicar | `button[data-filteraction='apply']` |

### Modal SMOWL
| Elemento | Selector |
|----------|----------|
| Overlay | `#popup-smowl` |
| Botón Entendido | `#btn-smowl-entendido` |

### Quiz (Eliminar Intentos)
| Elemento | Selector |
|----------|----------|
| Tabla | `table#attempts` |
| Checkbox | `input[name='attemptid[]']` |
| Eliminar | `input#deleteattemptsbutton` |
| Confirmar | `input.btn-primary[value='Sí']` |

## Problemas Resueltos

| Problema | Causa | Solución |
|----------|-------|----------|
| Modal SMOWL bloquea clics | Nuevo modal informativo | `_close_smowl_modal()` en enrollment.py |
| Filtros de búsqueda acumulados | No se limpiaban entre búsquedas | `_clear_search_filters()` en user.py |
| Campo de filtro no aparece | Ventana sin foco | Forzar foco + re-seleccionar |
| 50+ segundos en filtro | Selector incorrecto | `input[id^='form_autocomplete_input']` |
| No eliminaba intentos | Botón es `input[type=submit]` | `input#deleteattemptsbutton` |
| Modal no confirmaba | YUI modal diferente | `input.btn-primary[value='Sí']` |
| Página muy lenta | `wait_for_page_load()` | `page_load_strategy = "eager"` |

## Integración con n8n (Próximo Paso)

### Arquitectura Propuesta

```
┌─────────────────────────────────────────────────────────────┐
│                   FLUJO 100% AUTOMÁTICO                      │
└─────────────────────────────────────────────────────────────┘

    PYTHON (este proyecto)                  n8n
    ──────────────────────                 ────
    1. Leer Excel de solicitudes               
    2. Login Moodle (una vez)                  
    3. Por cada candidato:                     
       - Crear/actualizar usuario              
       - Asignar pruebas                       
       - Generar documento Word                
    4. POST al webhook de n8n ─────────────► Webhook recibe JSON
       {                                       ↓
         "email": "candidato@mail.com",       Envía correo Outlook
         "nombre": "Juan García",              con Word adjunto
         "documento_base64": "UEsDB...",       + CC a generalista
         "generalista_email": "gen@emp.com"    ↓
       }                                      ✅ Correo enviado
    5. Actualizar Excel (estado)               
    6. Siguiente candidato...
```

---

*Última actualización: Febrero 2026 - v4.1 con correcciones de modal SMOWL y filtros de búsqueda*# Gestor_qvision
