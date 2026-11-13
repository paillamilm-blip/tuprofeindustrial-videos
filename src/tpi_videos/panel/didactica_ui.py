"""Las tarjetas «Qué enseña» y «Herramientas de la explicación», iguales en Estudio y en la ficha QC.

Solo dibuja: las decisiones salen de ``didactica.recursos_del_guion`` y el guardado de
``qc.cambiar_recursos`` (que valida y escribe de una vez). El estilo NO se elige acá.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from nicegui import ui

from ..didactica import NOMBRES, RECURSOS, RecursoDidactico
from ..errores import ErrorMotor
from ..guion import INTENCIONES, Contenido, RecursosDidacticos
from . import qc

_ESTADOS = {"sugerido": "Sugerido", "si": "Encendido", "no": "Apagado"}
_EXPLICA = {
    "tabs": "Los números de paso arriba: muestran cuánto falta.",
    "panel": "Abajo quedan las fórmulas correctas que ya se vieron.",
    "mapa_color": "Une cada parte de la fórmula con lo que significa, por color.",
    "micro": "Pequeños movimientos que marcan lo que se está diciendo.",
}


def tarjeta_contenido(contenido: Contenido | None) -> None:
    with ui.column().classes("w-full gap-1"):
        ui.label("Qué enseña").classes("tpi-rotulo")
        if contenido is None:
            ui.label("Ejercicio · estructura de siempre").classes("font-semibold")
            ui.label("Este guion no dice qué enseña: se trata como un ejercicio.").classes("tpi-sobrio text-sm")
            return
        ui.label(" + ".join(INTENCIONES[i] for i in contenido.intenciones)).classes("font-semibold")
        ui.label(contenido.objetivo).classes("text-sm")
        ui.label("Es lo que aprende la persona; no es el molde ni el estilo.").classes("tpi-sobrio text-xs")


def tarjeta_herramientas(ruta: Path, recursos: list[RecursoDidactico], al_guardar: Callable[[], None]) -> None:
    with ui.column().classes("w-full gap-1"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Herramientas de la explicación").classes("tpi-rotulo")
            ui.button("Cambiar", on_click=lambda: _dialogo(ruta, recursos, al_guardar)).props(
                "flat no-caps dense"
            ).classes("tpi-ambar")
        for d in recursos:
            estado = "encendido" if d.activo else "apagado"
            origen = {"guion": "elegido", "contenido": "sugerido", "tema": "del estilo"}[d.origen]
            with ui.row().classes("w-full gap-2 no-wrap items-baseline"):
                ui.label("✓" if d.activo else "–").classes("tpi-verde" if d.activo else "tpi-sobrio")
                with ui.column().classes("gap-0 min-w-0"):
                    ui.label(f"{d.nombre}: {estado} · {origen}").classes("text-sm font-semibold")
                    ui.label(d.razon).classes("tpi-sobrio text-xs")


def _dialogo(ruta: Path, recursos: list[RecursoDidactico], al_guardar: Callable[[], None]) -> None:
    elegidos = {d.clave: ("sugerido" if d.origen != "guion" else ("si" if d.activo else "no")) for d in recursos}
    with ui.dialog() as dialogo, ui.card().props("flat").classes("tpi-consola p-6 gap-4 w-[520px] max-w-[95vw]"):
        ui.label("Herramientas de la explicación").classes("text-lg font-semibold")
        ui.label("Afecta la próxima producción; un lote ya creado no cambia.").classes("tpi-sobrio text-sm")
        for clave in RECURSOS:
            ui.select(_ESTADOS, label=NOMBRES[clave], value=elegidos[clave]).props(
                "outlined dark dense options-dark color=amber"
            ).classes("w-full").bind_value(elegidos, clave).tooltip(_EXPLICA[clave])

        def guardar() -> None:
            valores = {c: (None if v == "sugerido" else v == "si") for c, v in elegidos.items()}
            try:
                qc.cambiar_recursos(ruta, RecursosDidacticos(**valores))
            except ErrorMotor as e:
                ui.notify(f"{e.mensaje} {e.ayuda or ''}".strip(), type="negative", multi_line=True)
                return
            except OSError as e:
                ui.notify(f"No pude guardar el guion: {e}", type="negative")
                return
            dialogo.close()
            ui.notify("Herramientas guardadas: el guion vuelve a «por revisar».", type="positive")
            al_guardar()

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat no-caps")
            ui.button("Guardar", on_click=guardar).props("unelevated no-caps").classes("tpi-boton-principal")
    dialogo.open()
