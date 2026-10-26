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
from .moldes import MOLDES, normalizar_molde, opciones_de_moldes
from .tex import llaves_balanceadas
from .visuales import (
    MARCAS_CIRCULO,
    MARCAS_POLIGONO,
    MARCAS_PROYECTIL,
    SEGUNDOS_VISUAL,
    analizar_angulo,
    analizar_funcion,
    analizar_poligono,
    analizar_proyectil,
    normalizar_vectores,
)

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


class Visual(_Base):
    """El dibujo de un paso: un gráfico de función, un diagrama de fuerzas, un circuito o un polígono.

    Sólo se usan los campos del ``tipo`` elegido; los demás quedan vacíos a propósito.
    """

    tipo: Literal[
        "grafico_funcion", "diagrama_fuerzas", "circuito", "poligono_regular", "proyectil", "circulo_trig"
    ]

    # grafico_funcion
    funcion: str | None = None
    variable: str | None = None
    rango: list[float] | None = None
    marcar: list[float] = []
    eje_x: str | None = None  # ej. "tiempo (s)"
    eje_y: str | None = None  # ej. "altura (m)"

    # diagrama_fuerzas
    cuerpo: Literal["bloque", "bola"] = "bloque"
    vectores: list[str] = []
    angulo: float | None = None  # plano inclinado, en grados
    descomponer: bool = False  # parte el peso en P sen θ y P cos θ sobre el plano

    # circuito
    arreglo: Literal["serie", "paralelo"] = "serie"
    fuente: str | None = None  # ej. '12 V'
    resistencias: list[str] = []  # ej. ['4 Ω', '6 Ω']

    # proyectil
    velocidad: str | None = None  # la del lanzamiento, con su unidad: '20 m/s'

    # poligono_regular
    lados: int | None = None  # de 3 a 8
    lado: str | None = None  # la medida de un lado, con su unidad: '12 cm'
    anotar: list[str] = []  # ej. ['apotema', 'angulo_interior']

    _listas = field_validator("rango", "marcar", "vectores", "resistencias", "anotar", mode="before")(
        classmethod(lambda cls, v: None if v is None else _como_lista(v))
    )

    @model_validator(mode="after")
    def _campos_del_tipo(self) -> Visual:
        if self.tipo == "grafico_funcion":
            if not (self.funcion or "").strip():
                raise ValueError("un gráfico de función necesita la fórmula, ej. funcion: '-x^2 + 4x'")
            if self.rango is not None and len(self.rango) != 2:
                raise ValueError("el rango son dos números, ej. rango: [0, 5]")
        elif self.tipo == "diagrama_fuerzas":
            self.vectores = normalizar_vectores(self.vectores)
            if self.angulo is not None:
                if not 0 < self.angulo < 90:
                    raise ValueError(f"el ángulo del plano va entre 0 y 90 grados, y dice {self.angulo}")
                if self.cuerpo != "bloque":
                    raise ValueError("el ángulo (plano inclinado) solo va con cuerpo: bloque")
            if self.descomponer:
                if self.angulo is None:
                    raise ValueError("descomponer el peso sólo tiene sentido sobre la rampa: ponle angulo:")
                if "P" not in self.vectores:
                    raise ValueError("para descomponer el peso el diagrama necesita la flecha «P»")
        elif self.tipo == "proyectil":
            if not (self.velocidad or "").strip():
                raise ValueError("un proyectil necesita la velocidad de lanzamiento, ej. velocidad: '20 m/s'")
            if self.angulo is None:
                raise ValueError("un proyectil necesita el ángulo de lanzamiento, ej. angulo: 30")
            analizar_proyectil(self.velocidad, self.angulo)
            desconocidas = [m for m in self.anotar if m not in MARCAS_PROYECTIL]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de un proyectil; "
                    f"el motor sabe anotar {', '.join(MARCAS_PROYECTIL)}"
                )
        elif self.tipo == "circulo_trig":
            if self.angulo is None:
                raise ValueError("un círculo trigonométrico necesita su ángulo en grados, ej. angulo: 30")
            if not 0 <= self.angulo < 360:
                raise ValueError(
                    f"el ángulo del círculo va de 0 a 360 grados (una vuelta), y dice {self.angulo}"
                )
            figura = analizar_angulo(self.angulo)
            desconocidas = [m for m in self.anotar if m not in MARCAS_CIRCULO]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca del círculo trigonométrico; "
                    f"el motor sabe anotar {', '.join(MARCAS_CIRCULO)}"
                )
            if "tangente" in self.anotar and figura.tangente is None:
                raise ValueError(
                    f"a {figura.grados:g}° la tangente no existe (el radio queda paralelo a ella): "
                    "anota seno o coseno"
                )
        elif self.tipo == "poligono_regular":
            if not (self.lado or "").strip():
                raise ValueError("un polígono necesita la medida del lado, ej. lado: '12 cm'")
            if self.lados is None:
                raise ValueError("un polígono necesita cuántos lados tiene, ej. lados: 5")
            analizar_poligono(self.lados, self.lado)  # rechaza lados < 3 o una medida sin número
            desconocidas = [m for m in self.anotar if m not in MARCAS_POLIGONO]
            if desconocidas:
                raise ValueError(
                    f"«{desconocidas[0]}» no es una marca de un polígono; "
                    f"el motor sabe anotar {', '.join(MARCAS_POLIGONO)}"
                )
        elif not (self.fuente or "").strip():
            raise ValueError("un circuito necesita la fuente, ej. fuente: '12 V'")
        elif not 2 <= len(self.resistencias) <= 4:
            raise ValueError(
                f"un circuito va entre 2 y 4 resistencias para que se entienda en el celular, y dice {len(self.resistencias)}"
            )
        return self

    @property
    def segundos(self) -> float:
        """Lo que el dibujo suma a la duración estimada: la curva se mira un rato más."""
        return SEGUNDOS_VISUAL[self.tipo]

    def funcion_analizada(self):
        """La función lista para trazar (raíces, vértice y rango). Sólo en los gráficos."""
        if self.tipo != "grafico_funcion":
            raise ValueError(f"«{self.tipo}» no tiene una función que analizar")
        return analizar_funcion(self.funcion or "", self.variable, self.rango, self.marcar)

    def proyectil(self):
        """El vuelo ya resuelto (tiempo, alcance y altura). Sólo en los proyectiles."""
        if self.tipo != "proyectil":
            raise ValueError(f"«{self.tipo}» no es un proyectil")
        return analizar_proyectil(self.velocidad or "", self.angulo or 0)

    def angulo_trig(self):
        """El ángulo resuelto en el círculo (seno, coseno, tangente y cuadrante)."""
        if self.tipo != "circulo_trig":
            raise ValueError(f"«{self.tipo}» no es un círculo trigonométrico")
        return analizar_angulo(self.angulo or 0)

    def poligono(self):
        """El polígono regular ya resuelto (apotema, radio y ángulos). Sólo en los polígonos."""
        if self.tipo != "poligono_regular":
            raise ValueError(f"«{self.tipo}» no es un polígono")
        return analizar_poligono(self.lados or 0, self.lado)


