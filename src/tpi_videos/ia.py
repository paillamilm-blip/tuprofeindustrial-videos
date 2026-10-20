"""Conexión con Gemini (Google AI Studio): clave, cliente y errores en español.

La clave se guarda en el archivo ``.env`` de la carpeta del repo (nunca se sube a GitHub)
o se lee de la variable de entorno ``GEMINI_API_KEY``.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

from .entorno import raiz_proyecto
from .errores import ErrorMotor

MODELO_POR_DEFECTO = "gemini-3.8-flash"  # Flash estable con nivel gratuito
NOMBRES_CLAVE = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
URL_CLAVE = "https://aistudio.google.com/apikey"
AYUDA_CLAVE = f"1) Créala gratis en {URL_CLAVE}   2) Guárdala con:  ./tpi clave"


def archivo_env() -> Path:
    return raiz_proyecto() / ".env"


def obtener_clave() -> str | None:
    for nombre in NOMBRES_CLAVE:
        if os.environ.get(nombre, "").strip():
            return os.environ[nombre].strip()
    ruta = archivo_env()
    if ruta.exists():
        from dotenv import dotenv_values

        valores = dotenv_values(ruta)
        for nombre in NOMBRES_CLAVE:
            if (valores.get(nombre) or "").strip():
                return str(valores[nombre]).strip()
    return None


def clave_obligatoria() -> str:
    clave = obtener_clave()
    if not clave:
        raise ErrorMotor("Falta la clave de Gemini para redactar con IA.", ayuda=AYUDA_CLAVE)
    return clave


def guardar_clave(clave: str) -> Path:
    """Guarda (o reemplaza) GEMINI_API_KEY en .env, solo legible por tu usuario."""
    clave = clave.strip()
    if not clave or any(c.isspace() for c in clave):
        raise ErrorMotor(
            "Esa clave está vacía o tiene espacios.", ayuda=f"Cópiala de nuevo desde {URL_CLAVE}"
        )
    ruta = archivo_env()
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
    lineas = [ln for ln in lineas if not ln.strip().startswith(tuple(f"{n}=" for n in NOMBRES_CLAVE))]
    lineas.append(f"GEMINI_API_KEY={clave}")
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    ruta.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
    return ruta


def cliente(clave: str | None = None) -> Any:
    from google import genai
    from google.genai import types

    reintentos = types.HttpRetryOptions(
        attempts=3, initial_delay=2.0, max_delay=20.0, http_status_codes=[429, 500, 502, 503, 504]
    )
    return genai.Client(
        api_key=clave or clave_obligatoria(),
        http_options=types.HttpOptions(timeout=15 * 60 * 1000, retry_options=reintentos),  # ms
    )


def explicar_error(error: Exception, modelo: str) -> ErrorMotor:
    """Convierte errores de la API o de la red en mensajes claros."""
    from google.genai import errors

    if isinstance(error, errors.APIError):
        codigo = getattr(error, "code", None)
        mensaje = str(getattr(error, "message", "") or error)
        if codigo in (400, 401, 403) and ("API key" in mensaje or "API_KEY" in mensaje or codigo == 401):
            return ErrorMotor("Gemini rechazó la clave (no es válida o fue borrada).", ayuda=AYUDA_CLAVE)
        if codigo == 403:
            if modelo == MODELO_POR_DEFECTO:
                # El modelo por defecto negado es un corte del proyecto, no un error del comando.
                return ErrorMotor(
                    f"Google le cortó el acceso al proyecto de tu clave ({mensaje}).",
                    ayuda=f"No es el modelo ni el comando: es tu cuenta de Google. Entra a {URL_CLAVE}, "
                    "revisa el estado del proyecto y crea una clave nueva. Después: ./tpi clave",
                )  # fmt: skip
            return ErrorMotor(
                f"Tu clave no tiene permiso para usar «{modelo}» ({mensaje}).",
                ayuda=f"Prueba con --modelo {MODELO_POR_DEFECTO} o revisa tu cuenta en {URL_CLAVE}",
            )
        if codigo == 404:
            return ErrorMotor(
                f"El modelo «{modelo}» no existe o no está disponible para tu clave.",
                ayuda=f"Prueba con --modelo {MODELO_POR_DEFECTO}",
            )
        if codigo == 429:
            return ErrorMotor(
                "Llegaste al límite de uso de Gemini por ahora.",
                ayuda="Espera un par de minutos y repite (si es el límite diario, mañana).",
            )
        if codigo and codigo >= 500:
            return ErrorMotor(
                "El servicio de Gemini está con problemas en este momento.",
                ayuda="Intenta de nuevo en unos minutos.",
            )
        return ErrorMotor(f"Gemini respondió con un error ({codigo}): {mensaje[:300]}")
    nombre = type(error).__name__
    if "Timeout" in nombre or "Connect" in nombre or "Network" in nombre or isinstance(error, OSError):
        return ErrorMotor("No pude conectarme con Gemini.", ayuda="Revisa tu conexión a internet y repite.")
    return ErrorMotor(f"Error inesperado al hablar con Gemini: {error}")


def probar_clave(clave: str, modelo: str = MODELO_POR_DEFECTO) -> None:
    """Comprueba la clave sin gastar cuota de generación (consulta los datos del modelo)."""
    conexion = cliente(clave)  # guardar la referencia: si el cliente se libera, cierra su conexión
    try:
        conexion.models.get(model=modelo)
    except Exception as e:
        raise explicar_error(e, modelo) from e
