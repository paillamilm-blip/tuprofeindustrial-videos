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

from .entorno import PLANTILLAS_DIR, escribir_atomico, raiz_proyecto
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
LARGO_TIKTOK = 150  # el texto entero, con el aviso de IA incluido
# Lo que el texto de TikTok puede ocupar antes del aviso («\n\nCreado con IA.»).
LARGO_TIKTOK_SIN_AVISO = LARGO_TIKTOK - len(AVISO_IA) - 2


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


def es_ejercicio(guion: Guion) -> bool:
    """¿El video resuelve un ejercicio? Sin ``contenido`` (guiones de antes), sí: su copy no cambia."""
    return guion.contenido is None or "ejercicio" in guion.contenido.intenciones


def textos_de_plantilla(guion: Guion) -> TextosPublicacion:
    reto = f"\n\n✍️ Ahora tú: {guion.reto.texto}" if guion.reto else ""
    if not es_ejercicio(guion):
        # Un dato, mito o error: el copy sale de lo que enseña, sin «lo resolvemos» ni «ejercicios».
        objetivo = guion.contenido.objetivo
        etiquetas = [*HASHTAGS_MATERIA.get(guion.materia, []), *HASHTAGS_BASE]
        return TextosPublicacion(
            titulo_youtube=guion.titulo[:70],
            descripcion_youtube=f"{guion.gancho.texto}\n{objetivo}\n\n{SUSCRIBETE_CONTENIDO}",
            texto_tiktok=f"{guion.gancho.texto} {LLAMADOS_DE_SIEMPRE[0]}"[:150],
            texto_instagram=f"{guion.gancho.texto}\n\n{guion.enunciado.texto}\n{objetivo}{reto}"
            f"\n\n{LLAMADOS_DE_SIEMPRE[0]}",
            hashtags=[h for h in etiquetas if h not in _DE_EJERCICIO],
        )
    return TextosPublicacion(
        titulo_youtube=guion.titulo[:70],
        descripcion_youtube=f"{guion.gancho.texto}\n{guion.enunciado.texto}. Lo resolvemos paso a paso."
        f"\n\n{SUSCRIBETE}",
        texto_tiktok=f"{guion.gancho.texto} {LLAMADOS_DE_SIEMPRE[0]}"[:150],
        texto_instagram=f"{guion.gancho.texto}\n\n{guion.enunciado.texto}{reto}\n\n{LLAMADOS_DE_SIEMPRE[1]}",
        hashtags=[*HASHTAGS_MATERIA.get(guion.materia, []), *HASHTAGS_BASE],
    )


def textos_de_metadatos(guion: Guion) -> TextosPublicacion | None:
    """Los textos que ya trae el guion (bloque ``metadatos``): no hace falta volver a pedirlos."""
    m = guion.metadatos
    if m is None:
        return None
    reto = f"\n\n✍️ Ahora tú: {guion.reto.texto}" if guion.reto else ""
    primera = m.descripcion.split("\n")[0].strip()
    return TextosPublicacion(
        titulo_youtube=m.titulo,
        descripcion_youtube=f"{m.descripcion}\n\n{SUSCRIBETE}",
        texto_tiktok=(primera if len(primera) <= 150 else m.titulo)[:150],
        texto_instagram=f"{m.descripcion}{reto}\n\n{LLAMADOS_DE_SIEMPRE[1]}",
        hashtags=list(m.hashtags),
    )


LLAMADOS_DE_SIEMPRE = ("Te leo en los comentarios 👇", "¿Lo resolviste igual? 👇")
SUSCRIBETE = "Suscríbete para más ejercicios resueltos."
SUSCRIBETE_CONTENIDO = "Suscríbete para entender más matemática, física e ingeniería."
_DE_EJERCICIO = {"#ejerciciosresueltos"}


def segun_contenido(textos: TextosPublicacion, guion: Guion) -> TextosPublicacion:
    """Un dato, mito o error no se anuncia como ejercicio resuelto (vale también para la IA)."""
    if es_ejercicio(guion):
        return textos

    def limpio(texto: str) -> str:
        return texto.replace(LLAMADOS_DE_SIEMPRE[1], LLAMADOS_DE_SIEMPRE[0]).replace(
            SUSCRIBETE, SUSCRIBETE_CONTENIDO
        )

    return textos.model_copy(
        update={
            "descripcion_youtube": limpio(textos.descripcion_youtube),
            "texto_tiktok": limpio(textos.texto_tiktok),
            "texto_instagram": limpio(textos.texto_instagram),
            "hashtags": [h for h in textos.hashtags if h.lower() not in _DE_EJERCICIO],
        }
    )


