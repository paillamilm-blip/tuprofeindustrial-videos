"""Temas visuales: todo lo que define cómo se ve un video (marco, colores, letras, fondo, subtítulos).

- Los temas incluidos están en ``plantillas/temas/``: ``hoja_de_desarrollo`` (por defecto) y
  ``pizarra_nocturna`` (el estilo original del motor).
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
FONDOS_DIR = PAQUETE / "assets" / "fondos"
TEMA_POR_DEFECTO = "hoja_de_desarrollo"

# ------------------------------------------------------------------------------------------
# El estilo sugerido: el ÚNICO lugar del motor que decide cómo se ve un video que nadie eligió.
# Lo usan el render, la vista previa, el QC y la tarjeta «Así está armado». Solo estilos que ya
# existen en plantillas/temas/ (una prueba lo exige): estas tablas eligen, no crean nada.
# ------------------------------------------------------------------------------------------

# 3° La materia: la identidad de cada asignatura.
TEMA_POR_CATEGORIA: dict[str, str] = {
    "matematicas": "pizarra_nocturna",
    "fisica": "neon_cian",
    "ingenieria": "plano_noche",
}
NOMBRE_CATEGORIA = {"matematicas": "Matemáticas", "fisica": "Física", "ingenieria": "Ingeniería"}

# 1° El molde: la forma del video manda sobre la materia (un reto se ve como reto en cualquier ramo).
# «Nadie te enseñó esto» no está: es el dato sorpresa de cualquier ramo y debe lucir su materia.
TEMA_POR_MOLDE: dict[str, str] = {
    "reto": "neon_reja",
    "mito_realidad": "vineta_cine",
    "tres_errores": "rotulador",
    "pov": "kraft_tiza",
}
MOTIVO_POR_MOLDE = {
    "reto": "Un reto pide neón: se lee como desafío.",
    "mito_realidad": "El contraste mito/realidad funciona en cine.",
    "tres_errores": "Tres errores seguidos se siguen mejor en papel.",
    "pov": "Un POV se siente en cuaderno, no en pantalla.",
}

# 2° Lo que se dibuja: cuando el dibujo pide su propio papel.
DIBUJOS_INDUSTRIALES = frozenset(
    {
        "tolva_3d",
        "tuberia_3d",
        "eje_3d",
        "engranaje",
        "mohr",
        "viga",
        "cercha",
        "gradiente_termico",
        "perfil_flujo",
    }
)
TEMA_POR_DIBUJO: tuple[tuple[frozenset[str], str, str], ...] = (
    (frozenset({"circuito"}), "plano_azul", "Tiene un circuito: se lee mejor en lámina de ingeniería."),
    (DIBUJOS_INDUSTRIALES, "plano_noche", "Tiene piezas industriales: lucen en el plano nocturno."),
)
TEMA_DE_ERROR = "cuaderno_con_sello"
MOTIVO_DE_ERROR = "Corrige un error típico: el rojo de profe del cuaderno lo marca."


class EstiloSugerido(BaseModel):
    """Qué estilo lleva un video y por qué, en una frase que se le puede mostrar a una persona."""

    model_config = ConfigDict(frozen=True)

    clave: str
    razon: str
    origen: Literal["guion", "molde", "dibujo", "error", "materia", "marca"]


def sugerir_tema(
    *,
    molde: str | None = None,
    categoria: str | None = None,
    dibujos: set[str] | frozenset[str] = frozenset(),
    con_error: bool = False,
    de_siempre: str | None = None,
) -> EstiloSugerido:
    """El estilo que mejor le queda a un video, según lo que se sabe de él (sin mirar el ``tema:``).

    1° su molde · 2° sus dibujos · 3° si corrige un error · 4° su materia · 5° ``de_siempre``
    (el ``tema`` de marca.yaml).
    """
    if molde in TEMA_POR_MOLDE:
        return EstiloSugerido(clave=TEMA_POR_MOLDE[molde], razon=MOTIVO_POR_MOLDE[molde], origen="molde")
    for tipos, clave, razon in TEMA_POR_DIBUJO:
        if tipos & set(dibujos):
            return EstiloSugerido(clave=clave, razon=razon, origen="dibujo")
    if con_error:
        return EstiloSugerido(clave=TEMA_DE_ERROR, razon=MOTIVO_DE_ERROR, origen="error")
    if categoria in TEMA_POR_CATEGORIA:
        clave = TEMA_POR_CATEGORIA[categoria]
        return EstiloSugerido(
            clave=clave, razon=f"Es de {NOMBRE_CATEGORIA[categoria]}: su estilo de materia.", origen="materia"
        )
    clave = (de_siempre or TEMA_POR_DEFECTO).strip()
    return EstiloSugerido(clave=clave, razon="Tu estilo de siempre (marca.yaml).", origen="marca")


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
    casos += [
        "circuitos" if "circuito" in tipos else "piezas industriales"
        for tipos, t, _razon in TEMA_POR_DIBUJO
        if t == clave
    ]
    if clave == TEMA_DE_ERROR:
        casos.append("videos que corrigen un error")
    casos += [NOMBRE_CATEGORIA[c] for c, t in TEMA_POR_CATEGORIA.items() if t == clave]
    return casos


def resolver_tema(manual: str | None, guion: Any | None, marca: Marca) -> str:
    """Qué estilo lleva un video, en cascada.

    1° Lo que se pidió en la llamada (``--tema`` en la Terminal). 2° El ``tema:`` del guion (lo que
    se eligió en QC). 3° El sugerido para ese video (``sugerir_tema``: molde, dibujos, error, materia).
    4° El ``tema:`` de marca.yaml.
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


class Layout(_Base):
    """Diagramación vertical del cuadro.

    Los ``y_...`` vacíos (``None``) son las zonas del marco (pizarra u hoja), que es lo que usa hoy
    cada tema: así un YAML que no menciona ``layout`` se ve exactamente igual que antes.
    """

    y_cabecera: float | None = None  # la línea de la marca y la materia
    y_zona_enunciado: float | None = None  # techo de la zona de trabajo (donde arranca el enunciado)
    y_zona_pasos: float | None = None  # piso de la zona de trabajo (donde se detiene la pila de pasos)
    banda_subtitulo: float = 0.28  # el tramo de abajo que se lleva el subtítulo quemado
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
    return [temas_usuario_dir() / f"{identificador}.yaml", TEMAS_DIR / f"{identificador}.yaml"]


def existe_tema(identificador: str) -> bool:
    return any(ruta.exists() for ruta in _rutas(identificador.strip()))


def listar_temas() -> list[tuple[str, Tema, bool]]:
    """(id, tema, es_propio) de todos los temas válidos; primero los incluidos."""
    vistos: dict[str, tuple[str, Tema, bool]] = {}
    for carpeta, propio in ((TEMAS_DIR, False), (temas_usuario_dir(), True)):
        if not carpeta.exists():
            continue
        for ruta in sorted(carpeta.glob("*.yaml")):
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
