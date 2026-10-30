"""Kit de publicación de un video: portada (PNG) y textos para YouTube Shorts, TikTok y Reels.

- La portada es el cuadro del gancho sin subtítulos (la pregunta grande, el emoji y la fórmula).
- Los textos los escribe Gemini a partir del guion. Sin clave (o con ``--sin-ia``) se arman con una
  plantilla a partir del mismo guion, así el kit siempre se puede crear.
- Todo queda junto al video: ``portada.png``, ``publicacion.md`` (para leer y copiar) y ``publicacion.json``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .entorno import PLANTILLAS_DIR, raiz_proyecto
from .errores import ErrorMotor
from .guion import Guion, cargar_guion

HASHTAGS_MATERIA = {
    "matematica": ["#matematicas", "#algebra"],
    "fisica": ["#fisica", "#ciencia"],
    "ingenieria": ["#ingenieria", "#electricidad"],
}
HASHTAGS_BASE = [
    "#tuprofeindustrial",
    "#ejerciciosresueltos",
    "#estudiantes",
    "#profe",
    "#aprendeentiktok",
    "#chile",
]

AVISO_IA = "Creado con IA."
_CAMPOS_CON_AVISO = ("descripcion_youtube", "texto_tiktok", "texto_instagram")


def _con_aviso(texto: str) -> str:
    if "creado con ia" in texto.lower():
        return texto
    return f"{texto.rstrip()}\n\n{AVISO_IA}"


class TextosPublicacion(BaseModel):
    titulo_youtube: str = Field(description="Título para YouTube Shorts, máximo 70 caracteres")
    descripcion_youtube: str = Field(description="2 o 3 frases y una invitación a suscribirse, sin hashtags")
    texto_tiktok: str = Field(description="Texto para TikTok, máximo 150 caracteres, invita a comentar")
    texto_instagram: str = Field(description="Texto para Reels: 2 a 4 frases cortas y una pregunta al final")
    hashtags: list[str] = Field(description="De 8 a 12 hashtags en español, cada uno empieza con #")


@dataclass
class Kit:
    carpeta: Path
    portada: Path
    textos: TextosPublicacion
    con_ia: bool
    archivo: Path  # publicacion.md
    aviso: str | None = None  # ej. por qué no se usó la IA


def _carpeta_del_video(entrada: Path) -> Path:
    """Acepta el video, su carpeta o el guion (busca salida/<nombre-del-guion>/)."""
    from .render import slug

    entrada = entrada.expanduser()
    if entrada.is_dir():
        carpeta = entrada
    elif entrada.suffix.lower() in (".yaml", ".yml"):
        carpeta = raiz_proyecto() / "salida" / slug(entrada.stem)
    else:
        carpeta = entrada.parent
    if not (carpeta / "linea_de_tiempo.json").exists():
        raise ErrorMotor(
            f"No encuentro un video creado en «{carpeta}».",
            ayuda="Primero crea el video: ./tpi crear guiones/mi_guion.yaml",
        )
    return carpeta


def guion_del_video(carpeta: Path, linea: dict[str, Any]) -> Path | None:
    """El guion del que salió el video. Los videos de versiones anteriores no lo anotaban: se busca en
    guiones/ el que tiene el mismo nombre que la carpeta del video."""
    from .render import slug

    ruta = Path(linea.get("guion") or "")
    if ruta.is_file():
        return ruta
    for candidato in sorted((raiz_proyecto() / "guiones").rglob("*.yaml")):
        if slug(candidato.stem) == carpeta.name:
            return candidato
    return None


def _video_sin_subtitulos(carpeta: Path, linea: dict[str, Any]) -> Path:
    """El video de Manim antes de quemar subtítulos (el de mejor calidad que haya)."""
    intermedio = Path(linea.get("intermedio") or "")
    candidatos = [intermedio] if intermedio.is_file() else []
    candidatos += sorted(
        carpeta.glob("manim/videos/*/animacion.mp4"), key=lambda p: p.stat().st_size, reverse=True
    )
    candidatos += sorted(p for p in carpeta.glob("*.mp4"))
    for c in candidatos:
        if c.is_file():
            return c
    raise ErrorMotor(f"No encuentro el video en {carpeta}.", ayuda="Vuelve a crearlo con ./tpi crear …")


def crear_portada(carpeta: Path, linea: dict[str, Any]) -> Path:
    from .postproduccion import extraer_cuadro

    gancho = next((b for b in linea["bloques"] if b["seccion"] == "gancho"), linea["bloques"][0])
    momento = gancho["inicio"] + max(0.1, gancho["duracion"] - 0.15)
    return extraer_cuadro(_video_sin_subtitulos(carpeta, linea), momento, carpeta / "portada.png")


def textos_de_plantilla(guion: Guion) -> TextosPublicacion:
    reto = f"\n\n✍️ Ahora tú: {guion.reto.texto}" if guion.reto else ""
    return TextosPublicacion(
        titulo_youtube=guion.titulo[:70],
        descripcion_youtube=f"{guion.gancho.texto}\n{guion.enunciado.texto}. Lo resolvemos paso a paso."
        "\n\nSuscríbete para más ejercicios resueltos.",
        texto_tiktok=f"{guion.gancho.texto} Te leo en los comentarios 👇"[:150],
        texto_instagram=f"{guion.gancho.texto}\n\n{guion.enunciado.texto}{reto}\n\n¿Lo resolviste igual? 👇",
        hashtags=[*HASHTAGS_MATERIA.get(guion.materia, []), *HASHTAGS_BASE],
    )


def textos_con_ia(guion: Guion, modelo: str | None = None) -> TextosPublicacion:
    from . import ia
    from .redactor import pedir_json

    sistema = (PLANTILLAS_DIR / "ia" / "publicar.md").read_text(encoding="utf-8")
    datos = guion.model_dump(exclude_none=True, exclude={"voz", "velocidad", "tema"})
    contenido = [f"GUION DEL VIDEO (JSON):\n{json.dumps(datos, ensure_ascii=False)}"]
    modelo = modelo or ia.MODELO_POR_DEFECTO
    return pedir_json(ia.cliente(), modelo, sistema, contenido, TextosPublicacion, "low")


def _limpiar(textos: TextosPublicacion) -> TextosPublicacion:
    etiquetas = []
    for h in textos.hashtags:
        h = "#" + "".join(h.strip().lstrip("#").split())
        if len(h) > 1 and h.lower() not in (e.lower() for e in etiquetas):
            etiquetas.append(h)
    if "#tuprofeindustrial" not in (e.lower() for e in etiquetas):
        etiquetas.insert(0, "#tuprofeindustrial")
    # TikTok e Instagram piden que el contenido generado por IA se declare en el texto,
    # no solo en la configuración de la cuenta; si ya viene dicho, no se repite.
    textos = textos.model_copy(
        update={c: _con_aviso(getattr(textos, c)) for c in _CAMPOS_CON_AVISO}
    )
    return textos.model_copy(
        update={"hashtags": etiquetas[:12], "titulo_youtube": textos.titulo_youtube[:100]}
    )


def _markdown(textos: TextosPublicacion, guion: Guion) -> str:
    etiquetas = " ".join(textos.hashtags)
    return "\n".join(
        [
            f"# Kit de publicación · {guion.titulo}",
            "",
            "## YouTube Shorts",
            f"**Título:** {textos.titulo_youtube}",
            "",
            textos.descripcion_youtube,
            "",
            etiquetas,
            "",
            "## TikTok",
            f"{textos.texto_tiktok} {etiquetas}",
            "",
            "## Instagram Reels",
            textos.texto_instagram,
            "",
            etiquetas,
            "",
        ]
    )


def crear_kit(
    entrada: Path,
    con_ia: bool = True,
    modelo: str | None = None,
    avisar: Callable[[str], None] = lambda m: None,
) -> Kit:
    from . import ia

    carpeta = _carpeta_del_video(entrada)
    linea = json.loads((carpeta / "linea_de_tiempo.json").read_text(encoding="utf-8"))
    ruta_guion = guion_del_video(carpeta, linea)
    if ruta_guion is None:
        raise ErrorMotor(
            f"No encuentro el guion de este video en guiones/ (busqué uno llamado «{carpeta.name}»).",
            ayuda="Si lo renombraste o borraste, vuelve a crear el video con ./tpi crear guiones/… y repite.",
        )
    guion = cargar_guion(ruta_guion)
    avisar("Creando la portada…")
    portada = crear_portada(carpeta, linea)

    avisos: list[str] = []
    if linea.get("calidad") == "borrador":
        avisos.append(
            "La portada salió del borrador (más pequeña): crea el video final y vuelve a crear el kit."
        )
    usar_ia = con_ia and ia.obtener_clave() is not None
    if con_ia and not usar_ia:
        avisos.append(
            "Sin clave de Gemini: los textos se armaron con una plantilla (./tpi clave para usar IA)."
        )
    textos = None
    if usar_ia:
        avisar("Gemini está escribiendo el título, la descripción y los hashtags…")
        try:
            textos = textos_con_ia(guion, modelo)
        except ErrorMotor as e:  # el kit igual se crea, con la plantilla
            avisos.append(f"No se pudo usar la IA ({e.mensaje}); los textos se armaron con una plantilla.")
    aviso = " ".join(avisos) or None
    con_ia_real = textos is not None
    textos = _limpiar(textos or textos_de_plantilla(guion))

    archivo = carpeta / "publicacion.md"
    archivo.write_text(_markdown(textos, guion), encoding="utf-8")
    datos = {"portada": str(portada), "con_ia": con_ia_real, **textos.model_dump()}
    (carpeta / "publicacion.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return Kit(
        carpeta=carpeta, portada=portada, textos=textos, con_ia=con_ia_real, archivo=archivo, aviso=aviso
    )
