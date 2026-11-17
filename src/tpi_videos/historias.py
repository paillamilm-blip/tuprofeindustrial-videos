"""Generador de historias para Instagram y TikTok en formato vertical (1080×1920).

Crea dos imágenes de historias automáticas de alto impacto listas para subir:
1. ``historia_01_encuesta.png``: Reto interactivo con opciones A y B para el sticker de encuesta.
2. ``historia_02_clases.png``: Tarjeta moderna de llamado a la acción para clases particulares PAES
   (online para todo Chile y presencial en toda la Región Metropolitana).
"""

from __future__ import annotations

import re
from pathlib import Path
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


def _pegar_emoji(base_img: Image.Image, emoji_img: Image.Image, x: int | float, y: int | float) -> None:
    base_img.paste(emoji_img, (int(x), int(y)), emoji_img)


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


def crear_historia_encuesta(guion: Guion, destino: Path) -> Path:
    """Genera la historia 1: Reto / Encuesta para Instagram y TikTok."""
    f = _fuentes()
    f_black = lambda sz: ImageFont.truetype(f["black"], sz)
    f_extra = lambda sz: ImageFont.truetype(f["extra"], sz)
    f_semi = lambda sz: ImageFont.truetype(f["semi"], sz)

    # 1. Fondo base y resplandor
    img = _fondo_base()
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([180, 580, 900, 1200], fill=(56, 189, 248, 35))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(80)))

    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    cfg = guion.historias.encuesta if guion.historias and guion.historias.encuesta else None
    es_paes = "paes" in guion.titulo.lower() or (guion.nivel and "paes" in guion.nivel.lower())

    # 2. Badge superior
    badge_txt = cfg.badge if cfg and cfg.badge else ("RETO PAES M1" if es_paes else f"RETO {guion.materia.upper()}")
    f_b = f_extra(34)
    bbox = f_b.getbbox(badge_txt)
    tw = bbox[2] - bbox[0]
    total_w = tw + 44 + 18
    bx0 = 540 - total_w // 2
    bx1 = 540 + total_w // 2
    _rect_con_sombra(
        d,
        [bx0 - 25, 270, bx1 + 25, 345],
        radius=35,
        fill=(245, 158, 11, 245),
        shadow_color=(0, 0, 0, 100),
    )
    d.text((bx0 + 44 + 16, 307), badge_txt, font=f_b, fill=(15, 23, 42), anchor="lm")

    # 3. Titular
    if cfg and cfg.titulo:
        t_l1, t_l2 = (cfg.titulo.split("\n") + [""])[:2]
    elif "20%" in guion.gancho.texto or "porcentaje" in guion.titulo.lower():
        t_l1 = "¿CAERÍAS EN LA TRAMPA"
        t_l2 = "DE LOS PORCENTAJES?"
    else:
        t_l1 = "¿SABRÍAS RESOLVER"
        t_l2 = "ESTE PROBLEMA?"

    d.text((540, 420), t_l1, font=f_black(58), fill=(255, 255, 255), anchor="mm")
    if t_l2:
        d.text((540, 500), t_l2, font=f_black(58), fill=(250, 204, 21), anchor="mm")

    # 4. Tarjeta del Problema
    _rect_con_sombra(
        d,
        [90, 590, 990, 930],
        radius=30,
        fill=(15, 23, 42, 235),
        outline=(56, 189, 248, 180),
        width=3,
    )
    if cfg and cfg.pregunta:
        lineas_p = [lp.strip() for lp in cfg.pregunta.split("\n") if lp.strip()]
        y_p = 660 if len(lineas_p) >= 3 else 700
        for lp in lineas_p:
            d.text((540, y_p), lp, font=f_extra(44 if len(lp) < 26 else 38), fill=(241, 245, 249), anchor="mm")
            y_p += 70
        has_steps_icons = False
    elif "20%" in guion.gancho.texto or "porcentaje" in guion.titulo.lower():
        d.text((540, 665), "Un producto cuesta $100:", font=f_extra(44), fill=(241, 245, 249), anchor="mm")
        d.text((370, 745), "1. Baja un 20%", font=f_semi(40), fill=(203, 213, 225), anchor="lm")
        d.text((370, 815), "2. Luego sube un 20%", font=f_semi(40), fill=(203, 213, 225), anchor="lm")
        d.text((540, 885), "¿Cuál es su precio final?", font=f_extra(42), fill=(56, 189, 248), anchor="mm")
        has_steps_icons = True
    else:
        enunc = guion.enunciado.texto
        if len(enunc) > 80:
            enunc = enunc[:77] + "…"
        d.text((540, 720), "Enunciado del ejercicio:", font=f_extra(38), fill=(241, 245, 249), anchor="mm")
        d.text((540, 800), enunc, font=f_semi(34), fill=(203, 213, 225), anchor="mm")
        has_steps_icons = False

    # 5. Opciones A y B
    if cfg and cfg.opcion_a and cfg.opcion_b:
        op_a = cfg.opcion_a
        op_b = cfg.opcion_b
    elif any(p.error for p in guion.pasos):
        paso_err = next(p for p in guion.pasos if p.error)
        err_tex = re.sub(r"\\[a-zA-Z]+", "", paso_err.tex or "").replace("{", "").replace("}", "").strip()
        if "=" in err_tex:
            err_tex = err_tex.split("=")[-1].strip()
        res_tex = re.sub(r"\\[a-zA-Z]+", "", guion.resultado.tex or "").replace("{", "").replace("}", "").strip()
        if "=" in res_tex:
            res_tex = res_tex.split("=")[-1].strip()
        op_a = f"{err_tex}  («La trampa clásica»)"
        op_b = f"{res_tex}  («Resultado correcto»)"
    elif "20%" in guion.gancho.texto or "porcentaje" in guion.titulo.lower():
        op_a = "$100  («Vuelve al inicio»)"
        op_b = "$96  («Pierde 4 pesos»)"
    else:
        op_a = "Opción A (Resultado 1)"
        op_b = "Opción B (Resultado 2)"

    _rect_con_sombra(
        d,
        [90, 980, 990, 1110],
        radius=24,
        fill=(30, 41, 59, 230),
        outline=(245, 158, 11, 200),
        width=2,
    )
    d.text((160, 1045), "A)", font=f_black(48), fill=(245, 158, 11), anchor="mm")
    d.text((540, 1045), op_a, font=f_extra(42), fill=(255, 255, 255), anchor="mm")

    _rect_con_sombra(
        d,
        [90, 1140, 990, 1270],
        radius=24,
        fill=(30, 41, 59, 230),
        outline=(56, 189, 248, 200),
        width=2,
    )
    d.text((160, 1205), "B)", font=f_black(48), fill=(56, 189, 248), anchor="mm")
    d.text((540, 1205), op_b, font=f_extra(42), fill=(255, 255, 255), anchor="mm")

    # 6. Guía para el sticker interactivo
    d.text((540, 1395), "VOTA EN LA ENCUESTA AQUÍ ABAJO", font=f_black(35), fill=(250, 204, 21), anchor="mm")
    d.text((540, 1450), "Más del 80% responde mal... ¿y tú?", font=f_semi(33), fill=(148, 163, 184), anchor="mm")

    # 7. Footer
    d.text((540, 1680), "@tuprofeindustrial · Solución en el nuevo Reel", font=f_extra(30), fill=(100, 116, 139), anchor="mm")

    img_comp = Image.alpha_composite(img, ov)
    _pegar_emoji(img_comp, _cargar_emoji("cerebro.png", 44), bx0, 285)
    if has_steps_icons:
        _pegar_emoji(img_comp, _cargar_emoji("baja.png", 42), 300, 725)
        _pegar_emoji(img_comp, _cargar_emoji("sube.png", 42), 300, 795)

    _pegar_emoji(img_comp, _cargar_emoji("abajo.png", 46), 540 - 23, 1320)

    destino.parent.mkdir(parents=True, exist_ok=True)
    img_comp.convert("RGB").save(destino, quality=95)
    return destino


