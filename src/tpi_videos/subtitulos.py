"""Subtítulos estilo CapCut: pocas palabras grandes, la palabra que suena en color.

Flujo:
1. Cada bloque de voz trae su texto exacto (del guion) y su posición en el video.
2. Se obtiene el tiempo de cada palabra desde la mejor fuente disponible:
   - ``voz``: marcas exactas del sintetizador (edge-tts),
   - ``whisper``: Whisper escucha el audio y se alinea con el texto del guion,
   - ``estimado``: reparto proporcional al largo de cada palabra.
3. Se agrupan en "páginas" de 1–3 palabras y se escribe un archivo ASS que FFmpeg quema.

Siempre se muestra el texto EXACTO del guion (Whisper solo aporta los tiempos), así no
aparecen errores de transcripción en pantalla.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import EstiloSubtitulos
from .errores import ErrorMotor
from .guion import sin_tildes

MODOS = ("auto", "voz", "whisper", "estimado")


@dataclass
class Palabra:
    texto: str
    inicio: float
    fin: float


def _normalizar(palabra: str) -> str:
    return re.sub(r"[^0-9a-z]", "", sin_tildes(palabra.lower()))


def _repartir(palabras: list[str], inicio: float, fin: float) -> list[tuple[float, float]]:
    pesos = [len(p) + 1 for p in palabras]
    total = sum(pesos) or 1
    tiempos, t = [], inicio
    for peso in pesos:
        d = (fin - inicio) * peso / total
        tiempos.append((t, t + d))
        t += d
    return tiempos


def alinear(
    guion: list[str], reconocidas: list[tuple[str, float, float]], duracion: float
) -> list[tuple[float, float]]:
    """Asigna a cada palabra del guion un (inicio, fin) usando las palabras reconocidas.

    Coincidencias exactas copian el tiempo; tramos distintos (ej. "veinte" vs "20") reparten
    el tiempo reconocido; lo que falte se interpola entre vecinos.
    """
    n = len(guion)
    if n == 0:
        return []
    if not reconocidas:
        return _repartir(guion, 0.1, max(duracion - 0.1, 0.2))

    a = [_normalizar(p) for p in guion]
    b = [_normalizar(p) for p, _, _ in reconocidas]
    tiempos: list[tuple[float, float] | None] = [None] * n
    for tipo, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tipo == "equal":
            for k in range(i2 - i1):
                _, ini, fin = reconocidas[j1 + k]
                tiempos[i1 + k] = (ini, fin)
        elif tipo == "replace":
            ini, fin = reconocidas[j1][1], reconocidas[j2 - 1][2]
            for k, par in enumerate(_repartir(guion[i1:i2], ini, max(fin, ini + 0.05))):
                tiempos[i1 + k] = par

    i = 0
    while i < n:  # rellenar huecos
        if tiempos[i] is not None:
            i += 1
            continue
        j = i
        while j < n and tiempos[j] is None:
            j += 1
        ini = tiempos[i - 1][1] if i > 0 else 0.05  # type: ignore[index]
        fin = tiempos[j][0] if j < n else max(duracion - 0.05, ini + 0.1)  # type: ignore[index]
        if fin - ini < 0.06 * (j - i):
            fin = ini + 0.06 * (j - i)
        for k, par in enumerate(_repartir(guion[i:j], ini, fin)):
            tiempos[i + k] = par
        i = j

    resultado, previo = [], 0.0
    for ini, fin in tiempos:  # type: ignore[misc]
        ini = max(ini, previo)
        fin = max(fin, ini + 0.06)
        resultado.append((ini, fin))
        previo = ini
    return resultado


def _fuente_de_marcas(modo: str, bloque: dict[str, Any], whisper_ok: bool) -> str:
    if modo == "estimado":
        return "estimado"
    if modo == "voz":
        return "voz" if bloque.get("palabras") else "estimado"
    if modo == "whisper":
        if not whisper_ok:
            raise ErrorMotor(
                "Pediste sincronizar con Whisper, pero Whisper no está instalado.",
                ayuda='Instálalo con: .venv/bin/pip install -e ".[whisper]"  (o usa --sincronizar auto)',
            )
        return "whisper"
    # auto: exactas > whisper (si hay voz real) > estimadas
    if bloque.get("marcas") == "exactas":
        return "voz"
    if whisper_ok and bloque.get("servicio") not in (None, "silencio"):
        return "whisper"
    return "voz" if bloque.get("palabras") else "estimado"


def palabras_de_bloques(
    bloques: list[dict[str, Any]], modo: str = "auto", modelo: str = "base"
) -> tuple[list[Palabra], set[str]]:
    """Palabras con tiempo absoluto en el video, y las fuentes de tiempo usadas."""
    from . import whisper_sync

    # Cargar Whisper (PyTorch) tarda: solo se consulta si algún bloque lo necesita.
    necesita = modo == "whisper" or (modo == "auto" and any(b.get("marcas") != "exactas" for b in bloques))
    whisper_ok = necesita and whisper_sync.disponible()
    palabras: list[Palabra] = []
    fuentes: set[str] = set()
    for bloque in bloques:
        guion = bloque["texto"].split()
        fuente = _fuente_de_marcas(modo, bloque, whisper_ok)
        if fuente == "voz":
            reconocidas = [(p["texto"], p["inicio"], p["fin"]) for p in bloque["palabras"]]
        elif fuente == "whisper":
            reconocidas = whisper_sync.transcribir(
                Path(bloque["audio"]), modelo=modelo, prompt=bloque["texto"]
            )
        else:
            reconocidas = []
        fuentes.add(fuente)
        for texto, (ini, fin) in zip(guion, alinear(guion, reconocidas, bloque["duracion"]), strict=True):
            palabras.append(Palabra(texto, bloque["inicio"] + ini, bloque["inicio"] + fin))
    return palabras, fuentes


# ------------------------------------------------------------------------------------------
# Agrupación y archivos ASS / SRT
# ------------------------------------------------------------------------------------------

_FIN_DE_FRASE = re.compile(r"[.,;:!?…]$")


def limpiar(palabra: str, mayusculas: bool = False) -> str:
    limpia = palabra.strip("\"'«»“”").rstrip(".,;:…")
    limpia = limpia.replace("{", "(").replace("}", ")").replace("\\", "/")
    return limpia.upper() if mayusculas else limpia


def agrupar(
    palabras: list[Palabra], max_palabras: int, max_caracteres: int, pausa: float = 0.45
) -> list[list[Palabra]]:
    grupos: list[list[Palabra]] = []
    actual: list[Palabra] = []
    for p in palabras:
        if not limpiar(p.texto):
            continue
        if actual:
            largo = sum(len(limpiar(x.texto)) + 1 for x in actual) + len(limpiar(p.texto))
            if (
                len(actual) >= max_palabras
                or largo > max_caracteres
                or p.inicio - actual[-1].fin > pausa
                or _FIN_DE_FRASE.search(actual[-1].texto)
            ):
                grupos.append(actual)
                actual = []
        actual.append(p)
    if actual:
        grupos.append(actual)
    return grupos


def _color_ass(hex_rgb: str, alfa: int = 0) -> str:
    """Color para la línea de estilo: &HAABBGGRR (ASS guarda los colores al revés)."""
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"&H{alfa:02X}{b}{g}{r}".upper()


def _color_etiqueta(hex_rgb: str) -> str:
    """Color para una etiqueta en línea: \\c&HBBGGRR&."""
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"&H{b}{g}{r}&".upper()


def _tiempo_ass(segundos: float) -> str:
    cs = max(0, round(segundos * 100))
    h, resto = divmod(cs, 360000)
    m, resto = divmod(resto, 6000)
    s, cs = divmod(resto, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def escribir_ass(
    grupos: list[list[Palabra]], ruta: Path, estilo: EstiloSubtitulos, ancho: int = 1080, alto: int = 1920
) -> Path:
    x, y = ancho // 2, round(alto * estilo.posicion_y)
    blanco = _color_ass(estilo.color)
    normal = _color_etiqueta(estilo.color)
    activo = _color_etiqueta(estilo.color_activo if estilo.resaltar else estilo.color)
    lineas = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {ancho}",
        f"PlayResY: {alto}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: CapCut,{estilo.fuente},{estilo.tamano},{blanco},{blanco},&H00000000,&H78000000,0,0,0,0,"
        f"100,100,1,0,1,{estilo.borde},{estilo.sombra},5,80,80,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for gi, grupo in enumerate(grupos):
        siguiente = grupos[gi + 1][0].inicio if gi + 1 < len(grupos) else None
        fin_grupo = grupo[-1].fin + 0.15
        if siguiente is not None:
            # si la próxima página llega pronto, se empalma (sin parpadeo); si no, se apaga
            fin_grupo = siguiente if siguiente - grupo[-1].fin < 0.3 else min(fin_grupo, siguiente)
        textos = [limpiar(p.texto, estilo.mayusculas) for p in grupo]
        for k, palabra in enumerate(grupo):
            inicio = grupo[0].inicio if k == 0 else palabra.inicio
            fin = grupo[k + 1].inicio if k + 1 < len(grupo) else fin_grupo
            if fin - inicio < 0.02:
                continue
            piezas = [f"{{\\c{activo}}}{t}{{\\c{normal}}}" if j == k else t for j, t in enumerate(textos)]
            salto = "\\fscx80\\fscy80\\t(0,90,\\fscx100\\fscy100)" if k == 0 else ""
            lineas.append(
                f"Dialogue: 0,{_tiempo_ass(inicio)},{_tiempo_ass(fin)},CapCut,,0,0,0,,"
                f"{{\\an5\\pos({x},{y}){salto}}}{' '.join(piezas)}"
            )
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


def _tiempo_srt(segundos: float) -> str:
    ms = max(0, round(segundos * 1000))
    h, resto = divmod(ms, 3_600_000)
    m, resto = divmod(resto, 60_000)
    s, ms = divmod(resto, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _partir_parejo(palabras: list[Palabra], partes: int) -> list[list[Palabra]]:
    """Divide en ``partes`` tramos de largo parecido (sin dejar fragmentos sueltos)."""
    if partes <= 1 or len(palabras) <= 1:
        return [palabras]
    total = sum(len(p.texto) + 1 for p in palabras)
    tramos: list[list[Palabra]] = [[]]
    acumulado = 0
    for p in palabras:
        meta = total * len(tramos) / partes
        if tramos[-1] and len(tramos) < partes and acumulado + (len(p.texto) + 1) / 2 > meta:
            tramos.append([])
        tramos[-1].append(p)
        acumulado += len(p.texto) + 1
    return tramos


def escribir_srt(palabras: list[Palabra], ruta: Path, max_linea: int = 42) -> Path:
    """Subtítulos clásicos para subir a YouTube: frases completas, hasta 2 líneas de 42 letras."""
    frases: list[list[Palabra]] = []
    actual: list[Palabra] = []
    for p in palabras:
        if actual and p.inicio - actual[-1].fin > 0.6:
            frases.append(actual)
            actual = []
        actual.append(p)
        if re.search(r"[.!?]$", p.texto):
            frases.append(actual)
            actual = []
    if actual:
        frases.append(actual)

    bloques = []
    for frase in frases:
        largo = len(" ".join(p.texto for p in frase))
        for entrada in _partir_parejo(frase, -(-largo // (2 * max_linea))):
            texto = " ".join(p.texto for p in entrada)
            if len(texto) > max_linea:
                texto = "\n".join(" ".join(p.texto for p in linea) for linea in _partir_parejo(entrada, 2))
            bloques.append((entrada[0].inicio, entrada[-1].fin + 0.1, texto))
    salida = []
    for i, (ini, fin, texto) in enumerate(bloques, 1):
        if i < len(bloques):
            fin = min(fin, bloques[i][0])  # sin superposición con la siguiente
        salida.append(f"{i}\n{_tiempo_srt(ini)} --> {_tiempo_srt(fin)}\n{texto}\n")
    ruta.write_text("\n".join(salida), encoding="utf-8")
    return ruta
