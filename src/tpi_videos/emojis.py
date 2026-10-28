"""Emojis 3D (Noto Emoji 3D, licencia OFL) y stickers propios para los videos.

En el guion, el campo ``emoji:`` acepta:
- el emoji mismo: ``emoji: "🤯"``
- su nombre en español: ``emoji: explota``
- una imagen propia (PNG con fondo transparente) guardada en ``mis_ajustes/stickers/``:
  ``emoji: robot`` usa ``mis_ajustes/stickers/robot.png``. Una imagen propia tiene prioridad sobre un
  nombre de emoji igual.
"""

from __future__ import annotations

import re
from pathlib import Path

from .entorno import PAQUETE, raiz_proyecto

EMOJIS_DIR = PAQUETE / "assets" / "emojis"

# emoji → nombre (el archivo es assets/emojis/<nombre>.png)
EMOJIS: dict[str, str] = {
    "🤯": "explota", "🚨": "alerta", "✅": "correcto", "❌": "incorrecto", "⚠️": "cuidado",
    "💡": "idea", "🔥": "fuego", "👀": "mira", "🤔": "piensa", "😱": "sorpresa",
    "😮": "asombro", "😅": "uff", "🫣": "nervios", "😎": "genial", "🤓": "nerd",
    "🥳": "logrado", "👏": "aplausos", "🙌": "celebra", "🙋": "yo", "💪": "fuerza",
    "👉": "apunta", "👇": "abajo", "🎯": "objetivo", "📌": "importante", "❓": "pregunta",
    "❗": "exclamacion", "💯": "cien", "⭐": "estrella", "🏆": "trofeo", "🎉": "fiesta",
    "🚀": "cohete", "🧠": "cerebro", "✍️": "escribe", "📝": "apuntes", "📚": "libros",
    "📐": "escuadra", "📏": "regla", "🧮": "abaco", "🔢": "numeros", "➕": "suma",
    "➖": "resta", "✖️": "multiplica", "➗": "divide", "📈": "sube", "📉": "baja",
    "⏱️": "cronometro", "⚡": "rayo", "🔌": "enchufe", "🔋": "bateria", "💥": "choque",
    "🧲": "iman", "🌡️": "termometro", "⚙️": "engranaje", "🔧": "llave", "🏗️": "construccion",
    "🤖": "robot", "🌍": "tierra", "🪨": "piedra", "💧": "agua", "🚗": "auto",
    "🚌": "bus", "🏃": "corre",
}  # fmt: skip

_VARIACION = "\ufe0f"  # selector que algunos teclados agregan (⚙ vs ⚙️)

# Emojis y símbolos gráficos más comunes (caras, objetos, transporte, ✓ ✅ ⚡ ⭐…). Dentro de un texto
# no se dibujan bien (las letras no los traen) y en la voz se leerían en voz alta.
PATRON_EMOJI = re.compile("[\U0001f300-\U0001faff\u2600-\u27bf\u2b50\u2b55\u23e9-\u23fa]")
_INVISIBLES = re.compile("[\ufe0f\u200d]")
_POR_EMOJI = {e.replace(_VARIACION, ""): n for e, n in EMOJIS.items()}
_POR_NOMBRE = {n: e for e, n in EMOJIS.items()}


def stickers_dir() -> Path:
    return raiz_proyecto() / "mis_ajustes" / "stickers"


def stickers_disponibles(carpeta: Path | None = None) -> list[str]:
    """Los stickers propios subidos, por nombre (sin ``.png``), para elegirlos en el panel."""
    base = carpeta if carpeta is not None else stickers_dir()
    return sorted(p.stem for p in base.glob("*.png")) if base.exists() else []


def _normalizar(valor: str) -> str:
    return valor.strip().replace(_VARIACION, "")


def resolver(valor: str | None) -> Path | None:
    """Ruta del PNG para ``valor`` (emoji, nombre o sticker propio), o None si no existe."""
    if not valor or not valor.strip():
        return None
    limpio = _normalizar(valor)
    if limpio in _POR_EMOJI:
        ruta = EMOJIS_DIR / f"{_POR_EMOJI[limpio]}.png"
        return ruta if ruta.exists() else None
    nombre = limpio.lower()
    propio = stickers_dir() / f"{nombre}.png"
    if propio.exists():
        return propio
    if nombre in _POR_NOMBRE:
        ruta = EMOJIS_DIR / f"{nombre}.png"
        return ruta if ruta.exists() else None
    return None


def es_valido(valor: str | None) -> bool:
    return not valor or resolver(valor) is not None


_RACHA = re.compile(f"(?:{PATRON_EMOJI.pattern}|{_INVISIBLES.pattern})+")


def quitar_emojis(texto: str) -> str:
    """El texto sin emojis (para lo que escribe la IA: los emojis van en su propio campo)."""
    sin_pegados = re.sub(rf"\s*{_RACHA.pattern}(?=[.,;:!?…])", "", texto)  # "error 😱." → "error."
    return " ".join(_RACHA.sub(" ", sin_pegados).split())


def lista_para_ia() -> str:
    """Los emojis disponibles, en una línea, para las instrucciones de la IA."""
    return " ".join(EMOJIS)


def normalizar_para_ia(valor: str | None) -> str | None:
    """Acepta solo emojis del catálogo (la IA no puede usar stickers ni inventar)."""
    if not valor:
        return None
    limpio = _normalizar(valor)
    if limpio in _POR_EMOJI:
        return next(e for e in EMOJIS if e.replace(_VARIACION, "") == limpio)
    if limpio.lower() in _POR_NOMBRE:
        return _POR_NOMBRE[limpio.lower()]
    return None
