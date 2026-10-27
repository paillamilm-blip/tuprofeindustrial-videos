"""Editor del guion en tarjetas: lo que se ve, lo que se escucha, emojis, error típico y fórmulas
con vista previa real. Guarda un YAML normal en ``guiones/`` (el mismo que se edita a mano)."""

from __future__ import annotations

import asyncio
import copy
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from nicegui import ui
from pydantic import ValidationError

from ..config import cargar_marca
from ..emojis import EMOJIS, stickers_dir
from ..entorno import raiz_proyecto
from ..errores import ErrorMotor
from ..guion import MATERIAS, Guion, Visual, a_yaml, explicar_errores
from ..moldes import MOLDES
from ..render import slug
from ..revision import Revision, revisar
from ..temas import cargar_tema
from ..visuales import CAMPOS, VECTORES, VISUALES, opciones_select
from . import formulas, miniaturas
from .comun import url_medio

_BLOQUE = {"texto": "", "voz": "", "emoji": ""}
VACIO: dict[str, Any] = {
    "titulo": "", "materia": "fisica", "nivel": "", "tema": "", "molde": "", "voz": "", "velocidad": "",
    "gancho": {"texto": "", "voz": "", "destacar": [], "tex": "", "emoji": ""},
    "enunciado": {"texto": "", "voz": "", "destacar": []},
    "datos": [],
    "pasos": [],
    "resultado": {"tex": "", "voz": "", "emoji": ""},
    "verificacion": dict(_BLOQUE), "reto": dict(_BLOQUE), "cierre": dict(_BLOQUE),
}  # fmt: skip

# El dibujo de un paso. En el formulario los números van como texto ("0 a 2,5") porque un campo
# numérico de NiceGUI no puede quedar vacío sin convertirse en 0. El editor no sabe qué dibujos
# existen: eso lo decide el catálogo de `visuales.py`.

_FORMA = {clave: campo.forma for clave, campo in CAMPOS.items()}


def tipos_visual_del_editor() -> dict[str, str]:
    """La lista del selector: las 24 entradas del catálogo, agrupadas por materia en la etiqueta."""
    return opciones_select()


def _campos_de(tipo: str) -> tuple[str, ...]:
    return VISUALES[tipo].campos if tipo in VISUALES else ()


def _visual_vacio() -> dict[str, Any]:
    """El formulario en blanco: el valor inicial es el default del modelo, no una cadena a mano.

    Se arma desde un `Visual` validado porque los defaults viven en `guion.py`; copiarlos acá
    sería exactamente el error que esta pantalla ya cometió una vez."""
    modelo = Visual.model_validate({"tipo": "torta", "categorias": ["A 1", "B 2"]})
    salida: dict[str, Any] = {"tipo": ""}
    for clave, campo in CAMPOS.items():
        si_no_tocado = getattr(modelo, clave)
        if campo.forma == "lista":
            salida[clave] = []
        elif campo.forma == "booleano":
            salida[clave] = bool(si_no_tocado)
        elif campo.forma in ("numero", "numeros"):
            salida[clave] = ""
        else:
            salida[clave] = "" if si_no_tocado is None else str(si_no_tocado)
    return salida


def _texto_numero(valor: float) -> str:
    return f"{valor:g}".replace(".", ",")


def _numeros(texto: str) -> list[float]:
    """Los números de un texto, aceptando la coma chilena: «0 a 2,5» → [0, 2.5]."""
    return [float(n.replace(",", ".")) for n in re.findall(r"-?\d+(?:[.,]\d+)?", texto)]


def _visual_al_formulario(v: dict[str, Any]) -> dict[str, Any]:
    """El dict del guion al formulario: los números salen con coma chilena, las listas quedan listas."""
    salida = {**_visual_vacio(), **copy.deepcopy(v)}
    for clave in _campos_de(str(salida.get("tipo") or "")):
        forma = _FORMA.get(clave, "texto")
        valor = salida.get(clave)
        if forma == "numeros":
            numeros = list(valor or [])
            salida[clave] = (
                " a ".join(_texto_numero(n) for n in numeros)
                if clave == "rango" and len(numeros) == 2
                else "; ".join(_texto_numero(n) for n in numeros)
            )
        elif forma == "numero":
            salida[clave] = _texto_numero(valor) if valor not in (None, "") else ""
        elif forma == "lista":
            salida[clave] = [str(x) for x in (valor or [])]
    return salida


