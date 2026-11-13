"""La voz de Gemini (Gemini TTS): natural, y se le puede pedir el tono con palabras.

Usa la misma clave de Gemini que el redactor. A diferencia de edge-tts no entrega el tiempo de cada
palabra: los subtítulos se sincronizan con Whisper si está instalado y, si no, se reparten sobre la
duración real del audio. Este módulo no depende de Manim (se prueba sin él); el servicio que usa la
escena está en ``voces.GeminiTTSService``.
"""

from __future__ import annotations

import base64
import re
from typing import Any

from .errores import ErrorMotor

MODELO_TTS = "gemini-3.8-flash-tts"
SEGUNDOS_DE_ESPERA = 45  # por frase: más que esto es que Gemini no está respondiendo
# Límite de RELOJ por frase. El timeout del SDK es por lectura: una respuesta que gotea un byte cada
# pocos segundos (o una conexión medio cerrada) no lo dispara nunca y el video queda colgado. Con 2
# intentos de 45 s y sus pausas, 2 minutos sin audio ya es que no va a llegar.
LIMITE_POR_FRASE = 120.0
VOZ_POR_DEFECTO = "Charon"  # «Informative»: la que más suena a profesor explicando

# Las 30 voces de estudio de Gemini y su carácter (docs: Text-to-speech · Voice options).
VOCES: dict[str, str] = {
    "Zephyr": "luminosa", "Puck": "animada", "Charon": "informativa", "Kore": "firme",
    "Fenrir": "entusiasta", "Leda": "juvenil", "Orus": "firme", "Aoede": "ligera",
    "Callirrhoe": "relajada", "Autonoe": "luminosa", "Enceladus": "susurrante", "Iapetus": "clara",
    "Umbriel": "relajada", "Algieba": "suave", "Despina": "suave", "Erinome": "clara",
    "Algenib": "grave", "Rasalgethi": "informativa", "Laomedeia": "animada", "Achernar": "suave",
    "Alnilam": "firme", "Schedar": "pareja", "Gacrux": "madura", "Pulcherrima": "directa",
    "Achird": "amistosa", "Zubenelgenubi": "casual", "Vindemiatrix": "amable", "Sadachbia": "vivaz",
    "Sadaltager": "sabia", "Sulafat": "cálida",
}  # fmt: skip

ESTILO_POR_DEFECTO = (
    "Profesor chileno joven y cercano, con acento chileno suave, que le explica a un estudiante de "
    "enseñanza media. Habla con calma y claridad, como conversando, sin leer: marca las pausas entre "
    "ideas, sube el ánimo en los descubrimientos y nunca suena a locutor de radio."
)


def es_voz_de_gemini(nombre: str | None) -> bool:
    nombre = (nombre or "").strip()
    return nombre in VOCES or nombre.startswith(("voice_", "voicekey_"))  # las propias (diseñadas o clonadas)


def voz_de_gemini(nombre: str | None) -> str:
    """La voz pedida si es de Gemini; si es una voz de edge («es-CL-LorenzoNeural») o nada, la de siempre."""
    return nombre.strip() if es_voz_de_gemini(nombre) else VOZ_POR_DEFECTO  # type: ignore[union-attr]


def estilo_con_ritmo(estilo: str | None, velocidad: str | None) -> str:
    """Gemini no tiene un control de velocidad en porcentaje: el ritmo se le pide con palabras."""
    texto = (estilo or "").strip() or ESTILO_POR_DEFECTO
    m = re.fullmatch(r"([+-])(\d{1,3})%", (velocidad or "").strip())
    if m:
        cuanto = int(m.group(2)) * (1 if m.group(1) == "+" else -1)
        if cuanto >= 10:
            texto += " Ritmo ágil."
        elif cuanto <= -10:
            texto += " Ritmo pausado, sin apuro."
    return texto


def _audio_de(respuesta: Any) -> bytes:
    """El WAV de la respuesta: ``output_audio`` en el SDK; si no viene, el último bloque de audio."""
    audio = getattr(respuesta, "output_audio", None)
    datos = getattr(audio, "data", None)
    if not datos:
        for paso in reversed(list(getattr(respuesta, "steps", None) or [])):
            for parte in reversed(list(getattr(paso, "content", None) or [])):
                if getattr(parte, "type", None) == "audio" and getattr(parte, "data", None):
                    datos = parte.data
                    break
            if datos:
                break
    if not datos:
        raise ErrorMotor(
            "Gemini no devolvió audio para la voz.",
            ayuda="Repite el comando; si sigue pasando, usa por ahora --voz edge.",
            transitorio=True,
        )
    return base64.b64decode(datos) if isinstance(datos, str) else bytes(datos)


def cliente_tts() -> Any:
    from google import genai
    from google.genai import types

    from .ia import clave_obligatoria

    # Una frase se sintetiza en segundos: si Gemini no responde en 45 s, algo pasa. Con 2 intentos, el
    # peor caso es ~1,5 min de espera antes del aviso, no los 15 que daban 3 intentos de 5 min.
    reintentos = types.HttpRetryOptions(
        attempts=2, initial_delay=2.0, max_delay=10.0, http_status_codes=[429, 500, 502, 503, 504]
    )
    return genai.Client(
        api_key=clave_obligatoria(),
        http_options=types.HttpOptions(
            api_version="v1beta", timeout=SEGUNDOS_DE_ESPERA * 1000, retry_options=reintentos
        ),
    )


def sintetizar(
    texto: str, voz: str = VOZ_POR_DEFECTO, estilo: str = ESTILO_POR_DEFECTO,
    modelo: str = MODELO_TTS, cliente: Any = None,
) -> bytes:  # fmt: skip
    """El audio WAV (24 kHz, mono) de ``texto`` dicho por ``voz`` con el tono de ``estilo``."""
    from . import ia

    cliente = cliente or cliente_tts()

    def pedir() -> Any:
        return cliente.interactions.create(
            model=modelo,
            input=[
                {
                    "type": "user_input",
                    "content": [
                        {
                            "type": "text",
                            "text": texto,
                            "annotations": [{"type": "speech_metadata", "style": estilo}],
                        }
                    ],
                }
            ],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voz}]},
        )

    try:
        respuesta = _con_limite(pedir, LIMITE_POR_FRASE)
    except ErrorMotor:
        raise
    except Exception as e:
        error = ia.explicar_error(e, modelo)
        error.ayuda = (error.ayuda + " " if error.ayuda else "") + "Mientras tanto puedes usar --voz edge."
        raise error from e
    return _audio_de(respuesta)


def _con_limite(funcion: Any, segundos: float) -> Any:
    """Corre ``funcion`` en un hilo aparte y no la espera más de ``segundos``.

    Si se pasa, avisa (ErrorMotor transitorio) en vez de colgar el video. El hilo colgado queda como
    daemon: no impide que el proceso termine.
    """
    import threading

    salida: dict[str, Any] = {}

    def correr() -> None:
        try:
            salida["valor"] = funcion()
        except BaseException as e:  # se relanza en el hilo principal
            salida["error"] = e

    hilo = threading.Thread(target=correr, name="voz-gemini", daemon=True)
    hilo.start()
    hilo.join(segundos)
    if hilo.is_alive():
        raise ErrorMotor(
            f"La voz de Gemini no respondió en {segundos:.0f} s para una frase.",
            ayuda="Repite el comando en un rato. Mientras tanto puedes usar --voz edge.",
            transitorio=True,
        )
    if "error" in salida:
        raise salida["error"]
    return salida["valor"]
