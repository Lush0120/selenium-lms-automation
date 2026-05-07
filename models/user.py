"""
models/user.py
Modelos de datos para usuarios con validación Pydantic.

Estos modelos aseguran que los datos de usuario sean válidos
antes de enviarlos a Moodle, evitando errores en tiempo de ejecución.

Incluye generación inteligente de usernames con múltiples estrategias
para evitar colisiones con usuarios existentes.

Uso:
    from models.user import UserData
    
    user = UserData(
        primer_nombre="Juan Pedro",
        primer_apellido="García",
        correo="juan@test.com",
        telefono="3001234567",
        ciudad="Bogotá"
    )
    
    # Generar alternativas si el username base ya existe
    for i in range(10):
        print(user.generar_username_alternativo(i))
"""

import re
import secrets
import string
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from core.logger import get_logger

logger = get_logger(__name__)


class UserCredentials(BaseModel):
    """
    Credenciales básicas de usuario.
    
    Usado para operaciones que solo requieren usuario/contraseña,
    como login o actualización de contraseña.
    """
    username: str = Field(..., min_length=1, description="Nombre de usuario")
    password: str = Field(..., min_length=1, description="Contraseña")


class UserData(BaseModel):
    """
    Datos completos de un usuario para creación o matrícula.
    
    Incluye validación automática y normalización de campos.
    El username y password se generan automáticamente si no se proporcionan.
    
    Attributes:
        primer_nombre: Primer nombre (requerido)
        segundo_nombre: Segundo nombre (opcional)
        primer_apellido: Primer apellido (requerido)
        segundo_apellido: Segundo apellido (opcional)
        correo: Email válido (requerido)
        telefono: Número de teléfono (requerido)
        ciudad: Ciudad de residencia (requerido)
        username: Nombre de usuario (se genera si no se proporciona)
        password: Contraseña (se genera si no se proporciona)
    """
    
    # Campos requeridos
    primer_nombre: str = Field(..., min_length=1, description="Primer nombre")
    primer_apellido: str = Field(..., min_length=1, description="Primer apellido")
    correo: EmailStr = Field(..., description="Correo electrónico")
    telefono: str = Field(..., min_length=1, description="Número de teléfono")
    ciudad: str = Field(..., min_length=1, description="Ciudad")
    
    # Campos opcionales
    segundo_nombre: Optional[str] = Field(default=None, description="Segundo nombre")
    segundo_apellido: Optional[str] = Field(default=None, description="Segundo apellido")
    
    # Campos generados automáticamente
    username: Optional[str] = Field(default=None, description="Nombre de usuario")
    password: Optional[str] = Field(default=None, description="Contraseña")
    
    # ==================== Validadores de campos ====================
    
    @field_validator('primer_nombre', 'primer_apellido', 'ciudad', mode='before')
    @classmethod
    def normalizar_campo_requerido(cls, v: str) -> str:
        """
        Normaliza campos de texto requeridos.
        
        - Elimina espacios extras
        - Capitaliza cada palabra
        - Valida que no esté vacío
        """
        if v is None:
            raise ValueError('Este campo es requerido')
        
        # Limpiar espacios extras y capitalizar
        cleaned = ' '.join(str(v).strip().split())
        
        if not cleaned:
            raise ValueError('Este campo no puede estar vacío')
        
        # Capitalizar cada palabra
        return cleaned.title()
    
    @field_validator('segundo_nombre', 'segundo_apellido', mode='before')
    @classmethod
    def normalizar_campo_opcional(cls, v: Optional[str]) -> Optional[str]:
        """
        Normaliza campos de texto opcionales.
        
        Retorna None si está vacío, normalizado si tiene contenido.
        """
        if v is None:
            return None
        
        cleaned = ' '.join(str(v).strip().split())
        
        if not cleaned:
            return None
        
        return cleaned.title()
    
    @field_validator('telefono', mode='before')
    @classmethod
    def normalizar_telefono(cls, v: str) -> str:
        """
        Normaliza número de teléfono.
        
        Elimina espacios, guiones y paréntesis.
        """
        if v is None:
            raise ValueError('El teléfono es requerido')
        
        # Eliminar caracteres no numéricos excepto el + inicial
        cleaned = re.sub(r'[^\d+]', '', str(v).strip())
        
        if not cleaned:
            raise ValueError('El teléfono no puede estar vacío')
        
        return cleaned
    
    @field_validator('correo', mode='before')
    @classmethod
    def normalizar_correo(cls, v: str) -> str:
        """
        Normaliza el correo electrónico.
        
        Convierte a minúsculas y elimina espacios.
        """
        if v is None:
            raise ValueError('El correo es requerido')
        
        return str(v).strip().lower()
    
    # ==================== Validador de modelo ====================
    
    @model_validator(mode='after')
    def generar_credenciales(self) -> 'UserData':
        """
        Genera username y password si no fueron proporcionados.
        
        Se ejecuta después de validar todos los campos individuales.
        """
        # Generar username si no existe (usa estrategia base)
        if not self.username:
            self.username = self.generar_username_alternativo(0)
        
        # Generar password si no existe
        if not self.password:
            self.password = self._generar_password()
        
        return self
    
    # ==================== Propiedades ====================
    
    @property
    def nombre_completo(self) -> str:
        """Retorna el nombre completo del usuario."""
        partes = [self.primer_nombre]
        
        if self.segundo_nombre:
            partes.append(self.segundo_nombre)
        
        partes.append(self.primer_apellido)
        
        if self.segundo_apellido:
            partes.append(self.segundo_apellido)
        
        return ' '.join(partes)
    
    @property
    def nombres(self) -> str:
        """Retorna solo los nombres (sin apellidos)."""
        if self.segundo_nombre:
            return f"{self.primer_nombre} {self.segundo_nombre}"
        return self.primer_nombre
    
    @property
    def apellidos(self) -> str:
        """Retorna solo los apellidos."""
        if self.segundo_apellido:
            return f"{self.primer_apellido} {self.segundo_apellido}"
        return self.primer_apellido
    
    # ==================== Generación de Username ====================
    
    def generar_username_alternativo(self, intento: int = 0) -> str:
        """
        Genera variantes del username usando diferentes estrategias.
        
        Cada intento usa una estrategia diferente para crear usernames
        únicos pero reconocibles.
        
        Args:
            intento: Número de intento (0-9 tienen estrategias específicas,
                    10+ usan sufijo aleatorio)
        
        Returns:
            Username candidato (debe verificarse en Moodle)
        
        Estrategias:
            0: jgarcia (inicial + apellido)
            1: jgarcia1 (+ número)
            2: jgarcia2 (+ número)
            3: jpgarcia (iniciales nombre + apellido)
            4: juang (nombre + inicial apellido)
            5: juangarcia (nombre + apellido)
            6: jgarcia25 (inicial + apellido + año)
            7: juanpedrogarcia (nombres completos + apellido)
            8: jgarcialopez (inicial + ambos apellidos)
            9: garcia.juan (apellido.nombre)
            10+: jgarcia_x7k (base + sufijo aleatorio)
        """
        # Componentes limpios para construir usernames
        nombre1 = self._limpiar_para_username(self.primer_nombre)
        nombre2 = self._limpiar_para_username(self.segundo_nombre) if self.segundo_nombre else ""
        apellido1 = self._limpiar_para_username(self.primer_apellido)
        apellido2 = self._limpiar_para_username(self.segundo_apellido) if self.segundo_apellido else ""
        
        # Inicial(es) del nombre
        inicial1 = nombre1[0] if nombre1 else ""
        inicial2 = nombre2[0] if nombre2 else ""
        
        # Año actual (últimos 2 dígitos)
        year = datetime.now().strftime("%y")
        
        # Estrategias de generación
        estrategias = {
            0: f"{inicial1}{apellido1}",
            1: f"{inicial1}{apellido1}1",
            2: f"{inicial1}{apellido1}2",
            3: f"{inicial1}{inicial2}{apellido1}" if inicial2 else f"{inicial1}{apellido1}3",
            4: f"{nombre1}{apellido1[0]}" if apellido1 else f"{nombre1}",
            5: f"{nombre1}{apellido1}",
            6: f"{inicial1}{apellido1}{year}",
            7: f"{nombre1}{nombre2}{apellido1}" if nombre2 else f"{nombre1}{apellido1}4",
            8: f"{inicial1}{apellido1}{apellido2}" if apellido2 else f"{inicial1}{apellido1}5",
            9: f"{apellido1}.{nombre1}",
        }
        
        if intento in estrategias:
            username = estrategias[intento]
            logger.debug(f"Username generado (estrategia {intento}): {username}")
            return username
        
        # Para intentos >= 10, usar sufijo aleatorio
        base = f"{inicial1}{apellido1}"
        sufijo = self._generar_sufijo_aleatorio(3)
        username = f"{base}_{sufijo}"
        logger.debug(f"Username generado (aleatorio, intento {intento}): {username}")
        return username
    
    def obtener_todos_los_usernames(self, limite: int = 15) -> List[str]:
        """
        Genera una lista de todos los usernames posibles.
        
        Útil para verificación en lote contra Moodle.
        
        Args:
            limite: Cantidad máxima de usernames a generar
            
        Returns:
            Lista de usernames candidatos únicos
        """
        usernames = []
        vistos = set()
        
        for i in range(limite):
            candidato = self.generar_username_alternativo(i)
            if candidato not in vistos:
                usernames.append(candidato)
                vistos.add(candidato)
        
        logger.debug(f"Generados {len(usernames)} usernames únicos")
        return usernames
    
    def actualizar_username(self, nuevo_username: str) -> None:
        """
        Actualiza el username después de verificación.
        
        Args:
            nuevo_username: Username verificado como único
        """
        self.username = nuevo_username
        logger.info(f"Username actualizado a: {nuevo_username}")
    
    # ==================== Generación de Password ====================
    
    def _generar_password(self, longitud: int = 10) -> str:
        """
        Genera una contraseña segura aleatoria.
        
        La contraseña incluye:
        - Letras mayúsculas y minúsculas
        - Números
        - Al menos un carácter especial
        
        Args:
            longitud: Longitud de la contraseña (mínimo 8)
        """
        if longitud < 8:
            longitud = 8
        
        # Caracteres disponibles
        letras = string.ascii_letters
        numeros = string.digits
        especiales = "!@#$%&*"
        
        # Asegurar al menos uno de cada tipo
        password_chars = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(numeros),
            secrets.choice(especiales),
        ]
        
        # Completar el resto
        todos = letras + numeros + especiales
        password_chars += [secrets.choice(todos) for _ in range(longitud - 4)]
        
        # Mezclar
        secrets.SystemRandom().shuffle(password_chars)
        
        password = ''.join(password_chars)
        logger.debug("Contraseña generada exitosamente")
        return password
    
    def regenerar_password(self, longitud: int = 10) -> str:
        """
        Regenera la contraseña del usuario.
        
        Args:
            longitud: Longitud de la nueva contraseña
            
        Returns:
            Nueva contraseña generada
        """
        self.password = self._generar_password(longitud)
        logger.info("Contraseña regenerada")
        return self.password
    
    # ==================== Métodos auxiliares ====================
    
    @staticmethod
    def _limpiar_para_username(texto: Optional[str]) -> str:
        """
        Limpia un texto para usarlo en username.
        
        - Convierte a minúsculas
        - Elimina espacios
        - Reemplaza caracteres especiales (tildes, ñ)
        - Elimina caracteres no alfanuméricos
        """
        if not texto:
            return ""
        
        texto = texto.lower().strip()
        
        # Reemplazar caracteres especiales
        reemplazos = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
            'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
            'ã': 'a', 'õ': 'o',
            'ñ': 'n', 'ç': 'c',
            ' ': '', '-': '', '_': '', '.': '', "'": ''
        }
        
        for original, reemplazo in reemplazos.items():
            texto = texto.replace(original, reemplazo)
        
        # Eliminar cualquier caracter no alfanumérico restante
        texto = re.sub(r'[^a-z0-9]', '', texto)
        
        return texto
    
    @staticmethod
    def _generar_sufijo_aleatorio(longitud: int = 3) -> str:
        """
        Genera un sufijo alfanumérico aleatorio.
        
        Args:
            longitud: Longitud del sufijo
            
        Returns:
            Sufijo aleatorio (ej: "x7k", "m2p")
        """
        caracteres = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(caracteres) for _ in range(longitud))