def crear_historia_clases(guion: Guion, destino: Path) -> Path:
    """Genera la historia 2: Llamado a la acción para clases particulares PAES."""
    f = _fuentes()
    f_black = lambda sz: ImageFont.truetype(f["black"], sz)
    f_extra = lambda sz: ImageFont.truetype(f["extra"], sz)
    f_semi = lambda sz: ImageFont.truetype(f["semi"], sz)

    # 1. Fondo base y resplandor
    img = _fondo_base()
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([180, 580, 900, 1200], fill=(245, 158, 11, 30))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(80)))

    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # 2. Badge
    badge_txt = "ADMISIÓN PAES 2025"
    f_b = f_extra(34)
    bbox = f_b.getbbox(badge_txt)
    tw = bbox[2] - bbox[0]
    total_w = tw + 44 + 18
    bx0 = 540 - total_w // 2
    bx1 = 540 + total_w // 2
    _rect_con_sombra(
        d,
        [bx0 - 25, 270, bx1 + 25, 345],
        radius=35,
        fill=(56, 189, 248, 245),
        shadow_color=(0, 0, 0, 100),
    )
    d.text((bx0 + 44 + 16, 307), badge_txt, font=f_b, fill=(15, 23, 42), anchor="lm")

    # 3. Titular
    d.text((540, 420), "¿BUSCAS 800+ EN", font=f_black(62), fill=(255, 255, 255), anchor="mm")
    d.text((540, 500), "MATEMÁTICA PAES?", font=f_black(62), fill=(250, 204, 21), anchor="mm")

    # 4. Tarjeta de Beneficios
    _rect_con_sombra(
        d,
        [80, 585, 1000, 1265],
        radius=30,
        fill=(15, 23, 42, 235),
        outline=(245, 158, 11, 180),
        width=3,
    )

    items = [
        ("objetivo.png", "Método enfocado en trampas PAES", "Aprende los patrones y atajos que el DEMRE repite."),
        ("idea.png", "Modalidad Online en vivo (Todo Chile)", "Clases con pizarra digital interactiva y grabadas."),
        ("alerta.png", "Presencial en toda la Región Metropolitana", "A domicilio o lugar a convenir con horarios a tu ritmo."),
        ("cien.png", "Ensayos reales y resolución continua", "Guías paso a paso y apoyo por WhatsApp para dudas."),
    ]

    y_pos = 665
    for _, tit, sub in items:
        d.text((220, y_pos - 15), tit, font=f_extra(34), fill=(241, 245, 249), anchor="lm")
        d.text((220, y_pos + 26), sub, font=f_semi(27), fill=(148, 163, 184), anchor="lm")
        y_pos += 140

    # 5. Botón de Acción tipo Sticker DM
    btn_txt = "RESPONDE «PAES» A ESTA HISTORIA"
    f_btn = f_black(37)
    bbox_btn = f_btn.getbbox(btn_txt)
    w_btn = bbox_btn[2] - bbox_btn[0]
    total_btn = w_btn + 44 + 18
    btn_x0 = 540 - total_btn // 2

    _rect_con_sombra(
        d,
        [90, 1330, 990, 1530],
        radius=28,
        fill=(245, 158, 11, 255),
        shadow_color=(0, 0, 0, 140),
    )
    d.text((btn_x0 + 44 + 16, 1395), btn_txt, font=f_btn, fill=(15, 23, 42), anchor="lm")
    d.text((540, 1465), "y coordinamos tu primera clase y diagnóstico", font=f_extra(32), fill=(15, 23, 42), anchor="mm")

    # 6. Footer
    d.text((540, 1680), "@tuprofeindustrial · Cupos limitados para este mes", font=f_extra(30), fill=(100, 116, 139), anchor="mm")

    img_comp = Image.alpha_composite(img, ov)
    _pegar_emoji(img_comp, _cargar_emoji("cohete.png", 44), bx0, 285)

    y_ico = 640
    for ico_name, _, _ in items:
        _pegar_emoji(img_comp, _cargar_emoji(ico_name, 48), 140, y_ico)
        y_ico += 140

    _pegar_emoji(img_comp, _cargar_emoji("rayo.png", 44), btn_x0, 1373)

    destino.parent.mkdir(parents=True, exist_ok=True)
    img_comp.convert("RGB").save(destino, quality=95)
    return destino


def crear_historias(carpeta: Path, guion: Guion) -> dict[str, Path]:
    """Crea ambas historias para el video y devuelve sus rutas."""
    encuesta = carpeta / "historia_01_encuesta.png"
    clases = carpeta / "historia_02_clases.png"
    crear_historia_encuesta(guion, encuesta)
    crear_historia_clases(guion, clases)
    return {"encuesta": encuesta, "clases": clases}