def _sin_llamado_de_siempre(texto: str) -> str:
    for viejo in LLAMADOS_DE_SIEMPRE:
        texto = texto.replace(viejo, "")
    return texto.rstrip()


def aplicar_llamado(textos: TextosPublicacion, llamado: str | None) -> TextosPublicacion:
    """El llamado a la acción que eligió el profe reemplaza al de siempre en los tres textos.

    Vale para la plantilla, los metadatos del guion y lo que escribió la IA: si la IA ya lo puso, no
    se repite. En TikTok se acorta el resto (nunca el llamado) para no pasar de 150 caracteres.
    """
    llamado = (llamado or "").strip()
    if not llamado:
        return textos

    def con(texto: str, separador: str) -> str:
        if llamado.casefold() in texto.casefold():
            return texto
        base = _sin_llamado_de_siempre(texto)
        return f"{base}{separador}{llamado}" if base else llamado

    tiktok = con(textos.texto_tiktok, " ")
    if len(tiktok) > LARGO_TIKTOK_SIN_AVISO:
        espacio = LARGO_TIKTOK_SIN_AVISO - len(llamado) - 2
        # Sin el llamado que ya traía (de la IA) ni el de siempre: si no, salía dos veces.
        base = _sin_llamado_de_siempre(textos.texto_tiktok)
        donde = base.casefold().find(llamado.casefold())
        if donde >= 0:
            base = (base[:donde] + base[donde + len(llamado) :]).strip()
        tiktok = f"{base[:espacio].rstrip()}… {llamado}" if espacio > 10 and base else llamado
        tiktok = tiktok[:LARGO_TIKTOK_SIN_AVISO]
    youtube = textos.descripcion_youtube
    if llamado.casefold() not in youtube.casefold():
        cierre = next((x for x in (SUSCRIBETE, SUSCRIBETE_CONTENIDO) if x in youtube), None)
        if cierre:
            youtube = youtube.replace(cierre, f"{llamado}\n\n{cierre}")
        else:
            youtube = f"{youtube.rstrip()}\n\n{llamado}"
    return textos.model_copy(
        update={
            "texto_tiktok": tiktok,
            "texto_instagram": con(textos.texto_instagram, "\n\n"),
            "descripcion_youtube": youtube,
        }
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
    tiktok = textos.texto_tiktok
    if "creado con ia" not in tiktok.lower() and len(tiktok) > LARGO_TIKTOK_SIN_AVISO:
        # El aviso no puede empujar el texto sobre el máximo: se acorta lo de antes, no el aviso.
        textos = textos.model_copy(
            update={"texto_tiktok": tiktok[: LARGO_TIKTOK_SIN_AVISO - 1].rstrip() + "…"}
        )
    textos = textos.model_copy(update={c: _con_aviso(getattr(textos, c)) for c in _CAMPOS_CON_AVISO})
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
    if con_ia and not usar_ia and guion.metadatos is None:
        avisos.append(
            "Sin clave de Gemini: los textos se armaron con una plantilla (./tpi clave para usar IA)."
        )
    textos = textos_de_metadatos(guion)
    if textos is not None:
        avisar("El guion ya trae título, descripción y hashtags: uso esos.")
    elif usar_ia:
        avisar("Gemini está escribiendo el título, la descripción y los hashtags…")
        try:
            textos = textos_con_ia(guion, modelo)
        except ErrorMotor as e:  # el kit igual se crea, con la plantilla
            avisos.append(f"No se pudo usar la IA ({e.mensaje}); los textos se armaron con una plantilla.")
        except Exception as e:  # una caída rara de la IA no debe botar un video ya hecho
            avisos.append(f"No se pudo usar la IA ({e}); los textos se armaron con una plantilla.")
    aviso = " ".join(avisos) or None
    con_ia_real = textos is not None and guion.metadatos is None
    textos = textos or textos_de_plantilla(guion)
    textos = _limpiar(segun_contenido(aplicar_llamado(textos, guion.llamado), guion))

    archivo = carpeta / "publicacion.md"
    escribir_atomico(archivo, _markdown(textos, guion))
    datos = {"portada": str(portada), "con_ia": con_ia_real, **textos.model_dump()}
    escribir_atomico(carpeta / "publicacion.json", json.dumps(datos, ensure_ascii=False, indent=2))
    return Kit(
        carpeta=carpeta, portada=portada, textos=textos, con_ia=con_ia_real, archivo=archivo, aviso=aviso
    )
