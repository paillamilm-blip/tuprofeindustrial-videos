"""Los dos públicos del canal y sus niveles: enseñanza media y universidad de ingeniería.

Solo biblioteca estándar: lo usan el motor, la IA, «Para hoy» y Ajustes. El nivel del guion sigue
siendo texto libre; acá se lee con tolerancia («3 medio», «2º Medio», «segundo año de ingeniería»).
"""

from __future__ import annotations

import re
import unicodedata

PUBLICOS = {"media": "Enseñanza media", "universidad": "Universidad (ingeniería)"}
NIVELES_MEDIA = ("1° medio", "2° medio", "3° medio", "4° medio")
NIVELES_UNIVERSIDAD = ("1° año ingeniería", "2° año ingeniería", "3° año ingeniería", "4° año ingeniería")
NIVELES = NIVELES_MEDIA + NIVELES_UNIVERSIDAD
CARRERAS = {
    "industrial": "Ing. Civil Industrial",
    "electrica": "Ing. Civil Eléctrica",
    "obras_civiles": "Ing. en Obras Civiles",
}
CARRERA_CORTA = {"industrial": "Industrial", "electrica": "Eléctrica", "obras_civiles": "Obras Civiles"}

_ORDINALES = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4, "quinto": 5}
# «º» (ordinal) sale como «o» al quitar tildes: «2º medio» → «2o medio».
_MEDIO = re.compile(r"\b([1-4])\s*[°ºo]?\s*(?:ano\s+)?(?:de\s+)?medio\b")
_ANO = re.compile(r"\b([1-6])\s*[°ºo]?\s*ano\b")
_ANO_ESCRITO = re.compile(r"\b(primero?|segundo|tercero?|cuarto|quinto)\s+ano\b")
_UNIVERSIDAD = re.compile(r"ingenier|universi|carrera|plan comun")


def _limpio(texto: str) -> str:
    sin = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return sin.lower()


def normalizar(texto: str | None) -> str | None:
    """El nivel en su forma de catálogo («3° medio», «2° año ingeniería»), o None si no es claro.

    El 5° y 6° año de las carreras largas cuentan como 4° año: la especialidad final es un nivel.
    """
    limpio = _limpio(str(texto or ""))
    if m := _MEDIO.search(limpio):
        return f"{m.group(1)}° medio"
    if not _UNIVERSIDAD.search(limpio):
        return None
    if m := _ANO.search(limpio):
        numero = int(m.group(1))
    elif m := _ANO_ESCRITO.search(limpio):
        numero = _ORDINALES[m.group(1)]
    else:
        return None
    return f"{min(numero, 4)}° año ingeniería"


def publico_de(nivel: str | None) -> str | None:
    clave = normalizar(nivel) if nivel not in NIVELES else nivel
    if clave in NIVELES_MEDIA:
        return "media"
    if clave in NIVELES_UNIVERSIDAD:
        return "universidad"
    return None


def es_universidad(nivel: str | None) -> bool:
    return publico_de(nivel) == "universidad"


def nombre_carrera(clave: str | None) -> str:
    return CARRERAS.get(clave or "", clave or "")
