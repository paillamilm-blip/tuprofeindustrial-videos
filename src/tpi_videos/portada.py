"""Generador de portadas de alto impacto y curiosidad (CTR) para TikTok, Instagram Reels y YouTube Shorts (1080×1920).

Diseñado con zona segura central (1080×1080) para que nunca se recorte
ni en la grilla del perfil de Instagram (1:1), ni en el feed de Instagram (4:5),
ni en el reproductor vertical (9:16).

Incluye sistema de temas cromáticos, fondos y emojis dinámicos para que
cada video tenga una identidad visual única y destacada en el feed.
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

PALETAS: dict[str, dict[str, Any]] = {
    "morado": {
        "fondo": "neon_uva.png",
        "vineta": "vineta_cine.png",
        "blend": 0.45,
        "glow": (168, 85, 247, 65),
        "badge_fill": (147, 51, 234, 245),
        "badge_emoji": "rayo.png",
        "titular_l2_fill": (192, 132, 252),
        "box_fill": (24, 14, 38, 235),
        "box_border": (192, 132, 252, 210),
        "alerta_fill": (255, 255, 255, 255),
        "alerta_border": (147, 51, 234, 255),
        "alerta_text": (126, 34, 206),
        "alerta_emoji": "alerta.png",
        "detalle_fill": (216, 180, 254),
        "flecha_color": (192, 132, 252, 255),
    },
    "ambar": {
        "fondo": "plano_azul.png",
        "vineta": "vineta_dorada.png",
        "blend": 0.50,
        "glow": (245, 158, 11, 65),
        "badge_fill": (217, 119, 6, 245),
        "badge_emoji": "fuego.png",
        "titular_l2_fill": (250, 204, 21),
        "box_fill": (26, 22, 14, 235),
        "box_border": (251, 191, 36, 210),
        "alerta_fill": (255, 255, 255, 255),
        "alerta_border": (217, 119, 6, 255),
        "alerta_text": (180, 83, 9),
        "alerta_emoji": "baja.png",
        "detalle_fill": (250, 204, 21),
        "flecha_color": (251, 191, 36, 255),
    },
    "verde": {
        "fondo": "tiza_verde.png",
        "vineta": "vineta_cine.png",
        "blend": 0.40,
        "glow": (16, 185, 129, 65),
        "badge_fill": (5, 150, 105, 245),
        "badge_emoji": "divide.png",
        "titular_l2_fill": (110, 231, 183),
        "box_fill": (10, 28, 20, 235),
        "box_border": (52, 211, 153, 210),
        "alerta_fill": (255, 255, 255, 255),
        "alerta_border": (5, 150, 105, 255),
        "alerta_text": (4, 120, 87),
        "alerta_emoji": "incorrecto.png",
        "detalle_fill": (110, 231, 183),
        "flecha_color": (52, 211, 153, 255),
    },
    "cian": {
        "fondo": "comic_azul.png",
        "vineta": "vineta_cine.png",
        "blend": 0.45,
        "glow": (6, 182, 212, 70),
        "badge_fill": (2, 132, 199, 245),
        "badge_emoji": "cronometro.png",
        "titular_l2_fill": (56, 189, 248),
        "box_fill": (12, 24, 42, 235),
        "box_border": (56, 189, 248, 210),
        "alerta_fill": (255, 255, 255, 255),
        "alerta_border": (2, 132, 199, 255),
        "alerta_text": (2, 132, 199),
        "alerta_emoji": "objetivo.png",
        "detalle_fill": (56, 189, 248),
        "flecha_color": (56, 189, 248, 255),
    },
    "naranja": {
        "fondo": "plano_noche.png",
        "vineta": "vineta_dorada.png",
        "blend": 0.45,
        "glow": (249, 115, 22, 65),
        "badge_fill": (234, 88, 12, 245),
        "badge_emoji": "construccion.png",
        "titular_l2_fill": (251, 146, 60),
        "box_fill": (28, 18, 14, 235),
        "box_border": (251, 146, 60, 210),
        "alerta_fill": (255, 255, 255, 255),
        "alerta_border": (234, 88, 12, 255),
        "alerta_text": (194, 65, 12),
        "alerta_emoji": "incorrecto.png",
        "detalle_fill": (253, 186, 116),
        "flecha_color": (251, 146, 60, 255),
    },
    "rojo": {
        "fondo": "plano_noche.png",
        "vineta": "vineta_cine.png",
        "blend": 0.45,
        "glow": (244, 63, 94, 65),
        "badge_fill": (225, 29, 72, 245),
        "badge_emoji": "alerta.png",
        "titular_l2_fill": (250, 204, 21),
        "box_fill": (24, 14, 18, 235),
        "box_border": (251, 113, 133, 210),
        "alerta_fill": (255, 255, 255, 255),
        "alerta_border": (225, 29, 72, 255),
        "alerta_text": (225, 29, 72),
        "alerta_emoji": "cien.png",
        "detalle_fill": (250, 204, 21),
        "flecha_color": (244, 63, 94, 255),
    },
}


def inferir_paleta(guion: Guion) -> str:
    """Deduce una paleta temática armónica según el contenido matemático/físico."""
    texto_total = f"{guion.titulo} {guion.gancho.texto} {guion.enunciado.texto}".lower()
    if any(k in texto_total for k in ["obrero", "trabajador", "días", "inversa", "proporcionalidad"]):
        return "naranja"
    if any(k in texto_total for k in ["fracción", "fracciones", "denominador", "tercio", "cuarto", "doceavos"]):
        return "verde"
    if any(k in texto_total for k in ["signo", "paréntesis", "distributiva", "potencia", "álgebra"]):
        return "morado"
    if any(k in texto_total for k in ["ecuación", "revisar", "comprobar", "despejar"]):
        return "cian"
    if any(k in texto_total for k in ["precio original", "descuento inverso", "pagaste", "16.000"]):
        return "rojo"
    if any(k in texto_total for k in ["porcentaje", "20%", "50%", "base", "iva"]):
        return "ambar"
    return "cian"


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
    if not nombre.endswith(".png"):
        nombre += ".png"
    ruta = _emojis_dir() / nombre
    if ruta.exists():
        im = Image.open(ruta).convert("RGBA")
        return im.resize((tamano, tamano), Image.Resampling.LANCZOS)
    return Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))


def _fondo_base(paleta: dict[str, Any], fondo_custom: str | None = None) -> Image.Image:
    fondos = raiz_proyecto() / "src" / "tpi_videos" / "assets" / "fondos"
    nombre_bg = (fondo_custom + ".png" if fondo_custom and not fondo_custom.endswith(".png") else fondo_custom) or paleta["fondo"]
    ruta_bg = fondos / nombre_bg
    if not ruta_bg.exists():
        ruta_bg = fondos / "plano_noche.png"
    bg = Image.open(ruta_bg).convert("RGBA")

    nombre_vin = paleta.get("vineta", "vineta_cine.png")
    ruta_vin = fondos / nombre_vin
    if ruta_vin.exists():
        vineta = Image.open(ruta_vin).convert("RGBA")
        return Image.blend(bg, vineta, paleta.get("blend", 0.45))
    return bg


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


def _fuente_adaptada(
    texto: str,
    creador_fuente: Any,
    tam_inicial: int,
    max_ancho: int,
    min_tam: int = 18,
) -> ImageFont.FreeTypeFont:
    """Reduce progresivamente el tamaño de fuente hasta que el texto quepa en max_ancho."""
    tam = tam_inicial
    f = creador_fuente(tam)
    if not texto:
        return f
    while tam > min_tam:
        bbox = f.getbbox(texto)
        if (bbox[2] - bbox[0]) <= max_ancho:
            return f
        tam -= 2
        f = creador_fuente(tam)
    return f


def crear_portada(carpeta: Path, linea: dict[str, Any], guion: Guion) -> Path:
    """Genera la portada/miniatura en alta resolución (1080×1920) y la guarda como PNG y JPG."""
    f = _fuentes()
    f_black = lambda sz: ImageFont.truetype(f["black"], sz)
    f_extra = lambda sz: ImageFont.truetype(f["extra"], sz)
    f_semi = lambda sz: ImageFont.truetype(f["semi"], sz)

    cfg = guion.portada
    es_paes = "paes" in guion.titulo.lower() or (guion.nivel and "paes" in guion.nivel.lower())

    # 1. Determinar estilo y paleta temática
    nombre_paleta = (cfg.estilo if cfg and cfg.estilo else inferir_paleta(guion)).lower()
    paleta = PALETAS.get(nombre_paleta, PALETAS["cian"])

    # 2. Fondo base dinámico y resplandor radial
    img = _fondo_base(paleta, cfg.fondo if cfg else None)
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([160, 600, 920, 1240], fill=paleta["glow"])
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(80)))

    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # 3. Badge superior personalizado
    badge_txt = (
        cfg.badge
        if cfg and cfg.badge
        else ("PAES M1 · ADMISIÓN 2027" if es_paes else f"DESAFÍO {guion.materia.upper()}")
    )
    f_b = _fuente_adaptada(badge_txt, f_extra, tam_inicial=34, max_ancho=700, min_tam=20)
    bbox = f_b.getbbox(badge_txt)
    tw = bbox[2] - bbox[0]
    total_w = tw + 44 + 18
    bx0 = 540 - total_w // 2
    bx1 = 540 + total_w // 2
    _rect_con_sombra(
        d,
        [bx0 - 25, 470, bx1 + 25, 540],
        radius=35,
        fill=paleta["badge_fill"],
        shadow_color=(0, 0, 0, 120),
    )
    d.text((bx0 + 44 + 16, 505), badge_txt, font=f_b, fill=(255, 255, 255), anchor="lm")

    # 4. Titular Gancho
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

    f_hook_l1 = _fuente_adaptada(l1, f_black, tam_inicial=80, max_ancho=940, min_tam=36)
    f_hook_l2 = _fuente_adaptada(l2, f_black, tam_inicial=80, max_ancho=940, min_tam=36)
    for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3), (0, 6), (0, 8)]:
        d.text((540 + dx, 630 + dy), l1, font=f_hook_l1, fill=(0, 0, 0, 200), anchor="mm")
        if l2:
            d.text((540 + dx, 730 + dy), l2, font=f_hook_l2, fill=(0, 0, 0, 200), anchor="mm")
    d.text((540, 630), l1, font=f_hook_l1, fill=(255, 255, 255), anchor="mm")
    if l2:
        d.text((540, 730), l2, font=f_hook_l2, fill=paleta["titular_l2_fill"], anchor="mm")

    # 5. Tarjeta Central de Curiosidad / Ruptura de Creencia
    _rect_con_sombra(
        d,
        [100, 835, 980, 1180],
        radius=30,
        fill=paleta["box_fill"],
        outline=paleta["box_border"],
        width=3,
    )
    pregunta_txt = (
        cfg.pregunta
        if cfg and cfg.pregunta
        else ("¿QUEDA EN EL MISMO PRECIO?" if "20%" in guion.gancho.texto else "¿CÓMO SE RESUELVE?")
    )
    f_preg = _fuente_adaptada(pregunta_txt, f_extra, tam_inicial=44, max_ancho=800, min_tam=24)
    d.text((540, 905), pregunta_txt, font=f_preg, fill=(241, 245, 249), anchor="mm")

    # 6. Sello Alerta: FONDO BLANCO con BORDE DINÁMICO adaptado al texto
    alerta_txt = cfg.alerta if cfg and cfg.alerta else "¡NO! EL 85% SE EQUIVOCA"
    f_alerta = _fuente_adaptada(alerta_txt, f_black, tam_inicial=36, max_ancho=700, min_tam=20)
    bbox_al = f_alerta.getbbox(alerta_txt)
    w_al = bbox_al[2] - bbox_al[0]
    emoji_sz = 46
    gap = 14
    content_w = emoji_sz + gap + w_al
    pill_pad = 24
    pill_w = max(min(content_w + pill_pad * 2, 840), 400)
    pill_x0 = 540 - pill_w // 2
    pill_x1 = 540 + pill_w // 2

    _rect_con_sombra(
        d,
        [pill_x0, 965, pill_x1, 1050],
        radius=22,
        fill=paleta["alerta_fill"],
        outline=paleta["alerta_border"],
        width=3,
        shadow_color=(0, 0, 0, 120),
    )
    content_x0 = 540 - content_w // 2
    al_emoji_x = content_x0
    al_text_x = content_x0 + emoji_sz + gap
    d.text((al_text_x, 1007), alerta_txt, font=f_alerta, fill=paleta["alerta_text"], anchor="lm")

    # 7. Fórmula reveladora o detalle con color de acento (auto-adaptable al ancho de la tarjeta)
    if cfg and cfg.detalle:
        f_det = _fuente_adaptada(cfg.detalle, f_black, tam_inicial=48, max_ancho=800, min_tam=22)
        d.text((540, 1115), cfg.detalle, font=f_det, fill=paleta["detalle_fill"], anchor="mm")
    elif "20%" in guion.gancho.texto:
        f_form = f_black(54)
        d.text((280, 1115), "100", font=f_form, fill=(255, 255, 255), anchor="mm")
        _dibujar_flecha(d, 350, 1115, 60, color=paleta["flecha_color"], width=5)
        d.text((485, 1115), "80", font=f_form, fill=(255, 255, 255), anchor="mm")
        _dibujar_flecha(d, 550, 1115, 60, color=paleta["flecha_color"], width=5)
        d.text((690, 1115), "96", font=f_form, fill=(250, 204, 21), anchor="mm")
    else:
        res_tex = guion.resultado.texto or guion.resultado.tex or ""
        limpio = re.sub(r"\\[a-zA-Z]+", "", res_tex).replace("{", "").replace("}", "").strip()
        f_det = _fuente_adaptada(limpio[:30], f_black, tam_inicial=46, max_ancho=800, min_tam=22)
        d.text((540, 1115), limpio[:30], font=f_det, fill=paleta["detalle_fill"], anchor="mm")

    # 8. Subtexto / Invitación al video
    pie_txt = (
        cfg.pie
        if cfg and cfg.pie
        else (
            "Descubre por qué termina en 96 en este video"
            if "20%" in guion.gancho.texto
            else "Descubre la explicación paso a paso en este video"
        )
    )
    f_pie = _fuente_adaptada(pie_txt, f_semi, tam_inicial=35, max_ancho=940, min_tam=20)
    d.text((540, 1250), pie_txt, font=f_pie, fill=(203, 213, 225), anchor="mm")

    # 9. Branding en la base segura
    materia_tag = "PAES M1 · ADMISIÓN 2027" if es_paes else guion.materia.upper()
    branding_txt = f"@tuprofeindustrial · {materia_tag}"
    f_brand = _fuente_adaptada(branding_txt, f_extra, tam_inicial=28, max_ancho=680, min_tam=20)
    _rect_con_sombra(
        d,
        [180, 1340, 900, 1405],
        radius=25,
        fill=(30, 41, 59, 220),
        outline=(71, 85, 105, 180),
        width=2,
    )
    d.text((540, 1372), branding_txt, font=f_brand, fill=(148, 163, 184), anchor="mm")

    # 10. Pegar emojis visuales temáticos
    emoji_badge_nombre = (cfg.emoji_badge if cfg and cfg.emoji_badge else paleta["badge_emoji"])
    emoji_alerta_nombre = (cfg.emoji_alerta if cfg and cfg.emoji_alerta else paleta["alerta_emoji"])

    img_comp = Image.alpha_composite(img, ov)
    _pegar_emoji(img_comp, _cargar_emoji(emoji_badge_nombre, 44), bx0, 483)
    _pegar_emoji(img_comp, _cargar_emoji(emoji_alerta_nombre, emoji_sz), al_emoji_x, 984)

    destino_png = carpeta / "portada.png"
    destino_jpg = carpeta / "portada.jpg"
    destino_mini = carpeta / "miniatura.jpg"

    rgb_final = img_comp.convert("RGB")
    rgb_final.save(destino_png, quality=95)
    rgb_final.save(destino_jpg, quality=95)
    rgb_final.save(destino_mini, quality=95)

    return destino_png
