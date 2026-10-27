"""Estilos: ver los temas, elegir el de siempre, y duplicar uno para personalizar colores, letras,
fondo (con tu foto), la hoja, los subtítulos y las animaciones. Todo queda en ``mis_ajustes/``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from nicegui import events, run, ui
from pydantic import ValidationError

from ...config import cargar_marca, guardar_ajustes_marca
from ...errores import ErrorMotor
from ...temas import (
    FONDOS_DIR,
    TEMA_POR_DEFECTO,
    Tema,
    cargar_tema,
    fondos_usuario_dir,
    guardar_tema,
    id_tema,
    listar_temas,
    temas_usuario_dir,
)
from ...tipografia import PARA_SUBTITULOS, PARA_TEXTO, PARA_TITULOS
from ...vista_previa import en_cache
from ..comun import confirmar, marco, titulo_seccion, url_medio
from ..tareas import TAREAS, Tarea

COLORES = (
    ("titulos", "Títulos"), ("texto", "Explicaciones"), ("formulas", "Fórmulas"), ("acento", "Destacados"),
    ("exito", "Resultado"), ("error", "Error típico"), ("panel", "Tarjetas"), ("borde", "Bordes"),
    ("fondo", "Fondo"),
)  # fmt: skip


def preparar_fondo(origen: Path, destino: Path) -> Path:
    """Tu foto como fondo: recortada a 9:16, difuminada y oscurecida para que todo se lea bien."""
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError

    try:
        imagen = ImageOps.exif_transpose(Image.open(origen)).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise ErrorMotor(
            "No pude abrir esa imagen.",
            ayuda="Usa una foto JPG o PNG (en el Mac: Archivo → Exportar como JPEG).",
        ) from e
    imagen = ImageOps.fit(imagen, (1080, 1920), Image.LANCZOS)
    imagen = imagen.filter(ImageFilter.GaussianBlur(14))
    imagen = ImageEnhance.Brightness(imagen).enhance(0.72)
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagen.save(destino, optimize=True)
    return destino


def _fondos(actual: str | None = None) -> dict[str, str]:
    opciones = {p.stem: f"{p.stem} (incluido)" for p in sorted(FONDOS_DIR.glob("*.png"))}
    if fondos_usuario_dir().exists():
        opciones |= {
            p.stem: f"{p.stem} (tuyo)"
            for p in sorted(fondos_usuario_dir().glob("*.png"))
            if not p.stem.startswith("_")
        }
    if actual and actual not in opciones:  # una lista sin el valor actual haría fallar la página
        opciones[actual] = f"{actual} (no encontrado)"
    return opciones


def _opciones(base: tuple[str, ...], actual: str | None) -> list[str]:
    """Las opciones del panel más el valor actual (si un tema editado a mano usa otra letra)."""
    return list(dict.fromkeys([*base, *([actual] if actual else [])]))


def _cuadros(identificador: str, contenedor: ui.element) -> None:
    contenedor.clear()
    cuadros = en_cache(identificador)
    with contenedor:
        if not cuadros:
            ui.label("Sin vista previa todavía").classes("tpi-ayuda")
            return
        for cuadro in cuadros:
            ui.image(url_medio(cuadro)).classes("w-[120px] rounded border")


async def generar_vista(
    identificador: str, contenedor: ui.element, estado: ui.label | None = None, automatica: bool = False
) -> bool:
    """Crea la vista previa (3 cuadros). ``automatica``: sin avisos si hay otro trabajo en curso."""
    if TAREAS.ocupado():
        if not automatica:
            ui.notify("Hay un trabajo en curso: espera a que termine.", type="warning")
        return False

    def avance(t: Tarea) -> None:
        if estado is not None:
            estado.text = f"Creando vista previa… {round(t.avance * 100)} %"

    args = ["vista-previa", "--tema", identificador] + ([] if automatica else ["--forzar"])
    tarea = await TAREAS.ejecutar("Vista previa del estilo", args, al_cambiar=avance)
    if estado is not None:
        estado.text = ""
    if not tarea.ok:
        mensaje = (tarea.error or {}).get("mensaje", "No se pudo crear la vista previa")
        if estado is not None and automatica:
            estado.text = f"⚠️ {mensaje}"
        elif not tarea.cancelada:
            ui.notify(mensaje, type="negative", multi_line=True)
        return False
    if not contenedor.is_deleted:
        _cuadros(identificador, contenedor)
    return True


async def _completar_vistas(pendientes: list[tuple[str, ui.element, ui.label]]) -> None:
    """Primera visita: crea las vistas previas que faltan, de a una y sin estorbar otros trabajos."""
    for identificador, contenedor, estado in pendientes:
        if contenedor.is_deleted or not await generar_vista(
            identificador, contenedor, estado, automatica=True
        ):
            return


def lista_de_temas() -> None:
    """La lista de estilos (una por pestaña: refrescarla no toca otras pestañas)."""

    @ui.refreshable
    def lista() -> None:
        actual = cargar_marca().tema
        pendientes: list[tuple[str, ui.element, ui.label]] = []
        for identificador, tema, propio in listar_temas():
            with (
                ui.card().classes("tpi-hoja w-full p-5"),
                ui.row().classes("w-full items-start gap-6 no-wrap"),
            ):
                cuadros = ui.row().classes("gap-2 min-w-[380px]")
                _cuadros(identificador, cuadros)
                with ui.column().classes("flex-1 gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(tema.nombre).classes("tpi-titulo text-lg")
                        if identificador == actual:
                            ui.chip("⭐ El de siempre", color="primary", text_color="white").props("dense")
                        if propio:
                            ui.chip("Tuyo", color="grey-7", text_color="white").props("dense")
                    ui.label(tema.descripcion or "—").classes("tpi-ayuda")
                    estado = ui.label("").classes("tpi-ayuda")
                    if en_cache(identificador) is None:
                        pendientes.append((identificador, cuadros, estado))
                    with ui.row().classes("gap-2"):
                        if identificador != actual:

                            def usar(i: str = identificador) -> None:
                                guardar_ajustes_marca({"tema": i})
                                ui.notify("Listo: tus próximos videos usarán este estilo.", type="positive")
                                lista.refresh()

                            ui.button("Usar siempre", icon="star", on_click=usar).props("outline")
                        ui.button(
                            "Ver vista previa", icon="visibility",
                            on_click=lambda i=identificador, c=cuadros, e=estado: generar_vista(i, c, e),
                        ).props("flat")  # fmt: skip
                        ui.button("Duplicar y personalizar", icon="content_copy",
                                  on_click=lambda i=identificador, t=tema: _duplicar(i, t)).props("flat")  # fmt: skip
                        if propio:
                            ui.button("Editar", icon="edit",
                                      on_click=lambda i=identificador: ui.navigate.to(f"/estilos/editar?tema={i}"))  # fmt: skip

                            def borrar(i: str = identificador) -> None:
                                (temas_usuario_dir() / f"{i}.yaml").unlink(missing_ok=True)
                                if cargar_marca().tema == i:
                                    guardar_ajustes_marca({"tema": TEMA_POR_DEFECTO})
                                ui.notify("Estilo borrado", type="info")
                                lista.refresh()

                            ui.button(icon="delete", on_click=lambda i=identificador, n=tema.nombre: confirmar(
                                f"¿Borrar tu estilo «{n}»?", lambda: borrar(i))).props("flat round color=grey-7")  # fmt: skip

        if pendientes:
            ui.timer(0.5, lambda: _completar_vistas(pendientes), once=True)

    lista()


def _duplicar(identificador: str, tema: Tema) -> None:
    with ui.dialog() as dialogo, ui.card().classes("p-6 gap-3 w-[420px]"):
        ui.label("Duplicar estilo").classes("tpi-titulo text-lg")
        nombre = (
            ui.input("Nombre del nuevo estilo", value=f"{tema.nombre} mío")
            .props("outlined")
            .classes("w-full")
        )

        def crear() -> None:
            nuevo_id = id_tema(nombre.value or "mi_estilo")
            if (temas_usuario_dir() / f"{nuevo_id}.yaml").exists() or nuevo_id in {
                i for i, _, _ in listar_temas()
            }:
                ui.notify("Ya existe un estilo con ese nombre: elige otro.", type="warning")
                return
            # Con los colores ya resueltos (el estilo original los toma de marca.yaml)
            completo = cargar_tema(identificador, cargar_marca())
            copia = completo.model_copy(update={"nombre": nombre.value.strip(), "usar_marca": False})
            guardar_tema(nuevo_id, copia)
            dialogo.close()
            ui.navigate.to(f"/estilos/editar?tema={nuevo_id}")

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Duplicar", on_click=crear)
    dialogo.open()


def _color(d: dict[str, Any], clave: str, etiqueta: str) -> None:
    ui.color_input(etiqueta, value=d.get(clave, "")).props("outlined dense").classes("w-44").bind_value(
        d, clave
    )


class EditorTema:
    def __init__(self, identificador: str) -> None:
        self.id = identificador
        self.t = cargar_tema(identificador, cargar_marca()).model_dump(mode="json")
        materias = self.t["materias"]
        self.etiquetas = {"color": materias.get("matematica", "#D32F2F")}  # las 3 materias con un color

    def render(self) -> None:
        t = self.t
        with ui.row().classes("w-full gap-6 items-start no-wrap"):
            with ui.column().classes("flex-[3] gap-4"):
                with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
                    ui.label("General").classes("tpi-titulo")
                    ui.input("Nombre").props("outlined dense").classes("w-full").bind_value(t, "nombre")
                    ui.input("Descripción").props("outlined dense").classes("w-full").bind_value(
                        t, "descripcion"
                    )
                    ui.toggle({"hoja": "Hoja de desarrollo", "pizarra": "Pizarra"}).bind_value(t, "marco")
                with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
                    ui.label("Colores").classes("tpi-titulo")
                    with ui.row().classes("gap-3"):
                        for clave, etiqueta in COLORES:
                            _color(t["colores"], clave, etiqueta)
                        _color(self.etiquetas, "color", "Etiquetas (PROBLEMA…)")
                with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
                    ui.label("Letras").classes("tpi-titulo")
                    with ui.row().classes("gap-3 items-center"):
                        titulos, texto = t["tipografia"]["titulos"], t["tipografia"]["texto"]
                        ui.select(_opciones(PARA_TITULOS, titulos["familia"]), label="Títulos").props(
                            "outlined dense"
                        ).classes("w-48").bind_value(titulos, "familia")
                        ui.switch("Títulos en MAYÚSCULAS").bind_value(
                            t["tipografia"]["titulos"], "mayusculas"
                        )
                        ui.select(_opciones(PARA_TEXTO, texto["familia"]), label="Explicaciones").props(
                            "outlined dense"
                        ).classes("w-48").bind_value(texto, "familia")
                        ui.switch("Fórmulas en negrita").bind_value(t, "formulas_negrita")
                self._fondo()
                self._hoja()
                self._nota()
                self._subtitulos()
                with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
                    ui.label("Movimiento").classes("tpi-titulo")
                    with ui.row().classes("gap-6"):
                        plumon = {"valor": t["animacion"]["titulos"] == "plumon"}
                        ui.switch("Títulos escritos con plumón", value=plumon["valor"], on_change=lambda e: t[
                            "animacion"].__setitem__("titulos", "plumon" if e.value else "aparecer"))  # fmt: skip
                        ui.switch("Emojis 3D").bind_value(t, "emojis")
            with ui.column().classes("flex-[2] gap-3 sticky top-20"):
                with ui.card().classes("tpi-hoja w-full p-5 gap-3 items-center"):
                    ui.label("Vista previa").classes("tpi-titulo")
                    self.cuadros = ui.row().classes("gap-2 justify-center")
                    _cuadros(self.id, self.cuadros)
                    self.estado = ui.label("").classes("tpi-ayuda")
                    ui.button("Guardar y ver vista previa", icon="visibility", on_click=self.guardar_y_ver)
                    ui.button(
                        "Volver a Estilos", icon="arrow_back", on_click=lambda: ui.navigate.to("/estilos")
                    ).props("flat")

    def _fondo(self) -> None:
        fondo = self.t["fondo"]
        with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
            ui.label("Fondo").classes("tpi-titulo")
            ui.toggle(
                {
                    "imagen": "Imagen",
                    "color": "Color liso",
                    "degradado": "Degradado",
                    "cuadricula": "Cuadrícula",
                }
            ).bind_value(fondo, "tipo")
            with ui.row().classes("gap-3 items-center"):
                self.selector_fondo = (
                    ui.select(_fondos(fondo.get("imagen")), label="Imagen")
                    .props("outlined dense")
                    .classes("w-60")
                )
                self.selector_fondo.bind_value(fondo, "imagen")
                ui.upload(label="Subir tu foto (se difumina y oscurece sola)", auto_upload=True, max_files=1,
                          on_upload=self._subir_fondo).props('accept=".jpg,.jpeg,.png,.webp" flat bordered')  # fmt: skip
            with ui.row().classes("gap-3"):
                for i, etiqueta in enumerate(("Degradado: arriba", "Degradado: abajo")):
                    ui.color_input(etiqueta, value=fondo["degradado"][i],
                                   on_change=lambda e, i=i: fondo["degradado"].__setitem__(i, e.value)).props(
                        "outlined dense").classes("w-44")  # fmt: skip

    async def _subir_fondo(self, e: events.UploadEventArguments) -> None:
        fondos_usuario_dir().mkdir(parents=True, exist_ok=True)
        temporal = fondos_usuario_dir() / f"_subida_{self.id}"
        await e.file.save(temporal)
        try:
            destino = await run.io_bound(preparar_fondo, temporal, fondos_usuario_dir() / f"{self.id}.png")
        except ErrorMotor as error:
            ui.notify(f"{error.mensaje} {error.ayuda or ''}", type="negative", multi_line=True)
            return
        finally:
            temporal.unlink(missing_ok=True)
        if destino is None:
            return
        self.selector_fondo.options = _fondos(destino.stem)
        self.selector_fondo.update()
        self.t["fondo"].update({"tipo": "imagen", "imagen": destino.stem})
        ui.notify("Foto lista como fondo. Guarda para verla en la vista previa.", type="positive")

    def _hoja(self) -> None:
        hoja = self.t["hoja"]
        with (
            ui.card().classes("tpi-hoja w-full p-5 gap-3").bind_visibility_from(self.t, "marco", value="hoja")
        ):
            ui.label("La hoja").classes("tpi-titulo")
            with ui.row().classes("gap-3 items-center"):
                ui.input("Encabezado").props("outlined dense").bind_value(hoja, "encabezado")
                ui.input("Arriba a la izquierda").props("outlined dense").bind_value(hoja, "etiqueta")
                ui.input("Pastilla").props("outlined dense").bind_value(hoja, "fecha")
                _color(hoja, "color", "Color de la hoja")
                ui.switch("Cuadrícula").bind_value(hoja, "cuadricula")
            ui.label("Deja un texto vacío para que no aparezca.").classes("tpi-ayuda")

    def _nota(self) -> None:
        nota = self.t["nota"]
        with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
            ui.label("Nota al margen").classes("tpi-titulo")
            with ui.row().classes("gap-3 items-center"):
                ui.select(
                    {
                        "materia": "Color de la materia",
                        "titulos": "Color de los títulos",
                        "acento": "Color de acento",
                    },
                    label="Color",
                ).props("outlined dense").classes("w-56").bind_value(nota, "color")
                ui.select(
                    {"texto": "Letra de las explicaciones", "titulos": "Letra de los títulos"}, label="Letra"
                ).props("outlined dense").classes("w-64").bind_value(nota, "rol")
                ui.number("Tamaño", min=0.5, max=2.5, step=0.1).props("outlined dense").classes(
                    "w-32"
                ).bind_value(nota, "escala")
            ui.label("El texto pequeño que acompaña cada fórmula («Despejamos t»).").classes("tpi-ayuda")

    def _subtitulos(self) -> None:
        s = self.t["subtitulos"]
        with ui.card().classes("tpi-hoja w-full p-5 gap-3"):
            ui.label("Subtítulos").classes("tpi-titulo")
            with ui.row().classes("gap-3 items-center"):
                ui.select(_opciones(PARA_SUBTITULOS, s["fuente"]), label="Letra").props(
                    "outlined dense"
                ).classes("w-52").bind_value(s, "fuente")
                _color(s, "color", "Color")
                _color(s, "color_activo", "Palabra que suena")
                ui.switch("Pintar la palabra que suena").bind_value(s, "resaltar")
                ui.switch("MAYÚSCULAS").bind_value(s, "mayusculas")
            with ui.row().classes("gap-8 items-center w-full"):
                with ui.column().classes("flex-1 gap-0"):
                    ui.label("Tamaño").classes("tpi-ayuda")
                    ui.slider(min=60, max=150, step=2).props("label").bind_value(s, "tamano")
                with ui.column().classes("flex-1 gap-0"):
                    ui.label("Altura (más a la derecha = más abajo)").classes("tpi-ayuda")
                    ui.slider(min=0.5, max=0.9, step=0.01).props("label").bind_value(s, "posicion_y")
                with ui.column().classes("flex-1 gap-0"):
                    ui.label("Palabras por pantalla").classes("tpi-ayuda")
                    ui.slider(min=1, max=5, step=1).props("label markers").bind_value(s, "max_palabras")

    async def guardar_y_ver(self) -> None:
        self.t["materias"] = {m: self.etiquetas["color"] for m in ("matematica", "fisica", "ingenieria")}
        try:
            tema = Tema.model_validate(self.t)
        except ValidationError as e:
            detalle = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
            ui.notify(f"Hay un valor no válido: {detalle}", type="negative", multi_line=True)
            return
        guardar_tema(self.id, tema)
        ui.notify("Estilo guardado", type="positive")
        await generar_vista(self.id, self.cuadros, self.estado)


def registrar() -> None:
    @ui.page("/estilos", title="Estilos · Tu Profe Industrial")
    def pagina() -> None:
        with marco("/estilos"):
            titulo_seccion(
                None,
                "Estilos",
                "Cómo se ven tus videos. Duplica uno para cambiar colores, letras o el fondo.",
            )
            lista_de_temas()

    @ui.page("/estilos/editar", title="Editar estilo · Tu Profe Industrial")
    def editar(tema: str = "") -> None:
        with marco("/estilos"):
            valido = bool(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", tema))  # nunca una ruta («../…»)
            if not valido or not (temas_usuario_dir() / f"{tema}.yaml").exists():
                ui.label("Ese estilo no existe o no es tuyo (los incluidos se duplican antes de editarlos).")
                ui.button("Volver a Estilos", on_click=lambda: ui.navigate.to("/estilos"))
                return
            titulo_seccion(
                None, "Editar estilo", "Cambia lo que quieras y presiona «Guardar y ver vista previa»."
            )
            try:
                editor = EditorTema(tema)
            except ErrorMotor as e:  # un tema dañado a mano: se explica en vez de mostrar un error técnico
                ui.label(e.mensaje).style("color:#D32F2F")
                ui.button("Volver a Estilos", on_click=lambda: ui.navigate.to("/estilos"))
                return
            editor.render()
