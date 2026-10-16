"""Formato del guion (YAML) y su lectura con mensajes de error en español claro.

Cada bloque separa lo que se VE (``texto`` o ``tex`` en LaTeX) de lo que se ESCUCHA (``voz``),
porque la voz sintética no sabe leer LaTeX.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .errores import ErrorMotor
from .tex import llaves_balanceadas

MATERIAS: dict[str, str] = {"matematica": "MATEMÁTICA", "fisica": "FÍSICA", "ingenieria": "INGENIERÍA"}

# Caracteres que aparecen cuando una fórmula se escribe entre comillas DOBLES en YAML:
# "\frac" → salto de página + "rac", "\times" → tabulación + "imes", "\vec" → tab vertical…
_CONTROL_YAML = {"\x07", "\x08", "\t", "\n", "\x0b", "\x0c", "\r", "\x1b", "\x00"}
_AYUDA_COMILLAS = (
    "parece que la fórmula está entre comillas dobles y YAML se 'comió' las barras invertidas. "
    "Escríbela entre comillas simples, por ejemplo: tex: 'h = \\frac{1}{2} g t^2'"
)


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _validar_tex(valor: str | None) -> str | None:
    if valor is None:
        return None
    if any(c in valor for c in _CONTROL_YAML):
        raise ValueError(_AYUDA_COMILLAS)
    if not llaves_balanceadas(valor):
        raise ValueError("las llaves { } de la fórmula no están balanceadas")
    return valor


def _como_lista(valor: Any) -> Any:
    if valor is None:
        return []
    if isinstance(valor, str):
        return [valor]
    return valor


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def _quitar_comillas_curvas(cls, valor: Any) -> Any:
        """TextEdit (Mac) cambia ' y " por comillas curvas; si envuelven el valor, se quitan."""
        if isinstance(valor, str):
            limpio = valor.strip()
            if len(limpio) >= 2 and limpio[0] in "“‘«" and limpio[-1] in "”’»":
                return limpio[1:-1]
        return valor


class _ConTexto(_Base):
    """Bloque que acepta la forma corta ``clave: "texto"`` o la larga con ``texto`` y ``voz``."""

    texto: str = Field(min_length=1)
    voz: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _forma_corta(cls, valor: Any) -> Any:
        return {"texto": valor} if isinstance(valor, str) else valor

    @property
    def voz_final(self) -> str:
        return self.voz or self.texto


class Gancho(_ConTexto):
    destacar: list[str] = []
    tex: str | None = None  # fórmula bajo la pregunta, ej. '(x+5)^2 = x^2 + 25'
    emoji: str | None = None  # ej. "🤯", "alerta" o un sticker propio

    _lista = field_validator("destacar", mode="before")(classmethod(lambda cls, v: _como_lista(v)))
    _tex = field_validator("tex")(classmethod(lambda cls, v: _validar_tex(v)))


class Enunciado(_ConTexto):
    destacar: list[str] = []

    _lista = field_validator("destacar", mode="before")(classmethod(lambda cls, v: _como_lista(v)))


class Bloque(_ConTexto):
    emoji: str | None = None


class Dato(_Base):
    tex: str = Field(min_length=1)
    voz: str = Field(min_length=1)

    _tex = field_validator("tex")(classmethod(lambda cls, v: _validar_tex(v)))


class Paso(_Base):
    voz: str = Field(min_length=1)
    tex: str | None = None
    nota: str | None = None
    destacar: list[str] = []
    transformar: bool = True
    emoji: str | None = None
    # Error típico: la fórmula (equivocada) se tacha con una ✗ roja; no cuenta como paso correcto
    error: bool = False

    _tex = field_validator("tex")(classmethod(lambda cls, v: _validar_tex(v)))
    _lista = field_validator("destacar", mode="before")(classmethod(lambda cls, v: _como_lista(v)))

    @model_validator(mode="after")
    def _error_con_formula(self) -> Paso:
        if self.error and not self.tex:
            raise ValueError("un paso con «error: true» necesita la fórmula equivocada en «tex»")
        return self


class Resultado(_Base):
    tex: str = Field(min_length=1)
    voz: str = Field(min_length=1)
    emoji: str | None = None

    _tex = field_validator("tex")(classmethod(lambda cls, v: _validar_tex(v)))


