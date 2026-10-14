"""Redacta guiones con IA: enunciado (texto, foto o PDF) → guion YAML listo para revisar.

Flujo (con la persona siempre al final del ciclo):
1. Gemini resuelve el ejercicio y escribe el guion en un formato JSON fijo.
2. El motor lo valida: formato del guion, fórmulas LaTeX (se compilan de verdad) y las
   reglas de ``tpi revisar``.
3. Gemini, como profesor revisor y con contexto nuevo, rehace los cálculos.
4. Si hay problemas, se le pide corregirlos (hasta 2 rondas).
5. Se guarda ``guiones/<nombre>.yaml`` con los supuestos y advertencias como comentarios.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from . import ia
from .entorno import PLANTILLAS_DIR, raiz_proyecto
from .errores import ErrorMotor
from .guion import Guion, cargar_guion, explicar_errores, sin_tildes

RONDAS_DE_CORRECCION = 2
MAX_BYTES_ARCHIVO = 18 * 1024 * 1024  # límite práctico para enviar un archivo dentro de la petición
TIPOS_ARCHIVO = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".pdf": "application/pdf",
}
TEXTO = {".txt", ".md"}


# ------------------------------------------------------------------------------------------
# Formato que debe devolver Gemini (plano y explícito: más fácil de cumplir para el modelo)
# ------------------------------------------------------------------------------------------


class DatoIA(BaseModel):
    tex: str = Field(description="Dato en LaTeX, ej. h = 20\\ \\text{m}")
    voz: str = Field(description="El dato dicho en palabras, sin cifras ni símbolos")


class PasoIA(BaseModel):
    nota: str = Field(description="Qué se hace en este paso, máximo 5 palabras")
    tex: str = Field(description="Ecuación completa del paso en LaTeX, sin $")
    voz: str = Field(description="Por qué se hace este paso, en palabras, sin cifras ni símbolos")
    destacar: list[str] = Field(default_factory=list, description="0 o 1 fragmento copiado del tex")


class GuionIA(BaseModel):
    es_ejercicio: bool = Field(description="false si no es un ejercicio resoluble")
    motivo: str = Field(default="", description="Solo si es_ejercicio es false: por qué")
    titulo: str
    materia: Literal["matematica", "fisica", "ingenieria"]
    nivel: str
    gancho_texto: str
    gancho_voz: str
    enunciado_texto: str
    enunciado_voz: str
    enunciado_destacar: list[str]
    datos: list[DatoIA]
    pasos: list[PasoIA]
    resultado_tex: str
    resultado_voz: str
    verificacion_texto: str
    verificacion_voz: str
    reto_texto: str
    reto_voz: str
    supuestos: list[str] = Field(
        description="Supuestos o aclaraciones para el profesor (no salen en el video)"
    )


class RevisionIA(BaseModel):
    aprobado: bool
    problemas: list[str]


EJEMPLO = GuionIA(
    es_ejercicio=True,
    titulo="Caída libre: ¿cuánto tarda en caer?",
    materia="fisica",
    nivel="2° medio",
    gancho_texto="¿Cuánto tarda una piedra en caer 20 metros?",
    gancho_voz="¿Cuánto tarda una piedra en caer veinte metros? Menos de lo que crees.",
    enunciado_texto="Se deja caer una piedra desde 20 metros de altura. ¿Cuánto tarda en llegar al suelo? "
    "Usa g = 9,8 m/s².",
    enunciado_voz="Soltamos una piedra desde veinte metros de altura. ¿Cuánto demora en llegar al suelo?",
    enunciado_destacar=["20 metros", "g = 9,8 m/s²"],
    datos=[
        DatoIA(tex=r"h = 20\ \text{m}", voz="La altura es de veinte metros."),
        DatoIA(
            tex=r"g = 9,8\ \text{m/s}^2", voz="La gravedad, nueve coma ocho metros por segundo al cuadrado."
        ),
        DatoIA(tex="t = ?", voz="Y buscamos el tiempo."),
    ],
    pasos=[
        PasoIA(
            nota="Caída libre",
            tex=r"h = \frac{1}{2} g t^2",
            voz="Como la piedra parte del reposo, usamos la ecuación de caída libre.",
        ),
        PasoIA(
            nota="Despejamos t",
            tex=r"t = \sqrt{\frac{2h}{g}}",
            voz="Despejamos el tiempo. Queda la raíz de dos h sobre g.",
        ),
        PasoIA(
            nota="Reemplazamos",
            tex=r"t = \sqrt{\frac{2 \cdot 20}{9,8}}",
            voz="Reemplazamos la altura y la gravedad.",
        ),
        PasoIA(
            nota="Calculamos",
            tex=r"t = \sqrt{4,08}",
            voz="Dos por veinte es cuarenta. Dividido en nueve coma ocho, da cuatro coma cero ocho.",
        ),
    ],
    resultado_tex=r"t \approx 2,02\ \text{s}",
    resultado_voz="Sacamos la raíz: la piedra tarda unos dos segundos en caer.",
    verificacion_texto="Con el doble de altura no tarda el doble: el tiempo crece con la raíz de la altura.",
    verificacion_voz="Ojo: con el doble de altura no tarda el doble. El tiempo crece con la raíz de la altura.",
    reto_texto="¿Cuánto tarda en caer desde 45 metros? Usa g = 10 m/s².",
    reto_voz="Ahora tú. ¿Cuánto tarda desde cuarenta y cinco metros, con g igual a diez? "
    "Déjalo en los comentarios.",
    supuestos=[],
)


# ------------------------------------------------------------------------------------------
# Entrada: texto, foto o PDF
# ------------------------------------------------------------------------------------------


@dataclass
class Entrada:
    texto: str | None = None  # enunciado escrito
    datos: bytes | None = None  # foto o PDF
    tipo: str | None = None  # mime type del archivo
    origen: str = "texto"

    def partes(self) -> list[Any]:
        from google.genai import types

        if self.datos is not None:
            return [
                types.Part.from_bytes(data=self.datos, mime_type=self.tipo or "application/octet-stream"),
                "El ENUNCIADO está en el archivo adjunto. Transcríbelo fielmente en enunciado_texto.",
            ]
        return [f"ENUNCIADO:\n{self.texto}"]


def leer_entrada(valor: str) -> Entrada:
    """Interpreta el argumento: ruta a .txt/.md/.png/.jpg/.heic/.pdf, o el enunciado mismo."""
    ruta = Path(valor).expanduser()
    parece_archivo = bool(re.search(r"\.[A-Za-z0-9]{2,5}$", valor.strip())) and len(valor) < 300
    if ruta.is_file():
        sufijo = ruta.suffix.lower()
        if sufijo in TEXTO:
            texto = ruta.read_text(encoding="utf-8").strip()
            if not texto:
                raise ErrorMotor(f"{ruta.name} está vacío.")
            return Entrada(texto=texto, origen=ruta.name)
        if sufijo in TIPOS_ARCHIVO:
            datos = ruta.read_bytes()
            if len(datos) > MAX_BYTES_ARCHIVO:
                raise ErrorMotor(
                    f"{ruta.name} pesa {len(datos) // (1024 * 1024)} MB; el máximo es 18 MB.",
                    ayuda="Envía una captura de pantalla del ejercicio (Cmd+Shift+4 en el Mac).",
                )
            return Entrada(datos=datos, tipo=TIPOS_ARCHIVO[sufijo], origen=ruta.name)
        raise ErrorMotor(
            f"No sé leer archivos {sufijo}.", ayuda="Usa .txt, una foto (.jpg, .png, .heic) o un .pdf."
        )
    if parece_archivo and " " not in valor.strip():
        raise ErrorMotor(
            f"No encuentro el archivo «{valor}».",
            ayuda="Revisa la ruta o escribe el enunciado entre comillas.",
        )
    texto = " ".join(valor.split())
    if len(texto) < 15:
        raise ErrorMotor(
            "El enunciado es muy corto.",
            ayuda='Ejemplo: ./tpi redactar "Un auto acelera de 0 a 20 m/s en 5 s…"',
        )
    return Entrada(texto=texto, origen="texto")


# ------------------------------------------------------------------------------------------
# Limpieza de lo que devuelve el modelo
# ------------------------------------------------------------------------------------------

_UNICODE_A_LATEX = {
    "·": r" \cdot ", "×": r" \times ", "−": "-", "–": "-", "≈": r" \approx ", "≠": r" \neq ",
    "≤": r" \leq ", "≥": r" \geq ", "Ω": r"\Omega ", "π": r"\pi ", "Δ": r"\Delta ", "θ": r"\theta ",
    "α": r"\alpha ", "β": r"\beta ", "μ": r"\mu ", "λ": r"\lambda ", "ω": r"\omega ", "ρ": r"\rho ",
    "°": r"^{\circ}", "²": "^2", "³": "^3", "∞": r"\infty ",
}  # fmt: skip


def limpiar_tex(tex: str) -> str:
    tex = " ".join(tex.split())
    for inicio, fin in (("$$", "$$"), ("$", "$"), (r"\(", r"\)"), (r"\[", r"\]")):
        if tex.startswith(inicio) and tex.endswith(fin) and len(tex) > len(inicio) + len(fin):
            tex = tex[len(inicio) : -len(fin)].strip()
    tex = re.sub(r"\\\\(?=[A-Za-z])", r"\\", tex)  # "\\frac" (doble escape) → "\frac"
    for caracter, latex in _UNICODE_A_LATEX.items():
        tex = tex.replace(caracter, latex)
    return " ".join(tex.split())


def _texto(s: str) -> str:
    return " ".join((s or "").replace("—", ", ").split())


def a_guion(g: GuionIA) -> dict[str, Any]:
    """Convierte la respuesta del modelo al formato de guion del motor."""
    enunciado = _texto(g.enunciado_texto)
    pasos = []
    for p in g.pasos:
        tex = limpiar_tex(p.tex)
        paso: dict[str, Any] = {"nota": _texto(p.nota) or None, "tex": tex, "voz": _texto(p.voz)}
        destacar = [d.strip() for d in p.destacar if d.strip() and d.strip() in tex][:1]
        if destacar:
            paso["destacar"] = destacar
        pasos.append(paso)
    guion: dict[str, Any] = {
        "titulo": _texto(g.titulo),
        "materia": g.materia,
        "nivel": _texto(g.nivel) or None,
        "gancho": {"texto": _texto(g.gancho_texto), "voz": _texto(g.gancho_voz)},
        "enunciado": {
            "texto": enunciado,
            "voz": _texto(g.enunciado_voz),
            "destacar": [d.strip() for d in g.enunciado_destacar if d.strip() and d.strip() in enunciado][:3],
        },
        "datos": [{"tex": limpiar_tex(d.tex), "voz": _texto(d.voz)} for d in g.datos],
        "pasos": pasos,
        "resultado": {"tex": limpiar_tex(g.resultado_tex), "voz": _texto(g.resultado_voz)},
    }
    if _texto(g.verificacion_texto):
        guion["verificacion"] = {
            "texto": _texto(g.verificacion_texto),
            "voz": _texto(g.verificacion_voz) or None,
        }
    if _texto(g.reto_texto):
        guion["reto"] = {"texto": _texto(g.reto_texto), "voz": _texto(g.reto_voz) or None}
    return guion


# ------------------------------------------------------------------------------------------
# Revisiones automáticas
# ------------------------------------------------------------------------------------------


def _error_latex(excepcion: Exception) -> str:
    """El error útil del log de LaTeX, ej. «Undefined control sequence: \\sqrtt»."""
    m = re.search(r"log file: (\S+\.log)", str(excepcion))
    if m and Path(m.group(1)).exists():
        lineas = Path(m.group(1)).read_text(encoding="utf-8", errors="replace").splitlines()
        for i, linea in enumerate(lineas):
            if linea.startswith("! "):
                error = linea[2:].strip().rstrip(".")
                # TeX marca el punto del error cortando la línea: el último comando antes del corte
                siguiente = lineas[i + 1] if i + 1 < len(lineas) else ""
                culpable = re.findall(r"\\[A-Za-z]+", siguiente.replace("\\special", ""))
                return f"{error}: {culpable[-1]}" if culpable and "control sequence" in error else error
    return str(excepcion).splitlines()[0][:160]


class SinLatex(Exception):
    """LaTeX no está instalado: las fórmulas no se pudieron compilar."""


def errores_latex(guion: Guion) -> list[str]:
    """Compila cada fórmula con LaTeX (igual que al crear el video) y devuelve los errores."""
    from manim import MathTex, tempconfig

    from .entorno import latex_disponible, preparar
    from .tex import corregir_decimales, plantilla_tex

    preparar()
    if not all(latex_disponible()):  # sin LaTeX no se puede comprobar (y no es culpa de la IA)
        raise SinLatex
    formulas = [(f"dato {i}", d.tex) for i, d in enumerate(guion.datos, 1)]
    formulas += [(f"paso {i}", p.tex) for i, p in enumerate(guion.pasos, 1) if p.tex]
    formulas.append(("resultado", guion.resultado.tex))
    problemas = []
    registro = logging.getLogger("manim")
    nivel = registro.level
    cache = Path(tempfile.gettempdir()) / "tpi-tex"
    with tempconfig({"media_dir": str(cache), "tex_template": plantilla_tex(), "verbosity": "CRITICAL"}):
        registro.setLevel(logging.CRITICAL)
        try:
            for donde, tex in formulas:
                try:
                    MathTex(corregir_decimales(tex))
                except Exception as e:
                    problemas.append(f"{donde}: la fórmula «{tex}» no compila en LaTeX ({_error_latex(e)}).")
        finally:
            registro.setLevel(nivel)
    return problemas


def problemas_de_formato(guion: Guion) -> list[str]:
    from .config import cargar_marca
    from .revision import revisar

    rev = revisar(guion, cargar_marca().cierre.voz)
    return [f"{a.donde}: {a.mensaje}" for a in rev.avisos if a.nivel == "advertencia"]


# ------------------------------------------------------------------------------------------
# Llamadas a Gemini
# ------------------------------------------------------------------------------------------


def _sistema() -> str:
    plantilla = (PLANTILLAS_DIR / "ia" / "sistema.md").read_text(encoding="utf-8")
    ejemplo = json.dumps(EJEMPLO.model_dump(), ensure_ascii=False, indent=1)
    return plantilla.replace("{{EJEMPLO}}", ejemplo)


def _pedir(
    cliente: Any, modelo: str, sistema: str, contenido: list[Any], esquema: type[BaseModel], pensar: str
):
    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=sistema,
        response_mime_type="application/json",
        response_json_schema=esquema.model_json_schema(),
        thinking_config=types.ThinkingConfig(thinking_level=pensar),
        max_output_tokens=32768,  # incluye el razonamiento interno del modelo
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True
        ),  # no usamos herramientas
    )
    try:
        respuesta = cliente.models.generate_content(model=modelo, contents=contenido, config=config)
    except ErrorMotor:
        raise
    except Exception as e:
        raise ia.explicar_error(e, modelo) from e
    texto = respuesta.text or ""
    if not texto.strip():
        candidato = (respuesta.candidates or [None])[0]
        motivo = getattr(getattr(candidato, "finish_reason", None), "value", None)
        bloqueo = getattr(getattr(respuesta, "prompt_feedback", None), "block_reason", None)
        raise ErrorMotor(
            f"Gemini no devolvió respuesta ({motivo or bloqueo or 'sin motivo'}).",
            ayuda="Repite el comando; si sigue pasando, prueba con el enunciado en texto.",
        )
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    try:
        return esquema.model_validate_json(texto)
    except ValidationError as e:
        raise ErrorMotor(
            "Gemini devolvió una respuesta con un formato inesperado.",
            ayuda="Repite el comando (a veces pasa). Detalle: " + "; ".join(explicar_errores(e))[:300],
        ) from e


def _contenido_base(entrada: Entrada, materia: str | None, nivel: str | None) -> list[Any]:
    contenido = entrada.partes()
    pistas = []
    if materia:
        pistas.append(f"Materia: {materia}.")
    pistas.append(f"Nivel de los estudiantes: {nivel or 'enseñanza media (Chile)'}.")
    contenido.append(" ".join(pistas))
    return contenido


# ------------------------------------------------------------------------------------------
# Escritura del YAML (mismo estilo que los ejemplos: textos con "…", fórmulas con '…')
# ------------------------------------------------------------------------------------------


def _dobles(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _simples(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def a_yaml(guion: dict[str, Any], cabecera: list[str]) -> str:
    # Un salto de línea dentro de un comentario rompería el YAML
    cabecera = [c.replace("\r", " ").replace("\n", " ") for c in cabecera]
    lineas = [f"# {c}" if c else "#" for c in cabecera] + [""]
    lineas.append(f"titulo: {_dobles(guion['titulo'])}")
    lineas.append(f"materia: {guion['materia']}")
    if guion.get("nivel"):
        lineas.append(f"nivel: {_dobles(guion['nivel'])}")

    def bloque(nombre: str, b: dict[str, Any]) -> None:
        lineas.extend(["", f"{nombre}:", f"  texto: {_dobles(b['texto'])}"])
        if b.get("voz"):
            lineas.append(f"  voz: {_dobles(b['voz'])}")
        if b.get("destacar"):
            lineas.append(f"  destacar: [{', '.join(_dobles(d) for d in b['destacar'])}]")

    bloque("gancho", guion["gancho"])
    bloque("enunciado", guion["enunciado"])
    if guion["datos"]:
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
    lineas += ["", "resultado:", f"  tex: {_simples(guion['resultado']['tex'])}",
               f"  voz: {_dobles(guion['resultado']['voz'])}"]  # fmt: skip
    for nombre in ("verificacion", "reto"):
        if guion.get(nombre):
            bloque(nombre, guion[nombre])
    return "\n".join(lineas) + "\n"


def _nombre_archivo(titulo: str, nombre: str | None, forzar: bool) -> Path:
    base = re.sub(r"[^a-z0-9]+", "_", sin_tildes((nombre or titulo).lower())).strip("_")[:50] or "guion"
    carpeta = raiz_proyecto() / "guiones"
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{base}.yaml"
    n = 2
    while destino.exists() and not forzar:
        destino = carpeta / f"{base}_{n}.yaml"
        n += 1
    return destino


# ------------------------------------------------------------------------------------------
# Orquestación
# ------------------------------------------------------------------------------------------


@dataclass
class ResultadoRedaccion:
    ruta: Path
    guion: Guion
    supuestos: list[str]
    pendientes: list[str]  # problemas que quedaron sin resolver (para que el profesor los vea)
    rondas: int
    modelo: str
    revisado_por_ia: bool
    historial: list[str] = field(default_factory=list)


def redactar(
    valor: str,
    materia: str | None = None,
    nivel: str | None = None,
    modelo: str = ia.MODELO_POR_DEFECTO,
    nombre: str | None = None,
    forzar: bool = False,
    revisar_con_ia: bool = True,
    avisar=lambda mensaje: None,
) -> ResultadoRedaccion:
    entrada = leer_entrada(valor)
    cliente = ia.cliente()
    sistema = _sistema()
    base = _contenido_base(entrada, materia, nivel)
    revisor = (PLANTILLAS_DIR / "ia" / "revisor.md").read_text(encoding="utf-8")
    historial: list[str] = []
    sin_latex = False

    avisar("Gemini está resolviendo el ejercicio y escribiendo el guion (30–90 s)…")
    respuesta = _pedir(cliente, modelo, sistema, base, GuionIA, "high")
    rondas = 0
    revisado = False
    while True:
        if not respuesta.es_ejercicio:
            raise ErrorMotor(
                f"Gemini dice que esto no es un ejercicio que pueda resolver: {respuesta.motivo or 'sin motivo'}",
                ayuda="Revisa el enunciado (¿está completo y se lee bien en la foto?).",
            )
        problemas: list[str] = []
        datos = a_guion(respuesta)
        if materia:  # lo que pide la persona manda sobre lo que deduce la IA
            datos["materia"] = materia
        if nivel:
            datos["nivel"] = nivel
        try:
            guion = Guion.model_validate(datos)
        except ValidationError as e:
            guion = None
            problemas += [f"formato: {linea}" for linea in explicar_errores(e)]
        if guion is not None:
            avisar("Compilando las fórmulas con LaTeX…")
            try:
                problemas += errores_latex(guion)
            except SinLatex:
                sin_latex = True
            problemas += problemas_de_formato(guion)
            if revisar_con_ia and not problemas:
                avisar("Gemini revisa la matemática como profesor revisor…")
                guion_json = json.dumps(respuesta.model_dump(), ensure_ascii=False)
                revision = _pedir(cliente, modelo, revisor, [*base, f"GUION A REVISAR (JSON):\n{guion_json}"],
                                  RevisionIA, "high")  # fmt: skip
                revisado = True
                if not revision.aprobado:
                    problemas += [f"revisor: {p}" for p in revision.problemas] or [
                        "revisor: no aprobó el guion"
                    ]
        historial += [f"ronda {rondas}: {p}" for p in problemas]
        if not problemas or rondas >= RONDAS_DE_CORRECCION:
            break
        rondas += 1
        avisar(f"Corrigiendo {len(problemas)} detalle(s) (ronda {rondas} de {RONDAS_DE_CORRECCION})…")
        anterior = json.dumps(respuesta.model_dump(), ensure_ascii=False)
        pedido = "\n".join(
            [
                "Tu respuesta anterior tiene estos problemas. Corrígelos y devuelve el JSON completo corregido:",
                *[f"- {p}" for p in problemas],
                "",
                f"RESPUESTA ANTERIOR (JSON):\n{anterior}",
            ]
        )
        respuesta = _pedir(cliente, modelo, sistema, [*base, pedido], GuionIA, "high")

    if guion is None:
        detalle = "\n".join(f"  • {p}" for p in problemas[:8])
        raise ErrorMotor(f"No logré un guion válido tras {rondas + 1} intentos:\n{detalle}",
                         ayuda="Repite el comando o escribe el enunciado más claro.")  # fmt: skip

    destino = _nombre_archivo(guion.titulo, nombre, forzar)
    cabecera = [
        f"Guion redactado con IA ({modelo}) el {dt.date.today():%d-%m-%Y} a partir de: {entrada.origen}",
        "REVISA la matemática y los textos antes de publicar: la IA puede equivocarse.",
    ]
    if sin_latex:
        problemas.append(
            "no se compilaron las fórmulas porque falta LaTeX (ejecuta ./scripts/instalar_mac.sh)"
        )
    if respuesta.supuestos:
        cabecera += ["", "Supuestos de la IA:"] + [f"  - {s}" for s in respuesta.supuestos]
    if problemas:
        cabecera += ["", "Quedaron observaciones por revisar:"] + [f"  - {p}" for p in problemas]
    elif revisado:
        cabecera += [
            "",
            "Revisión automática: fórmulas compiladas y cálculos revisados por la IA (sin observaciones).",
        ]
    destino.write_text(a_yaml(datos, cabecera), encoding="utf-8")
    guion_final = cargar_guion(destino)  # comprueba que el archivo escrito se lee igual
    return ResultadoRedaccion(
        ruta=destino,
        guion=guion_final,
        supuestos=respuesta.supuestos,
        pendientes=problemas,
        rondas=rondas,
        modelo=modelo,
        revisado_por_ia=revisado,
        historial=historial,
    )