def _visual_al_guardar(v: dict[str, Any]) -> dict[str, Any] | None:
    """El formulario otra vez en formato guion: solo los campos del tipo elegido."""
    tipo = str(v.get("tipo") or "").strip()
    if tipo not in VISUALES:
        return None
    salida: dict[str, Any] = {"tipo": tipo}
    for clave in _campos_de(tipo):
        forma = _FORMA.get(clave, "texto")
        valor = v.get(clave)
        if forma == "numeros":
            if numeros := _numeros(str(valor or "")):
                salida[clave] = numeros
        elif forma == "numero":
            if numeros := _numeros(str(valor or "")):
                salida[clave] = numeros[0]
        elif forma == "booleano":
            salida[clave] = bool(valor)
        elif forma == "lista":
            if limpia := [str(x).strip() for x in (valor or []) if str(x).strip()]:
                salida[clave] = limpia
        elif str(valor or "").strip():
            salida[clave] = str(valor).strip()
    return salida


PASO_VACIO: dict[str, Any] = {
    "nota": "",
    "tex": "",
    "voz": "",
    "destacar": [],
    "transformar": True,
    "emoji": "",
    "error": False,
    "visual": _visual_vacio(),
}


def a_formulario(guion: Guion | None) -> dict[str, Any]:
    """Del guion a un dict completo (todos los campos presentes, vacíos = "")."""
    datos = copy.deepcopy(VACIO)
    if guion is None:
        datos["pasos"] = [copy.deepcopy(PASO_VACIO)]
        return datos
    crudo = guion.model_dump(exclude_none=True)
    for clave, valor in crudo.items():
        if isinstance(valor, dict):
            datos[clave] = {**datos.get(clave, {}), **valor}
        elif clave == "pasos":
            datos["pasos"] = [
                {**copy.deepcopy(PASO_VACIO), **p, "visual": _visual_al_formulario(p.get("visual") or {})}
                for p in valor
            ]
        else:
            datos[clave] = valor
    return datos


def _limpio(valor: Any) -> Any:
    if isinstance(valor, str):
        return valor.strip() or None
    if isinstance(valor, list):
        return [v for v in (_limpio(x) for x in valor) if v not in (None, "", [])]
    if isinstance(valor, dict):
        return {k: v for k, v in ((k, _limpio(x)) for k, x in valor.items()) if v not in (None, "", [])}
    return valor


def desde_formulario(datos: dict[str, Any]) -> dict[str, Any]:
    """Del formulario al formato del guion: sin campos vacíos ni bloques opcionales sin texto."""
    d = _limpio(copy.deepcopy(datos))
    for opcional in ("verificacion", "reto", "cierre"):
        if not d.get(opcional, {}).get("texto"):
            d.pop(opcional, None)
    d["datos"] = [x for x in d.get("datos", []) if x.get("tex") or x.get("voz")]
    d["pasos"] = [p for p in d.get("pasos", []) if p.get("voz") or p.get("tex")]
    for p in d["pasos"]:
        if p.get("transformar", True):
            p.pop("transformar", None)
        if not p.get("error"):
            p.pop("error", None)
        visual = _visual_al_guardar(p.get("visual") or {})
        if visual:
            p["visual"] = visual
        else:
            p.pop("visual", None)
    return d


def opciones_emoji(actual: str | None = None) -> dict[str, str]:
    opciones = {"": "Sin emoji"}
    opciones |= {e: f"{e}  {n}" for e, n in EMOJIS.items()}
    if stickers_dir().exists():
        opciones |= {p.stem: f"🖼  {p.stem} (tu sticker)" for p in sorted(stickers_dir().glob("*.png"))}
    if actual and actual not in opciones:
        opciones[actual] = actual
    return opciones


class _ultima_version:
    """Descarta el resultado de una fórmula que quedó vieja mientras LaTeX la dibujaba.

    El retardo lo pone Quasar (`input-debounce=400`); acá solo importa que una compilación lenta no tape
    a la fórmula que el autor escribió después.
    """

    def __init__(self) -> None:
        self._turno = 0

    def nueva(self) -> int:
        self._turno += 1
        return self._turno

    def al_dia(self, turno: int) -> bool:
        return turno == self._turno