class Paso(_Base):
    voz: str = Field(min_length=1)
    tex: str | None = None
    nota: str | None = None
    destacar: list[str] = []
    transformar: bool = True
    emoji: str | None = None
    visual: Visual | None = None
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
    molde: str | None = None  # estructura narrativa (ver moldes.py); opcional
    tema: str | None = None  # estilo visual de este video (ver ./tpi temas)
    voz: str | None = None
    velocidad: str | None = None
    gancho: Gancho
    gancho_variantes: list[Gancho] = []  # alternativas al gancho elegido; no lo repiten
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

    @field_validator("molde", mode="before")
    @classmethod
    def _normalizar_molde(cls, valor: Any) -> Any:
        if valor in (None, ""):
            return None
        clave = normalizar_molde(str(valor))
        if not clave:
            raise ValueError(
                f"«{valor}» no es un molde conocido; usa {opciones_de_moldes()} o quita el campo"
            )
        return clave

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
    "float_parsing": "debe ser un número (los decimales llevan punto: 4.9)",
    "float_type": "debe ser un número (los decimales llevan punto: 4.9)",
    "too_short": "no puede quedar vacío",
    "string_too_short": "no puede quedar vacío",
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


def _hay_correcto_despues(pasos: list[Paso], desde: int) -> bool:
    return any(not p.error for p in pasos[desde + 1 :])


