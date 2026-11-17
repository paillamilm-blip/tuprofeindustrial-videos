"""Generador de portadas de alto impacto y curiosidad (CTR) para TikTok, Instagram Reels y YouTube Shorts (1080×1920).

Diseñado con zona segura central (1080×1080) para que nunca se recorte
ni en la grilla del perfil de Instagram (1:1), ni en el feed de Instagram (4:5),
ni en el reproductor vertical (9:16).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .entorno import raiz_proyecto
from .guion import Guion

ANCHO = 1080
ALTO = 1920


def _fuentes() -> dict[str, str]:
    carpeta = raiz_proyecto() / "src" / "tpi_videos" / "assets" / "fuentes"
    return {
        "black": str(carpeta / "Montserrat-Black.ttf"),
        "extra": str(carpeta / "Montserrat-ExtraBold.ttf"),
        "semi": str(carpeta / "Montserrat-SemiBold.ttf"),
        "med": str(carpeta / "Montserrat-Medium.ttf"),
    }


def _emojis_dir() -> Path:
    return raiz_proyecto() / "src" / "tpi_videos" / "assets" / "emojis"


def _cargar_emoji(nombre: str, tamano: int) -> Image.Image:
    ruta = _emojis_dir() / nombre
    if ruta.exists():
        im = Image.open(ruta).convert("RGBA")
        return im.resize((tamano, tamano), Image.Resampling.LANCZOS)
    return Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))


def _fondo_base() -> Image.Image:
    fondos = raiz_proyecto() / "src" / "tpi_videos" / "assets" / "fondos"
    bg = Image.open(fondos / "plano_noche.png").convert("RGBA")
    vineta = Image.open(fondos / "vineta_cine.png").convert("RGBA")
    return Image.blend(bg, vineta, 0.45)


def _rect_con_sombra(
    draw: ImageDraw.ImageDraw,
    box: list[int | float],
    radius: int,
    fill: tuple[int, ...],
    outline: tuple[int, ...] | None = None,
    width: int = 1,
    shadow_offset: tuple[int, int] = (0, 10),
    shadow_color: tuple[int, int, int, int] = (0, 0, 0, 140),
) -> None:
    x0, y0, x1, y1 = box
    sx, sy = shadow_offset
    draw.rounded_rectangle([x0 + sx, y0 + sy, x1 + sx, y1 + sy], radius=radius, fill=shadow_color)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _dibujar_flecha(
    draw: ImageDraw.ImageDraw,
    x0: int,
    y: int,
    largo: int,
    color: tuple[int, int, int, int] = (56, 189, 248, 255),
    width: int = 5,
) -> None:
    x1 = x0 + largo
    draw.line([(x0, y), (x1, y)], fill=color, width=width)
    draw.polygon([(x1, y - 9), (x1 + 14, y), (x1, y + 9)], fill=color)


def _pegar_emoji(base_img: Image.Image, emoji_img: Image.Image, x: int | float, y: int | float) -> None:
    base_img.paste(emoji_img, (int(x), int(y)), emoji_img)


def crear_portada(carpeta: Path, linea: dict[str, Any], guion: Guion) -> Path:
    """Genera la portada/miniatura en alta resolución (1080×1920) y la guarda como PNG y JPG."""
    f = _fuentes()
    f_black = lambda sz: ImageFont.truetype(f["black"], sz)
    f_extra = lambda sz: ImageFont.truetype(f["extra"], sz)
    f_semi = lambda sz: ImageFont.truetype(f["semi"], sz)

    # 1. Fondo base y resplandor radial
    img = _fondo_base()
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([180, 620, 900, 1220], fill=(56, 189, 248, 45))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(80)))

    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # 2. Configuración o inferencia de textos
    cfg = guion.portada
    es_paes = "paes" in guion.titulo.lower() or (guion.nivel and "paes" in guion.nivel.lower())

    # Badge superior
    badge_txt = (
        cfg.badge
        if cfg and cfg.badge
        else ("ERROR TÍPICO PAES M1" if es_paes else f"DESAFÍO {guion.materia.upper()}")
    )
    f_b = f_extra(34)
    bbox = f_b.getbbox(badge_txt)
    tw = bbox[2] - bbox[0]
    total_w = tw + 44 + 18
    bx0 = 540 - total_w // 2
    bx1 = 540 + total_w // 2
    _rect_con_sombra(
        d,
        [bx0 - 25, 470, bx1 + 25, 540],
        radius=35,
        fill=(239, 68, 68, 245),
        shadow_color=(0, 0, 0, 120),
    )
    d.text((bx0 + 44 + 16, 505), badge_txt, font=f_b, fill=(255, 255, 255), anchor="lm")

    # Titular Gancho
    if cfg and cfg.titular:
        lineas = cfg.titular.split("\n")
        l1 = lineas[0]
        l2 = lineas[1] if len(lineas) > 1 else ""
    elif "20%" in guion.gancho.texto or "porcentaje" in guion.titulo.lower():
        l1 = "¿BAJA UN 20% Y"
        l2 = "SUBE UN 20%?"
    elif ":" in guion.gancho.texto:
        partes = guion.gancho.texto.split(":")
        l1 = partes[0].strip().upper()
        l2 = partes[1].strip().upper()
        if len(l1) > 22:
            l1 = l1[:22]
    else:
        l1 = guion.gancho.texto[:22].upper()
        l2 = guion.gancho.texto[22:45].upper()

    f_hook = f_black(80)
    for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3), (0, 6), (0, 8)]:
        d.text((540 + dx, 630 + dy), l1, font=f_hook, fill=(0, 0, 0, 200), anchor="mm")
        if l2:
            d.text((540 + dx, 730 + dy), l2, font=f_hook, fill=(0, 0, 0, 200), anchor="mm")
    d.text((540, 630), l1, font=f_hook, fill=(255, 255, 255), anchor="mm")
    if l2:
        d.text((540, 730), l2, font=f_hook, fill=(250, 204, 21), anchor="mm")

    # Tarjeta Central de Curiosidad / Ruptura de Creencia
    _rect_con_sombra(
        d,
        [100, 835, 980, 1180],
        radius=30,
        fill=(15, 23, 42, 235),
        outline=(56, 189, 248, 180),
        width=3,
    )
    pregunta_txt = (
        cfg.pregunta
        if cfg and cfg.pregunta
        else ("¿QUEDA EN EL MISMO PRECIO?" if "20%" in guion.gancho.texto else "¿CÓMO SE RESUELVE?")
    )
    d.text((540, 905), pregunta_txt, font=f_extra(44), fill=(241, 245, 249), anchor="mm")

    # Sello Alerta: FONDO BLANCO con BORDE ROJO para alto contraste
    alerta_txt = cfg.alerta if cfg and cfg.alerta else "¡NO! EL 85% SE EQUIVOCA"
    f_alerta = f_black(38)
    bbox_al = f_alerta.getbbox(alerta_txt)
    w_al = bbox_al[2] - bbox_al[0]
    total_al = w_al + 50 + 20
    al_x0 = 540 - total_al // 2

    _rect_con_sombra(
        d,
        [130, 965, 950, 1050],
        radius=22,
        fill=(255, 255, 255, 255),
        outline=(239, 68, 68, 255),
        width=3,
        shadow_color=(0, 0, 0, 120),
    )
    d.text((al_x0 + 50 + 16, 1007), alerta_txt, font=f_alerta, fill=(225, 29, 72), anchor="lm")

    # Fórmula reveladora o detalle
    if cfg and cfg.detalle:
        d.text((540, 1115), cfg.detalle, font=f_black(52), fill=(56, 189, 248), anchor="mm")
    elif "20%" in guion.gancho.texto:
        f_form = f_black(54)
        d.text((280, 1115), "100", font=f_form, fill=(255, 255, 255), anchor="mm")
        _dibujar_flecha(d, 350, 1115, 60, color=(56, 189, 248, 255), width=5)
        d.text((485, 1115), "80", font=f_form, fill=(255, 255, 255), anchor="mm")
        _dibujar_flecha(d, 550, 1115, 60, color=(56, 189, 248, 255), width=5)
        d.text((690, 1115), "96", font=f_form, fill=(250, 204, 21), anchor="mm")
    else:
        res_tex = guion.resultado.texto or guion.resultado.tex or ""
        limpio = re.sub(r"\\[a-zA-Z]+", "", res_tex).replace("{", "").replace("}", "").strip()
        d.text((540, 1115), limpio[:24], font=f_black(50), fill=(56, 189, 248), anchor="mm")

    # Subtexto / Invitación al video
    pie_txt = (
        cfg.pie
        if cfg and cfg.pie
        else (
            "Descubre por qué termina en 96 en este video"
            if "20%" in guion.gancho.texto
            else "Descubre la explicación paso a paso en este video"
        )
    )
    d.text((540, 1250), pie_txt, font=f_semi(35), fill=(203, 213, 225), anchor="mm")

    # Branding en la base segura
    _rect_con_sombra(
        d,
        [240, 1340, 840, 1405],
        radius=25,
        fill=(30, 41, 59, 220),
        outline=(71, 85, 105, 180),
        width=2,
    )
    materia_tag = "MATEMÁTICA PAES" if es_paes else guion.materia.upper()
    d.text((540, 1372), f"@tuprofeindustrial · {materia_tag}", font=f_extra(30), fill=(148, 163, 184), anchor="mm")

    # Pegar emojis visuales
    img_comp = Image.alpha_composite(img, ov)
    _pegar_emoji(img_comp, _cargar_emoji("alerta.png", 44), bx0, 483)
    _pegar_emoji(img_comp, _cargar_emoji("incorrecto.png", 50), al_x0, 982)

    destino_png = carpeta / "portada.png"
    destino_jpg = carpeta / "portada.jpg"
    destino_mini = carpeta / "miniatura.jpg"

    rgb_final = img_comp.convert("RGB")
    rgb_final.save(destino_png, quality=95)
    rgb_final.save(destino_jpg, quality=95)
    rgb_final.save(destino_mini, quality=95)

    return destino_png
