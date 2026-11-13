"""Temas visuales: todo lo que define cómo se ve un video (marco, colores, letras, fondo, subtítulos).

- Los temas incluidos están en ``plantillas/temas/``: la familia Consola neón, una variante por cada
  forma de contenido (paso a paso, error, mito, dato y reto). Cada forma elige la suya sola.
- Los 20 estilos anteriores viven en ``plantillas/temas/archivo/``: no se listan ni se sugieren, pero
  siguen funcionando si algo los pide por su nombre (un guion con ``tema:``, ``--tema`` o un video viejo
  que se rehace). Para volver a usar uno, basta con moverlo de vuelta a ``plantillas/temas/``.
- Los temas propios (creados en el panel) viven en ``mis_ajustes/temas/``. Git ignora esa carpeta, así
  que actualizar el motor nunca choca con ellos. Si un tema propio tiene el mismo nombre que uno
  incluido, se usa el propio.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .config import Colores, ColoresMateria, EstiloSubtitulos, Marca, _validar_hex
from .entorno import PAQUETE, PLANTILLAS_DIR, raiz_proyecto
from .errores import ErrorMotor
from .tipografia import existe

TEMAS_DIR = PLANTILLAS_DIR / "temas"
ARCHIVO_DIR = TEMAS_DIR / "archivo"  # los estilos retirados: se cargan por nombre, no se ofrecen
FONDOS_DIR = PAQUETE / "assets" / "fondos"
TEMA_POR_DEFECTO = "consola_pasos"

# ------------------------------------------------------------------------------------------
# El estilo sugerido: el ÚNICO lugar del motor que decide cómo se ve un video que nadie eligió.
# Lo usan el render, la vista previa, el QC y la tarjeta «Así está armado». Solo estilos que ya
# existen en plantillas/temas/ (una prueba lo exige): estas tablas eligen, no crean nada.
#
# Regla de la familia Consola neón: la FORMA de entregar el contenido decide el estilo. La materia
# y los dibujos ya no cambian la apariencia: todos los videos comparten letra, fondo oscuro y
# estructura, y solo el color y las herramientas dicen qué tipo de video es.
# ------------------------------------------------------------------------------------------

NOMBRE_CATEGORIA = {"matematicas": "Matemáticas", "fisica": "Física", "ingenieria": "Ingeniería"}

# 1° El molde: cada forma de contenido tiene su variante.
TEMA_POR_MOLDE: dict[str, str] = {
    "pov": "consola_pasos",
    "tres_errores": "consola_error",
    "mito_realidad": "consola_mito",
    "nadie_te_enseno": "consola_dato",
    "reto": "consola_reto",
}
MOTIVO_POR_MOLDE = {
    "pov": "Un paso a paso: pasos numerados y panel que acumula, en cian.",
    "tres_errores": "Tres errores: se tachan en rojo y el contador lleva la cuenta.",
    "mito_realidad": "Mito vs realidad: tablero partido en violeta, sin pasos numerados.",
    "nadie_te_enseno": "Un dato sorpresa: limpio, en ámbar, con la respuesta tapada.",
    "reto": "Un reto: pasos numerados en verde y la respuesta tapada para que lo intentes.",
}

# 2° Sin molde, si corrige un error típico.
TEMA_DE_ERROR = "consola_error"
MOTIVO_DE_ERROR = "Corrige un error típico: el rojo de la familia lo marca."

# 3° Sin molde ni error: es un ejercicio paso a paso.
TEMA_DE_PASOS = "consola_pasos"
MOTIVO_DE_PASOS = "Un ejercicio paso a paso: pasos numerados y panel que acumula."

# Las cinco variantes, en el orden en que se muestran (catálogo, QC y ./tpi temas).
FAMILIA: tuple[str, ...] = ("consola_pasos", "consola_error", "consola_mito", "consola_dato", "consola_reto")


class EstiloSugerido(BaseModel):
    """Qué estilo lleva un video y por qué, en una frase que se le puede mostrar a una persona."""

    model_config = ConfigDict(frozen=True)

    clave: str
    razon: str
    origen: Literal["guion", "molde", "error", "forma"]


def sugerir_tema(
    *,
    molde: str | None = None,
    categoria: str | None = None,
    dibujos: set[str] | frozenset[str] = frozenset(),
    con_error: bool = False,
    de_siempre: str | None = None,
) -> EstiloSugerido:
    """El estilo que le toca a un video según su forma de contenido (sin mirar el ``tema:``).

    1° su molde · 2° si corrige un error · 3° paso a paso. ``categoria``, ``dibujos`` y ``de_siempre``
    se aceptan para no romper a quien los pasa, pero ya no cambian el estilo: en la familia Consola
    neón la materia y los dibujos no deciden la apariencia.
    """
    del categoria, dibujos, de_siempre
    if molde in TEMA_POR_MOLDE:
        return EstiloSugerido(clave=TEMA_POR_MOLDE[molde], razon=MOTIVO_POR_MOLDE[molde], origen="molde")
    if con_error:
        return EstiloSugerido(clave=TEMA_DE_ERROR, razon=MOTIVO_DE_ERROR, origen="error")
    return EstiloSugerido(clave=TEMA_DE_PASOS, razon=MOTIVO_DE_PASOS, origen="forma")


def sugerir_tema_de_guion(guion: Any, marca: Marca | None = None) -> EstiloSugerido:
    """La sugerencia para un guion ya escrito: lee su molde, sus dibujos, sus errores y su materia."""
    pasos = list(getattr(guion, "pasos", None) or [])
    dibujos = {str(p.visual.tipo) for p in pasos if getattr(p, "visual", None) is not None}
    gancho = getattr(guion, "gancho", None)
    if getattr(gancho, "visual", None) is not None:
        dibujos.add(str(gancho.visual.tipo))
    return sugerir_tema(
        molde=getattr(guion, "molde", None),
        categoria=getattr(guion, "categoria", None),
        dibujos=dibujos,
        con_error=any(getattr(p, "error", False) for p in pasos),
        de_siempre=marca.tema if marca else None,
    )


def estilo_del_guion(guion: Any, marca: Marca | None = None) -> EstiloSugerido:
    """El estilo con que saldrá el guion: el que se eligió en QC (``tema:``) o, si no, el sugerido."""
    elegido = str(getattr(guion, "tema", None) or "").strip()
    if elegido:
        return EstiloSugerido(clave=elegido, razon="Elegido por ti en Aprobación de Guiones.", origen="guion")
    return sugerir_tema_de_guion(guion, marca)


def cuando_se_sugiere(clave: str) -> list[str]:
    """En qué videos sugiere el motor este estilo, en frases cortas (para el catálogo de estilos)."""
    from .moldes import nombre_molde

    casos = [f"molde {nombre_molde(m)}" for m, t in TEMA_POR_MOLDE.items() if t == clave]
    if clave == TEMA_DE_ERROR:
        casos.append("videos que corrigen un error")
    if clave == TEMA_DE_PASOS:
        casos.append("ejercicios sin molde")
    return casos


def resolver_tema(manual: str | None, guion: Any | None, marca: Marca) -> str:
    """Qué estilo lleva un video, en cascada.

    1° Lo que se pidió en la llamada (``--tema`` en la Terminal). 2° El ``tema:`` del guion (lo que
    se eligió en QC). 3° El sugerido para ese video (``sugerir_tema``: molde, error, paso a paso).
    Sin guion (vista previa, subtitular un video externo): el ``tema:`` de marca.yaml.
    """
    if manual and str(manual).strip():
        return str(manual).strip()
    if guion is None:
        return (marca.tema or TEMA_POR_DEFECTO).strip()
    return estilo_del_guion(guion, marca).clave


_ID_VALIDO = re.compile(r"[A-Za-z0-9_-]{1,80}")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FuenteRol(_Base):
    familia: str = "Montserrat"
    # "conservar" = cada texto usa su propio grosor (como el estilo original); o NORMAL, BOLD, HEAVY…
    grosor: str = "conservar"
    mayusculas: bool = False
    escala: float = Field(default=1.0, ge=0.5, le=2.0)

    @field_validator("familia")
    @classmethod
    def _familia(cls, v: str) -> str:
        if not existe(v):
            from .tipografia import FAMILIAS

            raise ValueError(f"no tengo la letra «{v}»; opciones: {', '.join(FAMILIAS)}")
        return v


class Tipografia(_Base):
    titulos: FuenteRol = FuenteRol()
    texto: FuenteRol = FuenteRol()


class ColoresTema(_Base):
    fondo: str = "#0B1220"
    panel: str = "#121B2F"
    borde: str = "#24324F"
    titulos: str = "#F8FAFC"
    texto: str = "#F8FAFC"
    formulas: str = "#F8FAFC"
    tenue: str = "#94A3B8"
    acento: str = "#FFC72C"
    exito: str = "#22C55E"
    cuadricula: str = "#38BDF8"
    error: str = "#EF4444"  # la ✗ y la nota del paso "error típico"

    _hex = field_validator("*")(classmethod(lambda cls, v: _validar_hex(v)))


class Nota(_Base):
    """Estilo de la nota pequeña sobre cada fórmula ("Despejamos t")."""

    rol: Literal["texto", "titulos"] = "texto"
    escala: float = Field(default=1.0, ge=0.5, le=2.5)
    color: Literal["materia", "titulos", "acento"] = "materia"


class Fondo(_Base):
    tipo: Literal["cuadricula", "imagen", "color", "degradado"] = "cuadricula"
    imagen: str = "difuminado"  # incluida (assets/fondos/) o propia (mis_ajustes/fondos/)
    degradado: list[str] = ["#1E3A8A", "#0B1220"]

    _hex = field_validator("degradado")(classmethod(lambda cls, v: [_validar_hex(c) for c in v]))


class Hoja(_Base):
    """La hoja cuadriculada del marco "hoja" (textos vacíos = no se muestran)."""

    encabezado: str = "HOJA DE DESARROLLO"
    etiqueta: str = "Notas"
    fecha: str = "Fecha:"
    color: str = "#FFFFFF"
    lineas: str = "#D4D4D4"
    cuadricula: bool = True

    _hex = field_validator("color", "lineas")(classmethod(lambda cls, v: _validar_hex(v)))


class Animacion(_Base):
    # "plumon": los títulos y notas se escriben trazo a trazo, como con un plumón
    titulos: Literal["aparecer", "plumon"] = "aparecer"


class Gramatica(_Base):
    """La gramática visual estilo XCris; apagada por defecto para no tocar los temas de hoy."""

    tabs: bool = False
    panel: bool = False
    mapa_color: bool = False
    micro: bool = False
    paleta_pasos: list[str] = Field(default_factory=list)

    _hex = field_validator("paleta_pasos")(classmethod(lambda cls, v: [_validar_hex(c) for c in v]))

    def paleta(self, colores: ColoresTema) -> list[str]:
        return self.paleta_pasos or colores_distintos(
            [colores.acento, colores.cuadricula, colores.exito, colores.error, colores.tenue], colores.panel
        )


# Los acentos sobrios de la familia Consola: de acá salen los colores que faltan cuando el tema repite
# uno (en Reto el acento ES el verde del éxito; en Error, el rojo del error).
ACENTOS_DE_RESPALDO = ("#6FA8DC", "#D4B26A", "#7DB894", "#A399C9", "#D27A72", "#7FC4C0", "#C99A6B")
DISTANCIA_MINIMA = 45  # en RGB: menos que esto, dos porciones de una torta se leen como una sola


def _rgb_de(color: str) -> tuple[int, int, int]:
    h = color.lstrip("#")[:6]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _distancia(a: str, b: str) -> float:
    return sum((x - y) ** 2 for x, y in zip(_rgb_de(a), _rgb_de(b), strict=True)) ** 0.5


def colores_distintos(colores: list[str], papel: str | None = None, cuantos: int | None = None) -> list[str]:
    """Los colores en el mismo orden, sin los que se confunden con uno anterior (ni con el papel).

    Si quedan menos de ``cuantos`` (por defecto, los que llegaron), se completan con los acentos de
    la familia que sí se distinguen. Sirve a la torta, las barras y el mapa de colores de los pasos.
    """
    cuantos = cuantos or len(colores)
    salida: list[str] = []
    for color in [*colores, *ACENTOS_DE_RESPALDO]:
        try:
            lejos_del_papel = papel is None or _distancia(color, papel) >= DISTANCIA_MINIMA
            lejos = all(_distancia(color, otro) >= DISTANCIA_MINIMA for otro in salida)
        except (ValueError, IndexError):
            continue  # un color con nombre (no hex) no se puede comparar: se salta
        if lejos and lejos_del_papel:
            salida.append(color)
        if len(salida) >= cuantos:
            break
    return salida or list(colores)


class Layout(_Base):
    """Diagramación vertical del cuadro.

    Los ``y_...`` vacíos (``None``) son las zonas del marco (pizarra u hoja), que es lo que usa hoy
    cada tema: así un YAML que no menciona ``layout`` se ve exactamente igual que antes.
    """

    y_cabecera: float | None = None  # la línea de la marca y la materia
    y_zona_enunciado: float | None = None  # techo de la zona de trabajo (donde arranca el enunciado)
    y_zona_pasos: float | None = None  # piso de la zona de trabajo (donde se detiene la pila de pasos)
    banda_subtitulo: float = 0.28  # el tramo de abajo que se lleva el subtítulo quemado
    banda_panel: float = Field(default=0.0, ge=0.0, le=2.0)  # alto del panel persistente de la gramática
    aire_dibujo: float = 0.28  # el respiro entre el techo del dibujo y la línea más baja de los pasos


class Tema(_Base):
    nombre: str
    descripcion: str = ""
    marco: Literal["pizarra", "hoja"] = "pizarra"
    # Compatibilidad: colores, materias y subtítulos salen de marca.yaml (estilo original)
    usar_marca: bool = False
    colores: ColoresTema = ColoresTema()
    materias: ColoresMateria = ColoresMateria()
    tipografia: Tipografia = Tipografia()
    nota: Nota = Nota()
    formulas_negrita: bool = True
    fondo: Fondo = Fondo()
    hoja: Hoja = Hoja()
    subtitulos: EstiloSubtitulos = EstiloSubtitulos()
    animacion: Animacion = Animacion()
    layout: Layout = Layout()
    emojis: bool = True
    # El halo de los trazos brillantes que pone postproduccion.py al armar el video final
    resplandor: bool = False
    gramatica: Gramatica = Gramatica()
    # El rótulo del rincón superior derecho («DATO», «MITO»…): dice qué tipo de video es desde el
    # primer segundo. Vacío = el nombre de la materia, como siempre. Solo en el marco «pizarra».
    rotulo: str = Field(default="", max_length=14)


def temas_usuario_dir() -> Path:
    return raiz_proyecto() / "mis_ajustes" / "temas"


def fondos_usuario_dir() -> Path:
    return raiz_proyecto() / "mis_ajustes" / "fondos"


def id_tema(nombre: str) -> str:
    """Nombre de archivo a partir de un nombre visible: "Mi Tema 2" → "mi_tema_2"."""
    from .guion import sin_tildes

    return re.sub(r"[^a-z0-9]+", "_", sin_tildes(nombre.lower())).strip("_") or "tema"


def _rutas(identificador: str) -> list[Path]:
    if not _ID_VALIDO.fullmatch(identificador):  # nunca una ruta como «../otra_carpeta»
        return []
    return [
        temas_usuario_dir() / f"{identificador}.yaml",
        TEMAS_DIR / f"{identificador}.yaml",
        ARCHIVO_DIR / f"{identificador}.yaml",  # retirado: no se ofrece, pero lo viejo sigue funcionando
    ]


def existe_tema(identificador: str) -> bool:
    return any(ruta.exists() for ruta in _rutas(identificador.strip()))


def listar_temas() -> list[tuple[str, Tema, bool]]:
    """(id, tema, es_propio) de todos los temas válidos; primero los incluidos."""
    vistos: dict[str, tuple[str, Tema, bool]] = {}
    for carpeta, propio in ((TEMAS_DIR, False), (temas_usuario_dir(), True)):
        if not carpeta.exists():
            continue
        # La familia en su orden (paso a paso, error, mito, dato, reto); lo demás, alfabético.
        orden = {clave: i for i, clave in enumerate(FAMILIA)}
        for ruta in sorted(carpeta.glob("*.yaml"), key=lambda r: (orden.get(r.stem, len(orden)), r.stem)):
            try:
                vistos[ruta.stem] = (ruta.stem, _leer(ruta), propio)
            except ErrorMotor:
                continue  # un tema propio dañado no debe impedir listar los demás
    return list(vistos.values())


def _leer(ruta: Path) -> Tema:
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        return Tema.model_validate(datos)
    except (yaml.YAMLError, ValidationError) as e:
        if isinstance(e, ValidationError):
            detalle = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
        else:
            detalle = str(e)
        raise ErrorMotor(f"El tema {ruta.name} tiene un error: {detalle}") from e


def _con_marca(tema: Tema, marca: Marca) -> Tema:
    c: Colores = marca.colores
    colores = ColoresTema(
        fondo=c.fondo, panel=c.panel, borde=c.borde, titulos=c.texto, texto=c.texto, formulas=c.texto,
        tenue=c.tenue, acento=c.acento, exito=c.exito, cuadricula=c.cuadricula,
    )  # fmt: skip
    return tema.model_copy(
        update={"colores": colores, "materias": marca.materias, "subtitulos": marca.subtitulos}
    )


def cargar_tema(identificador: str | None, marca: Marca) -> Tema:
    identificador = (identificador or marca.tema or TEMA_POR_DEFECTO).strip()
    for ruta in _rutas(identificador):
        if ruta.exists():
            tema = _leer(ruta)
            return _con_marca(tema, marca) if tema.usar_marca else tema
    opciones = ", ".join(t for t, _, _ in listar_temas())
    raise ErrorMotor(f"No existe el tema «{identificador}».", ayuda=f"Temas disponibles: {opciones}")


def guardar_tema(identificador: str, tema: Tema) -> Path:
    destino = temas_usuario_dir() / f"{id_tema(identificador)}.yaml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    datos = tema.model_dump(mode="json")
    destino.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return destino


def ruta_fondo(nombre: str) -> Path:
    for candidato in (fondos_usuario_dir() / f"{nombre}.png", FONDOS_DIR / f"{nombre}.png", Path(nombre)):
        if candidato.exists():
            return candidato
    raise ErrorMotor(
        f"No encuentro la imagen de fondo «{nombre}».", ayuda="Elige otro fondo en el panel (Estilos)."
    )