def problemas_de_molde(guion: Guion) -> list[str]:
    """Las reglas objetivas del molde: avisos corregibles, nunca un bloqueo del render."""
    if not guion.molde:
        return []
    molde = MOLDES.get(guion.molde)
    if molde is None:
        return [f"«{guion.molde}» no es un molde conocido; usa {opciones_de_moldes()}."]
    errores = [i for i, p in enumerate(guion.pasos) if p.error]
    if molde.regla == "un_error":
        if not errores:
            return [f"«{molde.nombre}» necesita al menos un paso con «error: true»."]
        if not _hay_correcto_despues(guion.pasos, errores[0]):
            return [f"«{molde.nombre}» necesita un paso correcto después del error."]
    elif molde.regla == "tres_errores":
        if len(errores) != 3:
            return [
                f"«{molde.nombre}» necesita exactamente 3 pasos con «error: true» y este guion tiene "
                f"{len(errores)}."
            ]
        if not _hay_correcto_despues(guion.pasos, errores[-1]):
            return [f"«{molde.nombre}» necesita un paso correcto después de los 3 errores."]
    elif molde.regla == "reto" and guion.reto is None:
        return [f"«{molde.nombre}» necesita el bloque «reto:» al final."]
    elif molde.regla == "verificacion" and guion.verificacion is None:
        return [f"«{molde.nombre}» necesita el bloque «verificacion:»."]
    return []


def _ubicacion(loc: tuple[Any, ...]) -> str:
    partes: list[str] = []
    for item in loc:
        if isinstance(item, int):
            partes.append(f"#{item + 1}")
        elif not str(item).startswith("function-"):  # nombres internos de validadores
            partes.append(str(item))
    return " → ".join(partes) or "(raíz)"


def _opciones_es(opciones: list[str]) -> str:
    """['a', 'b'] → «a o b» (en español la lista se cierra con «o», no con «or»)."""
    if len(opciones) <= 1:
        return opciones[0] if opciones else "revisa los ejemplos de guiones/"
    return ", ".join(opciones[:-1]) + " o " + opciones[-1]


def explicar_errores(error: ValidationError) -> list[str]:
    lineas = []
    for err in error.errors():
        tipo = err.get("type", "")
        if tipo == "value_error":
            mensaje = str(err.get("msg", "")).removeprefix("Value error, ")
        elif tipo == "literal_error":
            # pydantic entrega las opciones en inglés: "'a', 'b' or 'c'"
            opciones = re.findall(r"'([^']*)'", str(err.get("ctx", {}).get("expected", "")))
            mensaje = f"valor no válido; las opciones son: {_opciones_es(opciones)}"
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


# ---------------------------------------------------------------------------------------------
# Escritura (el inverso de cargar_guion): textos con "…", fórmulas con '…', como en los ejemplos
# ---------------------------------------------------------------------------------------------


