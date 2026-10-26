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
MODELOS_GRATUITOS = (
    # Google lleva la cuenta diaria por modelo, no por clave: si uno se agota, el siguiente
    # todavía tiene cupo propio. Son los escalones de respaldo del nivel gratuito.
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
)
NOMBRES_CLAVE = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
URL_CLAVE = "https://aistudio.google.com/apikey"
AYUDA_CLAVE = f"1) Créala gratis en {URL_CLAVE}   2) Guárdala con:  ./tpi clave"
URL_CUOTA = "https://ai.dev/rate-limit"


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


def cliente(clave: str | None = None, *, con_reintentos: bool = True) -> Any:
    """Conexión con Gemini. Sin reintentos para sondear cupos: ahí reintentar es perder un minuto.

    El cliente hay que dejarlo en una variable: si se libera, cierra su conexión y el siguiente
    pedido falla con «Cannot send a request, as the client has been closed».
    """
    from google import genai
    from google.genai import types

    reintentos = (
        types.HttpRetryOptions(
            attempts=3, initial_delay=2.0, max_delay=20.0, http_status_codes=[429, 500, 502, 503, 504]
        )
        if con_reintentos
        else None
    )
    return genai.Client(
        api_key=clave or clave_obligatoria(),
        http_options=types.HttpOptions(timeout=15 * 60 * 1000, retry_options=reintentos),  # ms
    )


def cadena_desde(modelo: str) -> list[str]:
    """El modelo pedido primero y después los demás gratuitos, sin repetir ninguno."""
    return [modelo, *[m for m in MODELOS_GRATUITOS if m != modelo]]


def es_cuota_agotada(error: Exception) -> bool:
    """Si Gemini contestó 429: esperando se levanta, pero cambiando de modelo se levanta ya."""
    from google.genai import errors

    return isinstance(error, errors.APIError) and getattr(error, "code", None) == 429


def saturado(error: Exception) -> bool:
    """5xx: ese modelo está saturado o caído ahora. Otro gratuito puede estar mejor."""
    from google.genai import errors

    codigo = getattr(error, "code", None) if isinstance(error, errors.APIError) else None
    return bool(codigo) and codigo >= 500


def vale_probar_otro_modelo(error: Exception) -> bool:
    """Cuota agotada o saturación son problemas de ESE modelo; un 400 lo sería de todos."""
    return es_cuota_agotada(error) or saturado(error)


def estado_de_cuota(conexion: Any, modelos: list[str]) -> list[tuple[str, str]]:
    """(modelo, estado) con una pregunta de dos palabras por modelo."""
    from google.genai import types

    config = types.GenerateContentConfig(
        max_output_tokens=16, thinking_config=types.ThinkingConfig(thinking_level="low")
    )
    estados: list[tuple[str, str]] = []
    for modelo in modelos:
        try:
            conexion.models.generate_content(model=modelo, contents="Responde solo: OK", config=config)
        except Exception as e:  # noqa: BLE001 - esto es un diagnóstico, no interrumpe nada
            if es_cuota_agotada(e):
                estados.append((modelo, "sin cupo"))
            elif saturado(e):
                estados.append((modelo, "saturado"))
            else:
                estados.append((modelo, "bloqueado"))
        else:
            estados.append((modelo, "ok"))
    return estados


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
                transitorio=True,  # es la cuota: esperando se levanta
            )
        if codigo and codigo >= 500:
            return ErrorMotor(
                "El servicio de Gemini está con problemas en este momento.",
                ayuda="Intenta de nuevo en unos minutos.",
                transitorio=True,
            )
        return ErrorMotor(f"Gemini respondió con un error ({codigo}): {mensaje[:300]}")
    nombre = type(error).__name__
    if "Timeout" in nombre or "Connect" in nombre or "Network" in nombre or isinstance(error, OSError):
        return ErrorMotor(
            "No pude conectarme con Gemini.",
            ayuda="Revisa tu conexión a internet y repite.",
            transitorio=True,
        )  # fmt: skip
    return ErrorMotor(f"Error inesperado al hablar con Gemini: {error}")


def probar_clave(clave: str, modelo: str = MODELO_POR_DEFECTO) -> None:
    """Comprueba la clave sin gastar cuota de generación (consulta los datos del modelo)."""
    conexion = cliente(clave)  # guardar la referencia: si el cliente se libera, cierra su conexión
    try:
        conexion.models.get(model=modelo)
    except Exception as e:
        raise explicar_error(e, modelo) from e