class Guion(_Base):
    titulo: str = Field(min_length=1)
    materia: Literal["matematica", "fisica", "ingenieria"]
    nivel: str | None = None
    tema: str | None = None  # estilo visual de este video (ver ./tpi temas)
    voz: str | None = None
    velocidad: str | None = None
    gancho: Gancho
    enunciado: Enunciado
    datos: list[Dato] = []
    pasos: list[Paso] = Field(min_length=1)
    resultado: Resultado
    verificacion: Bloque | None = None
    reto: Bloque | None = None
    cierre: Bloque | None = None

    @field_validator("materia", mode="before")
    @classmethod
    def _normalizar_materia(cls, valor: Any) -> Any:
        if not isinstance(valor, str):
            return valor
        limpio = sin_tildes(valor).strip().lower()
        return limpio[:-1] if limpio.endswith("s") else limpio  # "matemáticas" → "matematica"

    @field_validator("velocidad")
    @classmethod
    def _validar_velocidad(cls, valor: str | None) -> str | None:
        if valor is not None and not re.fullmatch(r"[+-]\d{1,3}%", valor):
            raise ValueError("usa un porcentaje con signo, por ejemplo '+5%' o '-10%'")
        return valor

    @property
    def etiqueta_materia(self) -> str:
        return MATERIAS[self.materia]

    def textos_de_voz(self, cierre_por_defecto: str) -> list[tuple[str, str]]:
        """Todos los textos que se dirán, en orden, con el nombre de su sección."""
        voces = [("gancho", self.gancho.voz_final), ("enunciado", self.enunciado.voz_final)]
        voces += [(f"dato {i}", d.voz) for i, d in enumerate(self.datos, 1)]
        voces += [(f"paso {i}", p.voz) for i, p in enumerate(self.pasos, 1)]
        voces.append(("resultado", self.resultado.voz))
        if self.verificacion:
            voces.append(("verificación", self.verificacion.voz_final))
        if self.reto:
            voces.append(("reto", self.reto.voz_final))
        voces.append(("cierre", self.cierre.voz_final if self.cierre else cierre_por_defecto))
        return voces


# ---------------------------------------------------------------------------------------------
# Lectura con errores amigables
# ---------------------------------------------------------------------------------------------

_MENSAJES = {
    "missing": "falta este campo (es obligatorio)",
    "extra_forbidden": "este campo no existe: ¿quizás un error de tipeo?",
    "string_type": "debe ser un texto",
    "list_type": "debe ser una lista (cada elemento empieza con '- ')",
    "bool_type": "debe ser true o false",
    "bool_parsing": "debe ser true o false",
    "too_short": "no puede quedar vacío",
    "string_too_short": "no puede quedar vacío",
    "literal_error": "valor no válido; las opciones son: matematica, fisica, ingenieria",
    "model_type": "debe tener sub-campos (por ejemplo texto: y voz:)",
    "model_attributes_type": "debe tener sub-campos (por ejemplo texto: y voz:)",
}


def emojis_del_guion(guion: Guion) -> list[tuple[str, str]]:
    """(sección, valor) de cada emoji usado en el guion."""
    usados = [("gancho", guion.gancho.emoji)]
    usados += [(f"paso {i}", p.emoji) for i, p in enumerate(guion.pasos, 1)]
    usados.append(("resultado", guion.resultado.emoji))
    for nombre in ("verificacion", "reto", "cierre"):
        bloque = getattr(guion, nombre)
        if bloque is not None:
            usados.append((nombre, bloque.emoji))
    return [(donde, valor) for donde, valor in usados if valor]


def _ubicacion(loc: tuple[Any, ...]) -> str:
    partes: list[str] = []
    for item in loc:
        if isinstance(item, int):
            partes.append(f"#{item + 1}")
        elif not str(item).startswith("function-"):  # nombres internos de validadores
            partes.append(str(item))
    return " → ".join(partes) or "(raíz)"


def explicar_errores(error: ValidationError) -> list[str]:
    lineas = []
    for err in error.errors():
        tipo = err.get("type", "")
        if tipo == "value_error":
            mensaje = str(err.get("msg", "")).removeprefix("Value error, ")
        else:
            mensaje = _MENSAJES.get(tipo, err.get("msg", "valor no válido"))
        lineas.append(f"{_ubicacion(err.get('loc', ()))}: {mensaje}")
    return lineas


def cargar_guion(ruta: str | Path) -> Guion:
    ruta = Path(ruta)
    if not ruta.exists():
        raise ErrorMotor(
            f"No encuentro el guion «{ruta}».",
            ayuda="Revisa la ruta. Ejemplo: ./tpi crear guiones/ejemplos/fisica_caida_libre.yaml",
        )
    crudo = ruta.read_text(encoding="utf-8")
    try:
        datos = yaml.safe_load(crudo)
    except yaml.YAMLError as e:
        ayuda = "Revisa la sangría (2 espacios, sin tabulaciones) y pon entre comillas los textos con ':'."
        if "escape" in str(e):
            ayuda = "Escribe las fórmulas LaTeX entre comillas simples: tex: '\\frac{1}{2}'"
        if any(q in crudo for q in "“”‘’"):
            ayuda += (
                " Además, el archivo tiene comillas curvas (“ ”): si usas TextEdit, desactiva "
                "Edición → Sustituciones → Comillas inteligentes."
            )
        marca = getattr(e, "problem_mark", None)
        donde = f" (línea {marca.line + 1})" if marca else ""
        raise ErrorMotor(f"El archivo {ruta.name} tiene un error de formato YAML{donde}.", ayuda=ayuda) from e
    if not isinstance(datos, dict):
        raise ErrorMotor(f"{ruta.name} no parece un guion: debería empezar con 'titulo:'.")
    try:
        return Guion.model_validate(datos)
    except ValidationError as e:
        detalle = "\n".join(f"  • {linea}" for linea in explicar_errores(e))
        raise ErrorMotor(
            f"El guion {ruta.name} tiene problemas:\n{detalle}",
            ayuda="Compara con guiones/ejemplos/ o con docs/GUIA_GUIONES.md",
        ) from e