class EditorGuion:
    def __init__(self, guion: Guion | None, ruta: Path | None, cabecera: list[str] | None = None) -> None:
        self.datos = a_formulario(guion)
        self.ruta = ruta
        self.cabecera = cabecera or []
        es_ejemplo = ruta is not None and ruta.parent.name == "ejemplos"
        base = ruta.stem if ruta else (slug(guion.titulo).replace("-", "_") if guion else "mi_guion")
        self.nombre = {"valor": f"{base}_mio" if es_ejemplo else base}
        tema = cargar_tema((guion.tema if guion else None), cargar_marca())
        self.negrita = tema.formulas_negrita
        self.al_cambiar_revision: Callable[[Revision | None, list[str]], None] | None = None

    # --------------------------------------------------------------------------------------
    # Campos
    # --------------------------------------------------------------------------------------

    def _texto(self, d: dict, clave: str, etiqueta: str, ayuda: str = "", largo: bool = False) -> ui.element:
        if largo:
            campo = ui.textarea(etiqueta, placeholder=ayuda).props("autogrow outlined dense")
        else:
            campo = ui.input(etiqueta, placeholder=ayuda).props("outlined dense")
        return campo.classes("w-full").bind_value(d, clave)

    def _emoji(self, d: dict, clave: str = "emoji") -> ui.select:
        return (
            ui.select(opciones_emoji(d.get(clave)), label="Emoji", with_input=True)
            .props("outlined dense options-dense")
            .classes("min-w-[170px]")
            .bind_value(d, clave)
        )

    def _chips(self, d: dict, clave: str, etiqueta: str, opciones: dict[str, str] | None = None) -> ui.select:
        valores = list(d.get(clave) or [])
        return (
            ui.select(
                opciones or valores, label=etiqueta, multiple=True, new_value_mode="add-unique", value=valores
            )
            .props("outlined dense use-chips use-input hide-dropdown-icon input-debounce=0")
            .classes("w-full")
            .bind_value(d, clave)
        )

    def _destacar(self, d: dict, etiqueta: str) -> ui.select:
        return self._chips(d, "destacar", etiqueta)

    # --------------------------------------------------------------------------------------
    # El dibujo del paso
    # --------------------------------------------------------------------------------------

    def _visual(self, paso: dict) -> None:
        """Los campos del dibujo elegido: los decide el catálogo, no una copia en el editor."""
        v = paso.setdefault("visual", _visual_vacio())
        with (
            ui.expansion("Dibujo en el pie de la hoja (opcional)", icon="draw", value=bool(v.get("tipo")))
            .classes("w-full")
            .props("dense")
        ):
            (
                ui.select(tipos_visual_del_editor(), label="Qué dibujar")
                .props("outlined dense")
                .classes("w-full")
                .bind_value(v, "tipo")
                .on("update:model-value", lambda: self.seccion_pasos.refresh())
            )
            tipo = str(v.get("tipo") or "")
            if not tipo:
                return
            definicion = VISUALES[tipo]
            for clave in definicion.campos:
                campo = CAMPOS[clave]
                if clave == "vectores":
                    w = self._chips(v, clave, campo.etiqueta, {k: f"{k} — {n}" for k, n in VECTORES.items()})
                elif clave == "anotar":
                    w = self._chips(
                        v, clave, campo.etiqueta, {m: m.replace("_", " ") for m in definicion.marcas}
                    )
                elif campo.forma == "opcion":
                    w = (
                        ui.select(dict(campo.opciones), label=campo.etiqueta)
                        .props("outlined dense")
                        .classes("w-full")
                        .bind_value(v, clave)
                    )
                elif campo.forma == "booleano":
                    w = ui.switch(campo.etiqueta).props("dense").bind_value(v, clave)
                elif campo.forma == "lista":
                    w = self._chips(v, clave, campo.etiqueta, None)
                else:
                    w = self._texto(v, clave, campo.etiqueta, campo.ayuda)
                # Al salir del campo se rehace la tarjeta: así el dibujo de abajo sigue lo que se escribió.
                w.on("blur", lambda: self.seccion_pasos.refresh())
            ui.label(
                f"{definicion.nombre} se dibuja en el pie de la hoja mientras suena la voz de este paso. "
                "Con un dibujo en todo el video basta."
            ).classes("tpi-ayuda")
            self._miniatura(v, tipo)

    def _miniatura(self, v: dict, tipo: str) -> None:
        """El dibujo elegido, visto acá mismo: un fotograma, sin voz y sin IA."""
        try:
            png = miniaturas.dibujar_miniatura(_visual_al_guardar(v) or {"tipo": tipo})
        except ErrorMotor as e:
            ui.label(f"⏳ Todavía no puedo dibujarlo: {e}").classes("tpi-ayuda")
            return
        with ui.row().classes("w-full justify-center"):
            ui.image(url_medio(png)).classes("w-[150px] rounded-lg border border-[#DCDCD7]")

    def _formula(self, d: dict, clave: str, etiqueta: str, ayuda: str = "") -> None:
        """Campo LaTeX con su dibujo debajo: se redibuja mientras se escribe, no al perder el foco."""
        with ui.column().classes("w-full gap-1"):
            campo = (
                ui.input(etiqueta, placeholder=ayuda)
                .props("outlined dense input-debounce=400")
                .classes("w-full font-mono")
                .bind_value(d, clave)
            )
            with ui.row().classes("tpi-formula items-center min-h-[8px] px-2"):
                imagen = ui.element("img").props('alt="Vista previa de la fórmula"')
                imagen.set_visibility(False)
                aviso = ui.label("").classes("text-sm").style("color:#D32F2F")

            versiones = _ultima_version()

            async def dibujar(tex: str) -> None:
                turno = versiones.nueva()
                svg, error = await formulas.dibujar(tex, self.negrita)
                if not versiones.al_dia(turno):
                    return  # llegó otra escritura mientras se dibujaba: ésa se pinta sola
                imagen.set_visibility(svg is not None)
                if svg is not None:
                    ancho, alto = formulas.tamano_en_pantalla(svg)
                    imagen.style(f"height:{alto}px; width:{ancho}px; max-width:100%; object-fit:contain")
                    imagen.props["src"] = url_medio(svg)
                    imagen.update()
                aviso.text = f"⚠️ {error}" if error else ""

            # El texto viene en el evento: al disparar el `.on("update:model-value")` el `bind_value` aún
            # no había escrito en `d`, y cada dibujo salía una letra detrás de lo tecleado.
            campo.on_value_change(lambda e: asyncio.create_task(dibujar(str(e.value or ""))))
            if d.get(clave):
                ui.timer(0.1, lambda: asyncio.create_task(dibujar(str(d[clave]))), once=True)

    # --------------------------------------------------------------------------------------
    # Secciones
    # --------------------------------------------------------------------------------------

    def render(self) -> None:
        d = self.datos
        with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
            with ui.row().classes("w-full items-start gap-3"):
                self._texto(d, "titulo", "Título del video", "Corto: cabe en 1–2 líneas").classes("flex-[3]")
                ui.select({k: v.capitalize() for k, v in MATERIAS.items()}, label="Materia").props(
                    "outlined dense"
                ).classes("flex-1").bind_value(d, "materia")
                self._texto(d, "nivel", "Nivel (opcional)", "Ej. 2° medio").classes("flex-1")
                ui.select({"": "Sin molde", **{c: m.nombre for c, m in MOLDES.items()}}, label="Molde").props(
                    "outlined dense"
                ).classes("flex-1").bind_value(d, "molde").tooltip(
                    "La estructura narrativa que trajo la familia: cuántos pasos y en qué orden. "
                    "Cámbiala o déjala en «Sin molde» si el guion es libre."
                )

        self._seccion_gancho()
        self._seccion_enunciado()
        self.seccion_datos()
        self.seccion_pasos()
        self._seccion_resultado()
        self._seccion_extras()

    def _tarjeta(self, titulo: str, ayuda: str) -> ui.card:
        tarjeta = ui.card().classes("tpi-hoja w-full p-5 gap-3")
        with tarjeta:
            ui.label(titulo).classes("tpi-titulo text-base")
            ui.label(ayuda).classes("tpi-ayuda -mt-2")
        return tarjeta

    def _seccion_gancho(self) -> None:
        g = self.datos["gancho"]
        with self._tarjeta(
            "Gancho (primeros 3 segundos)", "Una pregunta o un dato que sorprenda. Nada de «Hola»."
        ):
            with ui.row().classes("w-full items-start gap-3 no-wrap"):
                self._texto(g, "texto", "Lo que se ve", "¿Resuelves así?")
                self._emoji(g)
            self._texto(g, "voz", "Lo que se escucha (opcional)", "Como lo dirías en voz alta", largo=True)
            self._formula(g, "tex", "Fórmula bajo la pregunta (opcional)", "(x + 5)^2 = x^2 + 25")

    def _seccion_enunciado(self) -> None:
        e = self.datos["enunciado"]
        with self._tarjeta("Problema", "El enunciado tal como en una guía, con los números en cifras."):
            self._texto(e, "texto", "Lo que se ve", "Se deja caer una piedra desde 20 metros…", largo=True)
            self._texto(e, "voz", "Lo que se escucha (opcional)", "Cuéntalo con tus palabras", largo=True)
            self._destacar(e, "Subrayar cuando la voz lo diga (escribe y presiona Enter)")

    @ui.refreshable_method
    def seccion_datos(self) -> None:
        datos = self.datos["datos"]
        with self._tarjeta("Datos (opcional)", "Lo que sabemos. Luego quedan fijos arriba como referencia."):
            for i, dato in enumerate(datos):
                with ui.row().classes("w-full items-start gap-3 no-wrap"):
                    with ui.column().classes("flex-1 gap-0"):
                        self._formula(dato, "tex", f"Dato {i + 1} (fórmula)", "h = 20\\ \\text{m}")
                    self._texto(dato, "voz", "Se escucha", "La altura es de veinte metros.").classes("flex-1")
                    ui.button(icon="delete", on_click=lambda i=i: self._quitar("datos", i)).props(
                        "flat round color=grey-7"
                    ).tooltip("Quitar dato")
            ui.button("Agregar dato", icon="add", on_click=self._agregar_dato).props("flat color=primary")

    def _agregar_dato(self) -> None:
        self.datos["datos"].append({"tex": "", "voz": ""})
        self.seccion_datos.refresh()

    def _quitar(self, lista: str, i: int) -> None:
        del self.datos[lista][i]
        (self.seccion_datos if lista == "datos" else self.seccion_pasos).refresh()

    def _mover(self, i: int, delta: int) -> None:
        pasos = self.datos["pasos"]
        j = i + delta
        if 0 <= j < len(pasos):
            pasos[i], pasos[j] = pasos[j], pasos[i]
            self.seccion_pasos.refresh()

    @ui.refreshable_method
    def seccion_pasos(self) -> None:
        pasos = self.datos["pasos"]
        with self._tarjeta(
            "Pasos",
            "Un paso = un cambio. Cada fórmula se transforma en la siguiente. Mientras escribes una fórmula "
            "se dibuja debajo, tal como saldrá en el video.",
        ):
            for i, paso in enumerate(pasos):
                clase = "tpi-error" if paso.get("error") else ""
                with (
                    ui.card()
                    .classes(f"w-full p-4 gap-2 bg-[#FAFAF8] {clase}")
                    .props("flat bordered") as tarjeta
                ):
                    with ui.row().classes("w-full items-center gap-3 no-wrap"):
                        ui.label(str(i + 1)).classes("tpi-paso-num")
                        self._texto(paso, "nota", "Nota sobre la fórmula (opcional)", "Despejamos t")
                        self._emoji(paso)

                        def marcar(e: Any, tarjeta: ui.card = tarjeta) -> None:
                            # Solo el borde rojo (sin redibujar la sección: eso volvería a disparar el cambio)
                            if e.value:
                                tarjeta.classes(add="tpi-error")
                            else:
                                tarjeta.classes(remove="tpi-error")

                        ui.switch("Error típico", value=bool(paso.get("error")), on_change=marcar).bind_value(
                            paso, "error"
                        ).classes("whitespace-nowrap").tooltip(
                            "La fórmula equivocada se tacha con una ✗ roja"
                        )
                        ui.button(icon="arrow_upward", on_click=lambda i=i: self._mover(i, -1)).props(
                            "flat round dense color=grey-7"
                        ).tooltip("Subir")
                        ui.button(icon="arrow_downward", on_click=lambda i=i: self._mover(i, 1)).props(
                            "flat round dense color=grey-7"
                        ).tooltip("Bajar")
                        ui.button(icon="delete", on_click=lambda i=i: self._quitar("pasos", i)).props(
                            "flat round dense color=grey-7"
                        ).tooltip("Quitar paso")
                    self._formula(
                        paso, "tex", "Fórmula (vacía = paso solo hablado; en un error típico, la forma equivocada)",
                        "t = \\sqrt{\\frac{2h}{g}}",
                    )  # fmt: skip
                    self._texto(paso, "voz", "Lo que se escucha: por qué se hace este paso", largo=True)
                    with ui.row().classes("w-full items-center gap-3 no-wrap"):
                        self._destacar(
                            paso, "Enmarcar una parte (copia el trozo de la fórmula y presiona Enter)"
                        )
                        ui.switch("Transformar", value=paso.get("transformar", True)).bind_value(
                            paso, "transformar"
                        ).tooltip("Apagado: la fórmula se escribe de cero en vez de transformarse")
                    self._visual(paso)
            ui.button("Agregar paso", icon="add", on_click=self._agregar_paso).props("flat color=primary")

    def _agregar_paso(self) -> None:
        self.datos["pasos"].append(copy.deepcopy(PASO_VACIO))
        self.seccion_pasos.refresh()

    def _seccion_resultado(self) -> None:
        r = self.datos["resultado"]
        with self._tarjeta("Resultado", "La respuesta destacada, con unidades."):
            with ui.row().classes("w-full items-start gap-3 no-wrap"):
                with ui.column().classes("flex-1 gap-0"):
                    self._formula(r, "tex", "Fórmula del resultado", "t \\approx 2,02\\ \\text{s}")
                self._emoji(r)
            self._texto(r, "voz", "Lo que se escucha", "La piedra tarda unos dos segundos.", largo=True)

    def _seccion_extras(self) -> None:
        with self._tarjeta(
            "Para cerrar (opcional)", "Si dejas el texto vacío, esa parte no sale en el video."
        ):
            for clave, titulo, ayuda in (
                ("verificacion", "¿Tiene sentido?", "Una frase que compruebe o interprete el resultado"),
                ("reto", "Reto: ahora tú", "Un ejercicio parecido para que comenten"),
                ("cierre", "Cierre", "Vacío = el cierre de tu marca"),
            ):
                b = self.datos[clave]
                with ui.expansion(titulo, value=bool(b.get("texto"))).classes("w-full").props("dense"):
                    with ui.row().classes("w-full items-start gap-3 no-wrap"):
                        self._texto(b, "texto", "Lo que se ve", ayuda)
                        self._emoji(b)
                    self._texto(b, "voz", "Lo que se escucha (opcional)", largo=True)

    # --------------------------------------------------------------------------------------
    # Guardar y revisar
    # --------------------------------------------------------------------------------------

    def destino(self) -> Path:
        nombre = slug(self.nombre["valor"] or "mi_guion").replace("-", "_")
        return raiz_proyecto() / "guiones" / f"{nombre}.yaml"

    def validar(self) -> tuple[Guion | None, list[str]]:
        try:
            return Guion.model_validate(desde_formulario(self.datos)), []
        except ValidationError as e:
            return None, explicar_errores(e)

    def guardar(self) -> Path | None:
        guion, errores = self.validar()
        if guion is None:
            self._mostrar_errores(errores)
            return None
        destino = self.destino()
        # Solo se reemplaza el archivo que se abrió: otro guion con el mismo nombre nunca se pisa
        if destino.exists() and (self.ruta is None or destino.resolve() != self.ruta.resolve()):
            n = 2
            while (libre := destino.with_name(f"{destino.stem}_{n}.yaml")).exists():
                n += 1
            ui.notify(f"Ya existía {destino.name}: este guion se guarda como {libre.name}.", type="info")
            destino = libre
            self.nombre["valor"] = destino.stem
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(a_yaml(desde_formulario(self.datos), self.cabecera), encoding="utf-8")
        self.ruta = destino
        self.revisar(guion)
        return destino

    def revisar(self, guion: Guion | None = None) -> None:
        errores: list[str] = []
        if guion is None:
            guion, errores = self.validar()
        rev = revisar(guion, cargar_marca().cierre.voz) if guion is not None else None
        if self.al_cambiar_revision:
            self.al_cambiar_revision(rev, errores)

    def _mostrar_errores(self, errores: list[str]) -> None:
        if self.al_cambiar_revision:
            self.al_cambiar_revision(None, errores)
        ui.notify("El guion tiene campos por completar: mira la lista roja.", type="negative")
