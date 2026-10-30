"""Lo que el panel decide solo, y cómo se le muestra con su «cambiar».

Sin widgets y sin NiceGUI: acá sólo hay datos y frases. Así se prueba sin navegador, y la pantalla
no puede prometer nada que el motor no cumpla: cada pieza que se muestra es una que ``tpi producir``
recibe por bandera, o una que se cambia en otro lado (el rodaje, en Ajustes).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..formatos import (
    FORMATO_POR_DEFECTO,
    Formato,
    cargar_formatos,
    formato,
    palabra_que_delata,
    puntuar_idea,
)
from ..moldes import MOLDES, nombre_molde, normalizar_molde
from ..rodaje import QUE_HACE, RECETA_LIBRE, Receta, rodaje_para
from ..temas import listar_temas

# Las piezas de la tarjeta «Así está armado». «rodaje» no es una bandera: se cambia en Ajustes.
ETIQUETAS = {
    "familia": "Familia",
    "molde": "Molde",
    "tema": "Estilo",
    "voz": "Voz",
    "segundos": "Duración",
    "gancho": "Gancho",
    "rodaje": "Rodaje",
}
BANDERAS = {  # cada pieza con la bandera real de `tpi producir`
    "molde": "--molde",
    "tema": "--estilo",
    "voz": "--voz",
    "segundos": "--segundos",
    "gancho": "--gancho",
}
LIBRE = RECETA_LIBRE  # la receta de los videos que no llevan molde
# Los cuatro mandos que se ven en la pantalla; los otros cuatro sólo cambian una letra del guion.
MANDOS_VISTOS = (("gancho", "La apertura"), ("pasos", "Los pasos"), ("deriva", "El cuadro"), ("partida", "El tablero"))


@dataclass(frozen=True)
class Preferencias:
    """Lo que ya está guardado en Ajustes: el estilo y la voz de siempre, con sus nombres para mostrar."""

    tema: str = "hoja_de_desarrollo"
    voz: str = "es-CL-LorenzoNeural"
    voces: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Pieza:
    clave: str
    etiqueta: str
    valor: str  # lo que ella lee en la tarjeta
    codigo: str | None  # lo que recibe el motor; None = lo decide la IA
    razon: str
    tocada: bool = False  # lo cambió ella: la pantalla lo dice
    destino: str | None = None  # una pieza sin bandera dice dónde se cambia


@dataclass(frozen=True)
class Sugerencia:
    idea: str
    familia: str | None
    piezas: tuple[Pieza, ...]
    args: tuple[str, ...]
    motivo: str
    kit: bool = True
    rodaje: Receta = RECETA_LIBRE

    @property
    def clave_familia(self) -> str:
        """La familia que se dibuja en la portada: si la frase no delata ninguna, la de siempre."""
        return self.familia or FORMATO_POR_DEFECTO

    def pieza(self, clave: str) -> Pieza | None:
        return next((p for p in self.piezas if p.clave == clave), None)

    def bloqueada(self) -> str | None:
        """Por qué todavía no se puede crear (None si ya se puede)."""
        return "Escribe el tema o pega el enunciado." if not self.idea.strip() else None


def opciones(clave: str) -> dict[str, str]:
    """Las opciones reales de cada pieza: las mismas listas del motor, nunca una copia a mano.

    El hueco en la primera clave siempre significa «que decida la IA».
    """
    if clave == "familia":
        return {c: f.nombre for c, f in cargar_formatos().items()}
    if clave == "molde":
        return {c: m.nombre for c, m in MOLDES.items()}
    if clave == "tema":
        return {ident: tema.nombre for ident, tema, _propio in listar_temas()}
    if clave == "segundos":
        return {str(n): f"≈{n} s" for n in (30, 40, 50, 60, 70)}
    return {}


def armar(
    idea: str,
    cambios: dict[str, str],
    preferencias: Preferencias,
    propuesta: dict | None = None,
    kit: bool = True,
) -> Sugerencia:
    """La receta con la que se crea el video: valor, razón y bandera de cada pieza.

    `propuesta` es una de las 3 ideas de la IA (ya en dict): si trae molde, gancho o duración, ese
    valor deja de ser «lo decide la IA» y pasa a ser «lo trajo la idea que elegiste».
    """
    idea = (idea or "").strip()
    propuesta = propuesta or {}
    la_familia, toco_familia = _familia(idea, cambios)
    el_molde = _una_molde(la_familia, cambios, propuesta)
    piezas = (
        _una_familia(la_familia, toco_familia, idea),
        el_molde,
        _una_tema(la_familia, cambios, preferencias),
        _una_voz(cambios, preferencias),
        _una_duracion(cambios, propuesta),
        _un_gancho(cambios, propuesta),
        _un_rodaje(el_molde.codigo),
    )
    return Sugerencia(
        idea=idea,
        familia=la_familia.clave if la_familia else None,
        piezas=piezas,
        args=_args(idea, piezas, propuesta, kit),
        motivo=_motivo(la_familia, toco_familia, idea),
        kit=kit,
        rodaje=rodaje_para(el_molde.codigo or LIBRE),
    )


def _familia(texto: str, cambios: dict[str, str]) -> tuple[Formato | None, bool]:
    """La familia activa con la marca de si la puso ella (None si la frase no la delata)."""
    familias = cargar_formatos()
    if "familia" in cambios:
        clave = cambios["familia"]
        return ((formato(clave), True) if clave in familias else (None, True))
    clave = puntuar_idea(texto)
    return ((formato(clave), False) if clave in familias else (None, False))


def _motivo(la_familia, toco: bool, texto: str) -> str:
    if toco:
        return "Elegida por ti." if la_familia else "Pediste que lo decida la IA."
    if la_familia is None:
        return (
            f"No reconocí una familia en «{texto[:60]}»: va {formato(FORMATO_POR_DEFECTO).nombre}."
            if texto
            else "Todavía no escribiste nada."
        )
    palabra = palabra_que_delata(texto, la_familia.clave)
    return f"Tu frase dijo «{palabra}»: es {la_familia.nombre}." if palabra else f"Elegida: {la_familia.nombre}."


def _una_familia(la_familia, toco: bool, texto: str) -> Pieza:
    return Pieza(
        clave="familia",
        etiqueta=ETIQUETAS["familia"],
        valor=(la_familia or formato(FORMATO_POR_DEFECTO)).nombre,
        codigo=la_familia.clave if la_familia else None,
        razon=_motivo(la_familia, toco, texto),
        tocada=toco,
    )


def _una_molde(la_familia, cambios: dict[str, str], propuesta: dict) -> Pieza:
    ia = normalizar_molde(str(propuesta.get("molde") or ""))
    if "molde" in cambios:
        codigo, razon, tocada = (normalizar_molde(cambios["molde"]) or None), "Cambiado por ti.", True
    elif ia:
        codigo, razon, tocada = ia, "Lo trajo la idea que elegiste.", False
    elif la_familia and la_familia.moldes:
        codigo, razon, tocada = la_familia.moldes[0], f"Viene de {la_familia.nombre}.", False
    else:
        codigo, razon, tocada = None, "Tu frase no delató un molde: lo decide la IA.", False
    return Pieza("molde", ETIQUETAS["molde"], nombre_molde(codigo), codigo, razon, tocada)


def _una_tema(la_familia, cambios: dict[str, str], pref: Preferencias) -> Pieza:
    if "tema" in cambios:
        codigo, razon, tocada = (cambios["tema"] or pref.tema), "Cambiado por ti.", True
    elif la_familia:
        codigo, razon, tocada = la_familia.tema, f"El estilo de {la_familia.nombre}.", False
    else:
        codigo, razon, tocada = pref.tema, "Tu estilo de siempre (Ajustes).", False
    return Pieza("tema", ETIQUETAS["tema"], _nombre_tema(codigo), codigo, razon, tocada)


def _una_voz(cambios: dict[str, str], pref: Preferencias) -> Pieza:
    codigo = cambios.get("voz") or pref.voz
    return Pieza(
        clave="voz",
        etiqueta=ETIQUETAS["voz"],
        valor=pref.voces.get(codigo, codigo),
        codigo=codigo,
        razon="Cambiada por ti." if "voz" in cambios else "Tu voz de siempre (Ajustes).",
        tocada="voz" in cambios,
    )


def _una_duracion(cambios: dict[str, str], propuesta: dict) -> Pieza:
    if "segundos" in cambios:
        codigo, razon, tocada = (cambios["segundos"] or None), "Cambiado por ti.", True
    elif propuesta.get("segundos"):
        codigo, razon, tocada = str(propuesta["segundos"]), "Lo prometió la idea.", False
    else:
        codigo, razon, tocada = None, "La IA decide el largo (entre 30 y 75 s).", False
    return Pieza(
        clave="segundos",
        etiqueta=ETIQUETAS["segundos"],
        valor=f"≈{codigo} s" if codigo else "lo decide la IA",
        codigo=codigo,
        razon=razon,
        tocada=tocada,
    )


def _un_gancho(cambios: dict[str, str], propuesta: dict) -> Pieza:
    propio = (cambios.get("gancho") or "").strip()
    codigo = propio or str(propuesta.get("gancho") or "").strip()
    razon = (
        "Escrito por ti."
        if propio
        else ("Lo escribió la idea." if codigo else "La IA lo escribe al redactar el guion.")
    )
    return Pieza(
        clave="gancho",
        etiqueta=ETIQUETAS["gancho"],
        valor=f"«{codigo}»" if codigo else "lo escribe la IA",
        codigo=codigo or None,
        razon=razon,
        tocada=bool(propio),
    )


def _un_rodaje(molde: str | None) -> Pieza:
    return Pieza(
        clave="rodaje",
        etiqueta=ETIQUETAS["rodaje"],
        valor=f"La receta de {nombre_molde(molde)} · 8 mandos",
        codigo=None,
        razon="Se cambia en Ajustes → Rodaje, no viaja al crear.",
        destino="/ajustes",
    )


def anotaciones(receta: Receta) -> tuple[str, ...]:
    """Lo que se ve moverse, en frases cortas, para escribirlas encima de la portada."""
    return tuple(QUE_HACE[clave][getattr(receta, clave)] for clave, _nombre in MANDOS_VISTOS)


def _nombre_tema(codigo: str | None) -> str:
    for ident, tema, _propio in listar_temas():
        if ident == codigo:
            return tema.nombre
    return codigo or "sin estilo"


def _args(idea: str, piezas: tuple[Pieza, ...], propuesta: dict, kit: bool) -> tuple[str, ...]:
    """El comando exacto. Las variantes de gancho de la IA viajan en JSON, como en Fábrica."""
    args = ["producir"]
    for clave in ("materia", "nivel", "titulo"):
        if propuesta.get(clave):
            args += [f"--{clave}", str(propuesta[clave])]
    for pieza in piezas:
        bandera = BANDERAS.get(pieza.clave)
        if bandera and pieza.codigo and bandera != "--gancho":
            args += [bandera, str(pieza.codigo)]
    gancho = next((p for p in piezas if p.clave == "gancho"), None)
    if gancho and gancho.tocada and gancho.codigo:
        args += ["--gancho", gancho.codigo]
    elif gancho and gancho.codigo:
        variante = propuesta.get("gancho_elegido")
        args += ["--gancho-json", _json(variante)] if variante else ["--gancho", gancho.codigo]
    if propuesta.get("ganchos"):
        args += ["--ganchos-json", _json(list(propuesta["ganchos"]))]
    if not kit:
        args += ["--sin-kit"]
    if idea:
        args += ["--", idea]
    return tuple(args)


def _json(datos) -> str:
    return json.dumps(datos, ensure_ascii=False)
