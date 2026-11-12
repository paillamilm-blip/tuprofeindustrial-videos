"""La lógica de la pantalla única «Estudio» (sin NiceGUI, para poder probarla sola).

El flujo: idea + nivel + tipo de contenido → guion para revisar (gancho, dibujos, cierre y llamado a
la acción) → video. Aquí vive todo lo que no es dibujar la pantalla: qué molde corresponde a cada
tipo, los comandos que se lanzan, las sugerencias de cierre y de llamado, los atajos guardados y los
cambios al guion. Cada cambio se valida con ``Guion`` antes de escribir: un clic nunca deja un guion
que el motor no pueda leer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..entorno import raiz_proyecto
from ..errores import ErrorMotor
from ..ganchos import elegir_gancho
from ..guion import Guion, a_yaml, cabecera_de, cargar_guion, explicar_errores, sin_tildes
from ..niveles import NIVELES
from ..visuales import VISUALES


@dataclass(frozen=True)
class Tipo:
    clave: str
    nombre: str
    molde: str  # "" = paso a paso (libre)
    ayuda: str  # una línea bajo los chips: qué video sale
    ejemplo: str  # el texto de ejemplo dentro del cuadro de la idea
    cierres: tuple[str, ...]  # lo que se dice al final del video
    llamados: tuple[str, ...]  # el cierre del texto de la publicación


TIPOS: dict[str, Tipo] = {
    t.clave: t
    for t in (
        Tipo(
            "pasos",
            "Paso a paso",
            "",
            "Resuelve el ejercicio de principio a fin, explicando el porqué de cada paso.",
            "Ej.: Una escalera de 5 m se apoya en una pared a 3 m de la base. ¿A qué altura toca la pared?",
            (
                "Ejercicio resuelto paso a paso",
                "Ya sabes cómo se hace",
                "Ahora te toca a ti",
            ),
            (
                "¿Lo resolviste igual? Cuéntame 👇",
                "Guárdalo para tu próxima prueba 📌",
                "¿Qué ejercicio quieres que resuelva? 👇",
            ),
        ),
        Tipo(
            "error",
            "Error común",
            "tres_errores",
            "Muestra los errores que casi todos cometen y después la forma correcta.",
            "Ej.: Los errores típicos al despejar x en 2x + 6 = 14",
            (
                "Ahora ya no vas a caer",
                "El error más común, resuelto",
                "Ahora lo haces bien",
            ),
            (
                "¿Cuál de estos errores cometías? 👇",
                "Etiqueta a quien siempre se equivoca aquí 😅",
                "Guárdalo antes de tu prueba 📌",
            ),
        ),
        Tipo(
            "mito",
            "Mito",
            "mito_realidad",
            "Parte de algo que todos creen, demuestra por qué falla y muestra la verdad.",
            "Ej.: ¿(a + b)² es a² + b²?",
            (
                "Mito derribado",
                "Ahora sabes la verdad",
                "No te dejes engañar",
            ),
            (
                "¿Tú también lo creías? Cuéntame 👇",
                "Compártelo con quien todavía lo cree 🤯",
                "¿Qué otro mito derribamos? 👇",
            ),
        ),
        Tipo(
            "dato",
            "Dato curioso",
            "nadie_te_enseno",
            "Un dato que contradice la intuición, demostrado resolviendo.",
            'Ej.: Una TV de 55" no mide 55 pulgadas de ancho',
            (
                "Nadie te lo había contado",
                "Ahora lo sabes",
                "Ahora ya no lo olvidas",
            ),
            (
                "¿Lo sabías? Cuéntame 👇",
                "Compártelo con alguien que no lo sepa 🤯",
                "¿Qué otro dato quieres ver? 👇",
            ),
        ),
        Tipo(
            "reto",
            "Reto",
            "reto",
            "Resuelve uno y deja otro parecido para que el estudiante lo intente.",
            "Ej.: Si un auto va a 72 km/h, ¿cuántos metros recorre en 5 s?",
            (
                "Ahora te toca a ti",
                "¿Te atreves con el siguiente?",
                "Inténtalo antes de mirar la respuesta",
            ),
            (
                "¿Te atreves? Escribe tu respuesta 👇",
                "El primero en responder bien gana 🏆",
                "Responde sin mirar la solución 👇",
            ),
        ),
    )
}
TIPO_POR_DEFECTO = "pasos"
LARGO_MINIMO_IDEA = 8  # menos que esto no alcanza para un ejercicio
LARGO_GANCHO = 70
LARGO_CIERRE = 60
LARGO_LLAMADO = 150


def tipo_de_molde(molde: str | None) -> str:
    """El tipo de contenido que corresponde a un molde (un molde sin tipo propio = paso a paso)."""
    for tipo in TIPOS.values():
        if tipo.molde and tipo.molde == (molde or ""):
            return tipo.clave
    return TIPO_POR_DEFECTO


def _tipo(clave: str) -> Tipo:
    try:
        return TIPOS[clave]
    except KeyError:
        raise ErrorMotor(f"No conozco el tipo «{clave}».", ayuda="Elige uno de los chips.") from None


def revisar_idea(idea: str) -> str | None:
    """Por qué la idea todavía no sirve (o None si sirve). Lo que se muestra bajo el cuadro."""
    texto = " ".join((idea or "").split())
    if not texto:
        return "Escribe el ejercicio o la idea del video."
    if len(texto) < LARGO_MINIMO_IDEA:
        return "Cuéntame un poco más: el ejercicio con sus datos."
    return None


# ------------------------------------------------------------------------------------------
# Los comandos que lanza la pantalla
# ------------------------------------------------------------------------------------------


def args_redactar(idea: str, nivel: str | None, tipo: str) -> list[str]:
    """``tpi redactar`` con el molde del tipo. La idea va al final, tras «--» (puede empezar con «-»)."""
    problema = revisar_idea(idea)
    if problema:
        raise ErrorMotor(problema)
    args = ["redactar"]
    molde = _tipo(tipo).molde
    if molde:
        args += ["--molde", molde]
    if nivel:
        if nivel not in NIVELES:
            raise ErrorMotor(f"No conozco el nivel «{nivel}».", ayuda="Elige uno de la lista.")
        args += ["--nivel", nivel]
    return [*args, "--", " ".join(idea.split())]


def args_video(ruta: Path, borrador: bool = False) -> list[str]:
    """``tpi crear``: el final trae también el kit (portada y textos); el borrador es solo para mirar."""
    return ["crear", str(ruta), "--borrador"] if borrador else ["crear", str(ruta), "--kit"]


def args_redibujar(ruta: Path, paso: int, dibujo: str) -> list[str]:
    return ["redibujar", str(ruta), "--paso", str(paso), "--tipo", dibujo]


# ------------------------------------------------------------------------------------------
# Atajos: lo último que se usó, para repetirlo con un clic
# ------------------------------------------------------------------------------------------

MAX_ATAJOS = 6


def _archivo_atajos() -> Path:
    return raiz_proyecto() / "mis_ajustes" / "estudio.json"


def cargar_atajos() -> dict[str, Any]:
    """``{"nivel": …, "tipo": …, "recientes": [{"idea", "nivel", "tipo"}, …]}``. Si el archivo está
    roto o no existe, se parte de cero: nunca bota la pantalla."""
    vacio: dict[str, Any] = {"nivel": "", "tipo": TIPO_POR_DEFECTO, "recientes": []}
    try:
        datos = json.loads(_archivo_atajos().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return vacio
    if not isinstance(datos, dict):
        return vacio
    nivel = datos.get("nivel") if datos.get("nivel") in NIVELES else ""
    tipo = datos.get("tipo") if datos.get("tipo") in TIPOS else TIPO_POR_DEFECTO
    recientes = []
    for r in datos.get("recientes") or []:
        if isinstance(r, dict) and isinstance(r.get("idea"), str) and r["idea"].strip():
            recientes.append(
                {
                    "idea": r["idea"].strip(),
                    "nivel": r.get("nivel") if r.get("nivel") in NIVELES else "",
                    "tipo": r.get("tipo") if r.get("tipo") in TIPOS else TIPO_POR_DEFECTO,
                }
            )
    return {"nivel": nivel, "tipo": tipo, "recientes": recientes[:MAX_ATAJOS]}


def recordar(idea: str, nivel: str | None, tipo: str) -> dict[str, Any]:
    """Guarda el nivel y el tipo para la próxima vez, y la idea al inicio de los recientes."""
    atajos = cargar_atajos()
    idea = " ".join(idea.split())
    clave = sin_tildes(idea).casefold()
    otros = [r for r in atajos["recientes"] if sin_tildes(r["idea"]).casefold() != clave]
    atajos = {
        "nivel": nivel if nivel in NIVELES else "",
        "tipo": tipo if tipo in TIPOS else TIPO_POR_DEFECTO,
        "recientes": [{"idea": idea, "nivel": nivel or "", "tipo": tipo}, *otros][:MAX_ATAJOS],
    }
    archivo = _archivo_atajos()
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(atajos, ensure_ascii=False, indent=2), encoding="utf-8")
    return atajos


def resumen_atajo(atajo: dict[str, Any], largo: int = 46) -> str:
    """«Mito · 1° medio · ¿(a + b)² es a² + b²?» acortado para un chip."""
    partes = [TIPOS[atajo["tipo"]].nombre, atajo.get("nivel") or ""]
    idea = atajo["idea"]
    corta = idea if len(idea) <= largo else idea[: largo - 1].rstrip() + "…"
    return " · ".join(p for p in [*partes, corta] if p)


# ------------------------------------------------------------------------------------------
# Cambios al guion desde la pantalla de revisión
# ------------------------------------------------------------------------------------------


def ruta_de_guion(valor: str | Path) -> Path:
    """La ruta de un guion que esta pantalla puede abrir y modificar: solo un .yaml dentro de guiones/.

    La URL (``/?guion=…``) la puede escribir cualquiera; sin esto, un enlace podría hacer que el panel
    reescriba un archivo cualquiera del computador.
    """
    carpeta = (raiz_proyecto() / "guiones").resolve()
    ruta = Path(valor).expanduser()
    if not ruta.is_absolute():
        ruta = raiz_proyecto() / ruta
    ruta = ruta.resolve()
    if ruta.suffix.lower() not in (".yaml", ".yml") or not ruta.is_relative_to(carpeta):
        raise ErrorMotor(
            "Solo se pueden abrir aquí los guiones de la carpeta guiones/.",
            ayuda=f"«{valor}» está fuera de esa carpeta.",
        )
    if not ruta.is_file():
        raise ErrorMotor(f"No encuentro el guion «{ruta.name}».", ayuda="¿Lo borraste o lo renombraste?")
    return ruta


def guardar(ruta: Path, datos: dict[str, Any]) -> Guion:
    """Valida y escribe. Si algo no vale, lanza ErrorMotor con la explicación y el archivo no cambia."""
    try:
        guion = Guion.model_validate(datos)
    except Exception as e:
        detalle = "; ".join(explicar_errores(e)) if hasattr(e, "errors") else str(e)
        raise ErrorMotor("Ese cambio deja el guion incompleto.", ayuda=detalle[:300]) from e
    ruta.write_text(a_yaml(guion.model_dump(), cabecera_de(ruta)), encoding="utf-8")
    return cargar_guion(ruta)  # comprueba que lo escrito se lee igual


def _texto(valor: str, largo: int, que: str) -> str:
    texto = " ".join((valor or "").split())
    if not texto:
        raise ErrorMotor(f"{que} no puede quedar vacío.")
    if len(texto) > largo:
        raise ErrorMotor(f"{que} es muy largo: máximo {largo} caracteres (lleva {len(texto)}).")
    return texto


def usar_gancho(ruta: Path, numero: int) -> Guion:
    """Pone la alternativa ``numero`` (2, 3…; el 1 es el actual) como gancho del video."""
    elegir_gancho(ruta, numero)
    return cargar_guion(ruta)


def escribir_gancho(ruta: Path, texto: str) -> Guion:
    """Un gancho escrito a mano. El de antes queda como alternativa, por si se arrepiente.

    La fórmula y los destacados del gancho anterior no se heredan: hablaban de otra frase.
    """
    texto = _texto(texto, LARGO_GANCHO, "El gancho")
    guion = cargar_guion(ruta)
    datos = guion.model_dump()
    anterior = guion.gancho.model_dump(exclude_none=True)
    if sin_tildes(anterior.get("texto", "")).casefold() == sin_tildes(texto).casefold():
        return guion
    nuevo: dict[str, Any] = {"texto": texto}
    if guion.gancho.emoji:
        nuevo["emoji"] = guion.gancho.emoji
    clave = sin_tildes(texto).casefold()
    variantes = [anterior] + [
        v.model_dump(exclude_none=True)
        for v in guion.gancho_variantes
        if sin_tildes(v.texto).casefold() != clave
    ]
    datos["gancho"] = nuevo
    datos["gancho_variantes"] = variantes[:5]
    return guardar(ruta, datos)


def cambiar_cierre(ruta: Path, texto: str) -> Guion:
    """Lo que se lee y se dice al final del video (la voz es la misma frase)."""
    texto = _texto(texto, LARGO_CIERRE, "El cierre")
    guion = cargar_guion(ruta)
    datos = guion.model_dump()
    emoji = guion.cierre.emoji if guion.cierre else None
    datos["cierre"] = {"texto": texto, "voz": texto, **({"emoji": emoji} if emoji else {})}
    return guardar(ruta, datos)


def cambiar_llamado(ruta: Path, texto: str) -> Guion:
    """El cierre del texto de la publicación. Vacío = vuelve el de siempre."""
    guion = cargar_guion(ruta)
    datos = guion.model_dump()
    limpio = " ".join((texto or "").split())
    if len(limpio) > LARGO_LLAMADO:
        raise ErrorMotor(f"El llamado es muy largo: máximo {LARGO_LLAMADO} caracteres.")
    datos["llamado"] = limpio or None
    return guardar(ruta, datos)


def _paso(guion: Guion, numero: int) -> int:
    if not 1 <= numero <= len(guion.pasos):
        raise ErrorMotor(f"El guion tiene {len(guion.pasos)} pasos: no hay un paso {numero}.")
    return numero - 1


def quitar_dibujo(ruta: Path, numero: int) -> Guion:
    guion = cargar_guion(ruta)
    i = _paso(guion, numero)
    datos = guion.model_dump()
    datos["pasos"][i]["visual"] = None
    return guardar(ruta, datos)


def cambiar_paso(ruta: Path, numero: int, nota: str | None = None, voz: str | None = None) -> Guion:
    """Lo que dice la nota (en pantalla) o la voz de un paso. La fórmula no se toca aquí."""
    guion = cargar_guion(ruta)
    i = _paso(guion, numero)
    datos = guion.model_dump()
    if nota is not None:
        datos["pasos"][i]["nota"] = " ".join(nota.split()) or None
    if voz is not None:
        datos["pasos"][i]["voz"] = _texto(voz, 600, "Lo que dice la voz")
    return guardar(ruta, datos)


# ------------------------------------------------------------------------------------------
# Animaciones: qué dibujo ofrecer al tocar «Cambiar»
# ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Opcion:
    dibujo: str  # el nombre corto que entiende ``tpi redibujar``
    nombre: str
    icono: str


def _corto(tipo: str) -> str | None:
    from ..redactor import _DIBUJOS

    for corto, largo in _DIBUJOS.items():
        if largo == tipo:
            return corto
    return None


def animaciones_sugeridas(guion: Guion, numero: int, maximo: int = 8) -> list[Opcion]:
    """Los dibujos de la misma materia del guion (sin el que ya tiene ese paso), y al final los de las
    otras materias que suelen servir (gráfico, barras, escala). Solo los que la IA sabe armar."""
    i = _paso(guion, numero)
    actual = guion.pasos[i].visual.tipo if guion.pasos[i].visual else ""
    comunes = ("grafico_funcion", "escala", "barras")
    propios = [t for t in VISUALES.values() if t.materia == guion.materia]
    otros = [VISUALES[c] for c in comunes if c in VISUALES and VISUALES[c].materia != guion.materia]
    opciones: list[Opcion] = []
    for tipo in [*propios, *otros]:
        corto = _corto(tipo.clave)
        if corto is None or tipo.clave == actual or any(o.dibujo == corto for o in opciones):
            continue
        opciones.append(Opcion(corto, tipo.nombre, tipo.icono))
    return opciones[:maximo]


def nombre_dibujo(tipo: str | None) -> str:
    if not tipo:
        return "Sin dibujo"
    info = VISUALES.get(tipo)
    return info.nombre if info else tipo
