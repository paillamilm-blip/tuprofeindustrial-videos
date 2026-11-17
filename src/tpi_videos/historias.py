"""Generador de historias para Instagram y TikTok en formato vertical (1080×1920).

Crea dos imágenes de historias automáticas listas para subir:
1. ``historia_01_encuesta.png``: Reto interactivo con la fórmula y opciones A y B para el sticker de encuesta.
2. ``historia_02_clases.png``: Tarjeta de llamado a la acción para clases particulares PAES
   (online para todo Chile y presencial en toda la Región Metropolitana).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw, ImageFont

from .entorno import raiz_proyecto
from .guion import Guion

ANCHO = 1080
ALTO = 1920

COLOR_FONDO = (14, 20, 27)        # Slate oscuro #0e141b
COLOR_LINEA_GRID = (22, 32, 44)   # Cuadrícula sutil
COLOR_AMBAR = (245, 158, 11)      # Ámbar de marca #f59e0b
COLOR_CELESTE = (56, 189, 248)    # Celeste acento #38bdf8
COLOR_TEXTO = (241, 245, 249)     # Blanco suave #f1f5f9
COLOR_TARJETA = (26, 36, 48)      # Tarjeta sólida
COLOR_BORDE = (71, 85, 105)       # Borde sobrio
COLOR_TENUE = (148, 163, 184)     # Gris lectura


def _fuentes() -> tuple[str, str, str]:
    carpeta = raiz_proyecto() / "src" / "tpi_videos" / "assets" / "fuentes"
    bold = str(carpeta / "Montserrat-Black.ttf")
    semi = str(carpeta / "Montserrat-SemiBold.ttf")
    extra = str(carpeta / "Montserrat-ExtraBold.ttf")
    return bold, semi, extra


def _fondo_base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (ANCHO, ALTO), color=COLOR_FONDO)
    draw = ImageDraw.Draw(img)
    # Cuadrícula técnica sutil
    for x in range(0, ANCHO, 40):
        draw.line([(x, 0), (x, ALTO)], fill=COLOR_LINEA_GRID, width=1)
    for y in range(0, ALTO, 40):
        draw.line([(0, y), (ANCHO, y)], fill=COLOR_LINEA_GRID, width=1)
    return img, draw


def _limpiar_tex(tex: str) -> str:
    """Quita comandos LaTeX para dibujarlo limpio en texto sin distorsión."""
    tex = re.sub(r"\\(?:neq|ne)", "≠", tex)
    tex = re.sub(r"\\(?:cdot|times)", "·", tex)
    tex = re.sub(r"\\(?:frac)\{([^}]+)\}\{([^}]+)\}", r"\1/\2", tex)
    tex = re.sub(r"\\(?:sqrt)\{([^}]+)\}", r"√(\1)", tex)
    tex = re.sub(r"\\(?:text|mathrm|mathbf)\{([^}]+)\}", r"\1", tex)
    tex = re.sub(r"\\[a-zA-Z]+", "", tex)
    tex = re.sub(r"[{}]", "", tex)
    return tex.strip()


def crear_historia_encuesta(guion: Guion, destino: Path) -> Path:
    """Genera la historia 1: Reto / Encuesta para Instagram y TikTok."""
    bold, semi, extra = _fuentes()
    img, draw = _fondo_base()

    f_tag = ImageFont.truetype(extra, 36)
    f_title = ImageFont.truetype(bold, 58)
    f_formula = ImageFont.truetype(bold, 78)
    f_opt = ImageFont.truetype(bold, 50)
    f_hint = ImageFont.truetype(semi, 38)
    f_marca = ImageFont.truetype(extra, 34)

    # 1. Badge superior
    etiqueta = "RETO PAES M1" if "paes" in guion.titulo.lower() else "RETO MATEMÁTICO"
    draw.rounded_rectangle([300, 260, 780, 335], radius=35, fill=COLOR_AMBAR)
    draw.text((540, 297), etiqueta, font=f_tag, fill=COLOR_FONDO, anchor="mm")

    # 2. Pregunta
    draw.text((540, 460), "¿Cuánto da al desarrollar", font=f_title, fill=COLOR_TEXTO, anchor="mm")
    draw.text((540, 540), "esta expresión?", font=f_title, fill=COLOR_TEXTO, anchor="mm")

    # 3. Expresión / Fórmula principal
    expresion = _limpiar_tex(guion.gancho.tex or guion.resultado.tex or guion.titulo)
    # Si viene con signo igual o resultado, mostramos solo el miembro izquierdo para preguntar
    if "=" in expresion:
        partes = expresion.split("=")
        expresion = partes[0].strip()
    if len(expresion) > 24:
        expresion = expresion[:22] + "…"

    draw.rounded_rectangle([120, 640, 960, 840], radius=24, fill=COLOR_TARJETA, outline=COLOR_CELESTE, width=3)
    draw.text((540, 740), expresion, font=f_formula, fill=(255, 255, 255), anchor="mm")

    # 4. Opciones de respuesta
    # Buscamos si hay un paso de error para usarlo como la opción trampa
    opcion_error = None
    for p in guion.pasos:
        if p.error and p.tex:
            limpia = _limpiar_tex(p.tex)
            if "=" in limpia:
                limpia = limpia.split("=")[-1].strip()
            opcion_error = limpia
            break

    opcion_correcta = _limpiar_tex(guion.resultado.tex)
    if "=" in opcion_correcta:
        opcion_correcta = opcion_correcta.split("=")[-1].strip()

    op_a = opcion_error or "-x - 3"
    op_b = opcion_correcta or "-x + 3"

    # Opción A
    draw.rounded_rectangle([120, 930, 960, 1070], radius=20, fill=(30, 41, 59), outline=COLOR_BORDE, width=2)
    draw.text((200, 1000), "A)", font=f_opt, fill=COLOR_AMBAR, anchor="mm")
    draw.text((540, 1000), op_a, font=f_opt, fill=COLOR_TEXTO, anchor="mm")

    # Opción B
    draw.rounded_rectangle([120, 1120, 960, 1260], radius=20, fill=(30, 41, 59), outline=COLOR_BORDE, width=2)
    draw.text((200, 1190), "B)", font=f_opt, fill=COLOR_CELESTE, anchor="mm")
    draw.text((540, 1190), op_b, font=f_opt, fill=COLOR_TEXTO, anchor="mm")

    # 5. Indicador para poner el sticker de Instagram encima
    draw.text((540, 1370), "👆 Vota en la encuesta de aquí abajo", font=f_hint, fill=COLOR_TENUE, anchor="mm")
    draw.text((540, 1430), "¿Caíste en la trampa típica?", font=f_hint, fill=COLOR_AMBAR, anchor="mm")

    # 6. Marca inferior
    draw.text((540, 1720), "@tuprofeindustrial", font=f_marca, fill=(100, 116, 139), anchor="mm")

    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, quality=95)
    return destino


def crear_historia_clases(guion: Guion, destino: Path) -> Path:
    """Genera la historia 2: Llamado a la acción para clases particulares PAES."""
    bold, semi, extra = _fuentes()
    img, draw = _fondo_base()

    f_tag = ImageFont.truetype(extra, 36)
    f_big = ImageFont.truetype(bold, 66)
    f_sub = ImageFont.truetype(semi, 42)
    f_item = ImageFont.truetype(semi, 36)
    f_dm = ImageFont.truetype(bold, 46)
    f_marca = ImageFont.truetype(extra, 34)

    # 1. Badge superior
    draw.rounded_rectangle([250, 260, 830, 335], radius=35, fill=COLOR_CELESTE)
    draw.text((540, 297), "CLASES PARTICULARES", font=f_tag, fill=COLOR_FONDO, anchor="mm")

    # 2. Título
    draw.text((540, 460), "PREPARACIÓN PAES", font=f_big, fill=COLOR_AMBAR, anchor="mm")
    draw.text((540, 540), "Matemática M1 & M2", font=f_sub, fill=COLOR_TEXTO, anchor="mm")

    # 3. Tarjeta de beneficios (incluyendo toda la Región Metropolitana)
    draw.rounded_rectangle([110, 640, 970, 1180], radius=24, fill=COLOR_TARJETA, outline=COLOR_BORDE, width=2)
    items = [
        "🎯  Clases 100% personalizadas a tu ritmo",
        "💻  Modalidad Online para todo Chile",
        "📍  Presencial en toda la Región Metropolitana",
        "🧠  Aprende los atajos y trampas típicas",
        "📈  Asegura sobre 800+ puntos en la prueba",
    ]
    y_pos = 730
    for it in items:
        draw.text((160, y_pos), it, font=f_item, fill=COLOR_TEXTO, anchor="lm")
        y_pos += 88

    # 4. Caja de llamada a responder
    draw.rounded_rectangle([110, 1260, 970, 1490], radius=24, fill=COLOR_AMBAR)
    draw.text((540, 1335), "Responde «PAES» a esta historia", font=f_dm, fill=COLOR_FONDO, anchor="mm")
    draw.text((540, 1410), "y te envío horarios y cupos disponibles 📩", font=f_item, fill=COLOR_FONDO, anchor="mm")

    # 5. Marca inferior
    draw.text((540, 1720), "@tuprofeindustrial", font=f_marca, fill=(100, 116, 139), anchor="mm")

    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, quality=95)
    return destino


def crear_historias(carpeta: Path, guion: Guion) -> dict[str, Path]:
    """Crea ambas historias para el video y devuelve sus rutas."""
    encuesta = carpeta / "historia_01_encuesta.png"
    clases = carpeta / "historia_02_clases.png"
    crear_historia_encuesta(guion, encuesta)
    crear_historia_clases(guion, clases)
    return {"encuesta": encuesta, "clases": clases}