class UserSearchResult(BaseModel):
    """
    Resultado de buscar un usuario en Moodle.
    
    Attributes:
        found: Si se encontró el usuario
        user_id: ID del usuario en Moodle (si existe)
        username: Nombre de usuario
        full_name: Nombre completo mostrado
        email: Correo electrónico
        profile_url: URL al perfil del usuario
    """
    found: bool = Field(..., description="Si se encontró el usuario")
    user_id: Optional[str] = Field(default=None, description="ID en Moodle")
    username: Optional[str] = Field(default=None, description="Nombre de usuario")
    full_name: Optional[str] = Field(default=None, description="Nombre completo")
    email: Optional[str] = Field(default=None, description="Correo electrónico")
    profile_url: Optional[str] = Field(default=None, description="URL del perfil")
    
    @classmethod
    def not_found(cls) -> 'UserSearchResult':
        """Factory method para usuario no encontrado."""
        return cls(found=False)
    
    @classmethod
    def from_moodle(
        cls,
        user_id: str,
        username: str,
        full_name: str,
        email: str,
        profile_url: str
    ) -> 'UserSearchResult':
        """Factory method para usuario encontrado."""
        return cls(
            found=True,
            user_id=user_id,
            username=username,
            full_name=full_name,
            email=email,
            profile_url=profile_url
        )