def _dobles(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _simples(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _numero(valor: Any) -> str:
    """30.0 → «30», 2.5 → «2.5»: como se escribe un número en un guion a mano."""
    n = round(float(valor), 4)
    return str(n).removesuffix(".0")


def _numeros(vals: list[Any]) -> str:
    """[0, 5] con la coma como separador YAML y punto decimal (el que lee el motor)."""
    return "[" + ", ".join(_numero(v) for v in vals) + "]"


def _visual_yaml(v: dict[str, Any]) -> list[str]:
    """Los campos del visual que corresponden a su tipo, con la sangría de un paso."""
    tipo = v["tipo"]
    campos: list[tuple[str, str]] = [("tipo", tipo)]
    if tipo == "grafico_funcion":
        campos.append(("funcion", _simples(v.get("funcion") or "")))
        if v.get("variable"):
            campos.append(("variable", _dobles(v["variable"])))
        if v.get("rango"):
            campos.append(("rango", _numeros(v["rango"])))
        if v.get("marcar"):
            campos.append(("marcar", _numeros(v["marcar"])))
        for clave in ("eje_x", "eje_y"):
            if v.get(clave):
                campos.append((clave, _dobles(v[clave])))
    elif tipo == "diagrama_fuerzas":
        if v.get("cuerpo") not in (None, "bloque"):
            campos.append(("cuerpo", v["cuerpo"]))
        campos.append(("vectores", "[" + ", ".join(_simples(x) for x in v.get("vectores") or []) + "]"))
        if v.get("angulo") is not None:
            campos.append(("angulo", _numero(v["angulo"])))
        if v.get("descomponer"):
            campos.append(("descomponer", "true"))
    elif tipo == "proyectil":
        campos.append(("velocidad", _simples(v.get("velocidad") or "")))
        campos.append(("angulo", _numero(v.get("angulo") or 0)))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "circulo_trig":
        campos.append(("angulo", _numero(v.get("angulo") or 0)))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    elif tipo == "poligono_regular":
        campos.append(("lados", _numero(v.get("lados") or 0)))
        campos.append(("lado", _simples(v.get("lado") or "")))
        if v.get("anotar"):
            campos.append(("anotar", "[" + ", ".join(_simples(m) for m in v["anotar"]) + "]"))
    else:
        if v.get("arreglo") not in (None, "serie"):
            campos.append(("arreglo", v["arreglo"]))
        campos.append(("fuente", _simples(v.get("fuente") or "")))
        campos.append(
            ("resistencias", "[" + ", ".join(_simples(r) for r in v.get("resistencias") or []) + "]")
        )
    return [f"      {clave}: {valor}" for clave, valor in campos]


def a_yaml(guion: dict[str, Any], cabecera: list[str] | None = None) -> str:
    """Escribe un guion (dict con la forma de ``Guion``) como YAML legible. Omite lo que está por defecto."""
    # Un salto de línea dentro de un comentario rompería el YAML
    cabecera = [c.replace("\r", " ").replace("\n", " ") for c in (cabecera or [])]
    lineas = [f"# {c}" if c else "#" for c in cabecera] + ([""] if cabecera else [])
    lineas.append(f"titulo: {_dobles(guion['titulo'])}")
    lineas.append(f"materia: {guion['materia']}")
    if guion.get("nivel"):
        lineas.append(f"nivel: {_dobles(guion['nivel'])}")
    if guion.get("molde"):
        lineas.append(f"molde: {guion['molde']}")
    for clave in ("tema", "voz", "velocidad"):
        if guion.get(clave):
            lineas.append(f"{clave}: {_dobles(guion[clave])}")

    def bloque(nombre: str, b: dict[str, Any]) -> None:
        lineas.extend(["", f"{nombre}:", f"  texto: {_dobles(b['texto'])}"])
        if b.get("voz"):
            lineas.append(f"  voz: {_dobles(b['voz'])}")
        if b.get("destacar"):
            lineas.append(f"  destacar: [{', '.join(_dobles(d) for d in b['destacar'])}]")
        if b.get("tex"):
            lineas.append(f"  tex: {_simples(b['tex'])}")
        if b.get("emoji"):
            lineas.append(f"  emoji: {_dobles(b['emoji'])}")

    bloque("gancho", guion["gancho"])
    if guion.get("gancho_variantes"):
        lineas += ["", "gancho_variantes:"]
        for v in guion["gancho_variantes"]:
            lineas.append(f"  - texto: {_dobles(v['texto'])}")
            for clave in ("voz", "emoji"):
                if v.get(clave):
                    lineas.append(f"    {clave}: {_dobles(v[clave])}")
            if v.get("tex"):
                lineas.append(f"    tex: {_simples(v['tex'])}")
            if v.get("destacar"):
                lineas.append(f"    destacar: [{', '.join(_dobles(d) for d in v['destacar'])}]")
    bloque("enunciado", guion["enunciado"])
    if guion.get("datos"):
        lineas += ["", "datos:"]
        for d in guion["datos"]:
            lineas += [f"  - tex: {_simples(d['tex'])}", f"    voz: {_dobles(d['voz'])}"]
    lineas += ["", "pasos:"]
    for p in guion["pasos"]:
        primero = True
        for clave in ("nota", "tex", "voz"):
            if p.get(clave):
                valor = _simples(p[clave]) if clave == "tex" else _dobles(p[clave])
                lineas.append(f"  {'- ' if primero else '  '}{clave}: {valor}")
                primero = False
        if p.get("destacar"):
            lineas.append(f"    destacar: [{', '.join(_simples(d) for d in p['destacar'])}]")
        if p.get("transformar") is False:
            lineas.append("    transformar: false")
        if p.get("emoji"):
            lineas.append(f"    emoji: {_dobles(p['emoji'])}")
        if p.get("visual"):
            lineas.append("    visual:")
            lineas += _visual_yaml(p["visual"])
        if p.get("error"):
            lineas.append("    error: true   # error típico: se muestra tachado")
    lineas += ["", "resultado:", f"  tex: {_simples(guion['resultado']['tex'])}",
               f"  voz: {_dobles(guion['resultado']['voz'])}"]  # fmt: skip
    if guion["resultado"].get("emoji"):
        lineas.append(f"  emoji: {_dobles(guion['resultado']['emoji'])}")
    for nombre in ("verificacion", "reto", "cierre"):
        if guion.get(nombre):
            bloque(nombre, guion[nombre])
    return "\n".join(lineas) + "\n"


def cabecera_de(ruta: Path) -> list[str]:
    """Los comentarios del inicio de un guion (supuestos de la IA, etc.), para conservarlos al guardar."""
    cabecera: list[str] = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if not linea.startswith("#"):
            break
        cabecera.append(linea[2:] if linea.startswith("# ") else linea[1:])
    return cabecera
