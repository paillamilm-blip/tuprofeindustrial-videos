"""Ajustes: clave de Gemini, marca, público, voz, estilo, rodaje de cada molde, stickers y diagnóstico.

Todo se guarda en ``mis_ajustes/`` (``marca.yaml``, ``rodaje.yaml``; la clave en ``.env``): los
``.yaml`` que viajan con el motor no se tocan, así actualizar nunca borra lo tuyo.
"""

from __future__ import annotations

import hashlib

import re
from collections.abc import Callable

from nicegui import events, run, ui

from ... import ia
from ...config import cargar_marca, guardar_ajustes_marca
from ...emojis import stickers_dir, stickers_disponibles
from ...entorno import raiz_proyecto
from ...errores import ErrorMotor
from ...moldes import MOLDES, nombre_molde
from ...niveles import NIVELES, PUBLICOS, publico_de
from ...rodaje import NOMBRE_MANDO, QUE_HACE, RECETA_LIBRE, campos_de_receta, guardar_receta
from ...temas import (
    TEMA_DE_ERROR,
    TEMA_DE_PASOS,
    TEMA_POR_MOLDE,
    listar_temas,
)
from ..comun import PIEL, confirmar, url_medio
from ..sugerencia import DIFICULTADES, NOMBRE_MATERIA
from ..tareas import consultar

def _voces_gemini() -> dict[str, str]:
    from ...voz_gemini import VOCES as DE_GEMINI

    return {nombre: f"✨ Gemini · {nombre} ({caracter})" for nombre, caracter in DE_GEMINI.items()}


VOCES = {
    **_voces_gemini(),  # las más naturales: primero
    "es-CL-LorenzoNeural": "🇨🇱 Lorenzo (Chile, hombre)",
    "es-CL-CatalinaNeural": "🇨🇱 Catalina (Chile, mujer)",
    "es-MX-JorgeNeural": "🇲🇽 Jorge (México, hombre)",
    "es-MX-DaliaNeural": "🇲🇽 Dalia (México, mujer)",
    "es-AR-TomasNeural": "🇦🇷 Tomás (Argentina, hombre)",
    "es-AR-ElenaNeural": "🇦🇷 Elena (Argentina, mujer)",
    "es-CO-GonzaloNeural": "🇨🇴 Gonzalo (Colombia, hombre)",
    "es-CO-SalomeNeural": "🇨🇴 Salomé (Colombia, mujer)",
    "es-PE-AlexNeural": "🇵🇪 Alex (Perú, hombre)",
    "es-PE-CamilaNeural": "🇵🇪 Camila (Perú, mujer)",
    "es-ES-AlvaroNeural": "🇪🇸 Álvaro (España, hombre)",
    "es-ES-ElviraNeural": "🇪🇸 Elvira (España, mujer)",
}
MUESTRA = "Hola, soy la voz de Tu Profe Industrial. Hoy resolvemos un ejercicio paso a paso."


def _tarjeta(titulo: str, ayuda: str) -> ui.card:
    tarjeta = ui.card().classes("tpi-hoja w-full p-5 gap-3")
    with tarjeta:
        ui.label(titulo).classes("tpi-titulo text-base")
        ui.label(ayuda).classes("tpi-ayuda -mt-2")
    return tarjeta


def _generar_muestra(voz: str, velocidad: str, tono: str = "+0Hz"):
    from ...voz_gemini import es_voz_de_gemini

    if es_voz_de_gemini(voz):
        return _muestra_gemini(voz, velocidad)
    import edge_tts

    destino = (
        raiz_proyecto() / "salida" / "_panel" / "voces"
        / f"{voz}_{velocidad.replace('%', '')}_{tono.replace('Hz', '')}.mp3"
    )
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        edge_tts.Communicate(MUESTRA, voz, rate=velocidad, pitch=tono).save_sync(str(destino))
    except Exception as e:  # sin internet, voz inexistente…
        destino.unlink(missing_ok=True)
        raise ErrorMotor("No pude generar la muestra de voz.", ayuda="Revisa tu conexión a internet.") from e
    return destino


def _muestra_gemini(voz: str, velocidad: str):
    from ...voz_gemini import estilo_con_ritmo, sintetizar

    estilo = estilo_con_ritmo(cargar_marca().voz.estilo, velocidad)
    huella = hashlib.sha1(estilo.encode("utf-8")).hexdigest()[:8]
    destino = raiz_proyecto() / "salida" / "_panel" / "voces" / f"gemini_{voz}_{huella}.wav"
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(sintetizar(MUESTRA, voz, estilo))  # sus errores ya vienen explicados
    return destino


def _proveedor(voz: str) -> str:
    from ...voz_gemini import es_voz_de_gemini

    return "gemini" if es_voz_de_gemini(voz) else "edge"


def _seccion_clave() -> None:
    with _tarjeta(
        "Clave de Gemini (IA)", "Para «Escribir con IA» y el kit de publicación. Queda solo en este Mac."
    ):
        estado = ui.label("")

        def refrescar() -> None:
            hay = ia.obtener_clave() is not None
            estado.text = "✅ Clave configurada" if hay else "⚠️ Sin clave: la IA no funcionará"
            estado.style(f"color:{PIEL['exito'] if hay else PIEL['aviso']}")

        refrescar()
        with ui.row().classes("w-full items-center gap-3"):
            campo = (
                ui.input("Pega tu clave nueva", password=True, password_toggle_button=True)
                .props("outlined dense")
                .classes("w-96")
            )

            async def guardar() -> None:
                clave = (campo.value or "").strip()
                if not clave:
                    ui.notify("Pega la clave primero.", type="warning")
                    return
                try:
                    await run.io_bound(ia.probar_clave, clave)
                    ia.guardar_clave(clave)
                except ErrorMotor as e:
                    ui.notify(f"{e.mensaje} {e.ayuda or ''}", type="negative", multi_line=True)
                    return
                campo.value = ""
                refrescar()
                ui.notify("Clave probada y guardada.", type="positive")

            ui.button("Probar y guardar", icon="key", on_click=guardar)
        ui.link("Crear una clave gratis en Google AI Studio", ia.URL_CLAVE, new_tab=True)
        ui.label("Nunca pegues tu clave en un chat ni la compartas.").classes("tpi-ayuda")


@ui.refreshable
def _seccion_marca() -> None:
    marca = cargar_marca()
    stickers = {"": "Engranaje del motor", **{nombre: nombre for nombre in stickers_disponibles()}}
    if marca.cierre.emoji and marca.cierre.emoji not in stickers:  # un PNG borrado no se esconde
        stickers[marca.cierre.emoji] = f"{marca.cierre.emoji} (falta el PNG)"
    datos = {
        "nombre": marca.nombre,
        "usuario": marca.usuario,
        "texto": marca.cierre.texto,
        "voz": marca.cierre.voz,
        "sticker": marca.cierre.emoji,
    }
    with _tarjeta("Tu marca", "Aparece en el cierre de cada video."):
        with ui.row().classes("w-full gap-3"):
            ui.input("Nombre").props("outlined dense").classes("flex-1").bind_value(datos, "nombre")
            ui.input("Usuario (@)").props("outlined dense").classes("flex-1").bind_value(datos, "usuario")
        ui.input("Frase de cierre (se ve)").props("outlined dense").classes("w-full").bind_value(
            datos, "texto"
        )
        ui.input("Frase de cierre (se escucha)").props("outlined dense").classes("w-full").bind_value(
            datos, "voz"
        )
        ui.select(stickers, label="Tu logo").props("outlined dense").classes("w-full").bind_value(
            datos, "sticker"
        )
        ui.label(
            "Va arriba, en la franja de la cabecera, y al final de cada video. Súbelo en Tus stickers."
        ).classes("tpi-ayuda -mt-2")

        def guardar() -> None:
            try:
                guardar_ajustes_marca({"nombre": datos["nombre"].strip(), "usuario": datos["usuario"].strip(),
                                       "cierre": {"texto": datos["texto"].strip(), "voz": datos["voz"].strip(),
                                                  "emoji": datos["sticker"] or ""}})  # fmt: skip
            except ErrorMotor as e:
                ui.notify(e.mensaje, type="negative", multi_line=True)
                return
            ui.notify("Marca guardada.", type="positive")

        ui.button("Guardar marca", icon="save", on_click=guardar).props("outline")


@ui.refreshable
def _seccion_publico() -> None:
    """Su público de siempre: la tarjeta de cada video lo ofrece como punto de partida, no como orden."""
    marca = cargar_marca()
    datos = {
        "materia": marca.publico.materia,
        "nivel": marca.publico.nivel,
        "dificultad": marca.publico.dificultad,
    }
    with _tarjeta(
        "Tu público",
        "La materia, el nivel (enseñanza media o universidad de ingeniería) y la dificultad de siempre.",
    ):
        ui.select(
            {"": "Que lo decida la IA", **NOMBRE_MATERIA}, label="Materia"
        ).props("outlined dense").classes("w-full").bind_value(datos, "materia")
        niveles = {"": "Que lo deduzca la IA"}
        niveles |= {n: f"{n} · {PUBLICOS[publico_de(n)]}" for n in NIVELES}
        if datos["nivel"] and datos["nivel"] not in niveles:  # un nivel antiguo escrito a mano se conserva
            niveles[datos["nivel"]] = f"{datos['nivel']} (escrito a mano)"
        ui.select(niveles, label="Nivel").props("outlined dense").classes("w-full").bind_value(datos, "nivel")
        ui.select(
            {"": "Que la IA reparta las 3", **DIFICULTADES}, label="Dificultad"
        ).props("outlined dense").classes("w-full").bind_value(datos, "dificultad")
        ui.label("Si lo dejas vacío, la IA lo deduce de tu frase. En cada video lo puedes cambiar.").classes(
            "tpi-ayuda -mt-2"
        )

        def guardar() -> None:
            try:
                guardar_ajustes_marca(
                    {
                        "publico": {
                            "materia": datos["materia"] or "",
                            "nivel": (datos["nivel"] or "").strip(),
                            "dificultad": datos["dificultad"] or "",
                        }
                    }
                )
            except ErrorMotor as e:
                ui.notify(e.mensaje, type="negative", multi_line=True)
                return
            ui.notify("Público guardado.", type="positive")

        ui.button("Guardar público", icon="save", on_click=guardar).props("outline")


def _seccion_voz() -> None:
    marca = cargar_marca()
    opciones = dict(VOCES)
    if marca.voz.nombre not in opciones:
        opciones[marca.voz.nombre] = marca.voz.nombre
    m = re.fullmatch(r"([+-]\d+)%", marca.voz.velocidad or "+0%")
    t = re.fullmatch(r"([+-]\d+)Hz", marca.voz.tono or "+0Hz")
    datos = {
        "voz": marca.voz.nombre,
        "velocidad": int(m.group(1)) if m else 0,
        "tono": int(t.group(1)) if t else 0,
    }
    with _tarjeta(
        "Voz",
        "La voz de tus videos. Las ✨ Gemini suenan más naturales (usan tu clave de Gemini); "
        "las demás son voces neurales gratis. Todas necesitan internet.",
    ):
        with ui.row().classes("w-full items-center gap-4"):
            ui.select(opciones, label="Voz").props("outlined dense").classes("w-80").bind_value(datos, "voz")
            with ui.column().classes("flex-1 gap-0"):
                ui.label("Velocidad").classes("tpi-ayuda")
                ui.slider(min=-20, max=30, step=5).props("label markers").bind_value(datos, "velocidad")
            with ui.column().classes("flex-1 gap-0"):
                ui.label("Tono (Hz)").classes("tpi-ayuda")
                ui.slider(min=-50, max=50, step=5).props("label markers").bind_value(datos, "tono")
        reproductor = ui.row().classes("w-full")

        def velocidad() -> str:
            return f"{int(datos['velocidad']):+d}%"

        def tono() -> str:
            return f"{int(datos['tono']):+d}Hz"

        async def escuchar() -> None:
            try:
                muestra = await run.io_bound(_generar_muestra, datos["voz"], velocidad(), tono())
            except ErrorMotor as e:
                ui.notify(f"{e.mensaje} {e.ayuda or ''}", type="negative")
                return
            if muestra is None:
                return
            reproductor.clear()
            with reproductor:
                ui.audio(url_medio(muestra), autoplay=True).classes("w-full")

        def guardar() -> None:
            guardar_ajustes_marca(
                {"voz": {"proveedor": _proveedor(datos["voz"]), "nombre": datos["voz"],
                         "velocidad": velocidad(), "tono": tono()}}  # fmt: skip
            )
            ui.notify("Voz guardada para tus próximos videos.", type="positive")

        with ui.row().classes("gap-2"):
            ui.button("Escuchar", icon="play_arrow", on_click=escuchar).props("outline")
            ui.button("Guardar voz", icon="save", on_click=guardar).props("outline")


def _seccion_tema() -> None:
    """Cómo elige el motor el estilo de cada video. Se cambia en QC: acá solo se explica."""
    temas = {i: t.nombre for i, t, _ in listar_temas()}

    def nombre(clave: str) -> str:
        return temas.get(clave, clave)

    with _tarjeta(
        "Estilo de cada video",
        "Todos los videos son de la familia Consola neón: la forma del contenido elige la variante. "
        "Lo ves y lo cambias en un solo lugar: Aprobación de Guiones (QC).",
    ):
        reglas = [
            ("1° El molde", ", ".join(f"{nombre_molde(m)} → {nombre(t)}" for m, t in TEMA_POR_MOLDE.items())),
            ("2° Si corrige un error", nombre(TEMA_DE_ERROR)),
            ("3° Todo lo demás", nombre(TEMA_DE_PASOS)),
        ]
        for regla, detalle in reglas:
            with ui.row().classes("w-full gap-3 no-wrap items-start"):
                ui.label(regla).classes("text-sm font-bold w-44 shrink-0")
                ui.label(detalle).classes("tpi-ayuda")
        with ui.row().classes("items-center gap-4"):
            ui.link("Elegir el estilo de un video (QC)", "/qc")
            ui.link("Ver y personalizar estilos", "/motor")


def filas_de_rodaje(valores: dict[str, str]) -> list[tuple]:
    """Una fila por mando: clave del archivo, nombre, qué hace hoy, sus dos opciones y el activo."""
    filas = []
    for mando, nombre in NOMBRE_MANDO.items():
        activo = valores[mando]
        filas.append((mando, nombre, QUE_HACE[mando][activo], list(QUE_HACE[mando].items()), activo))
    return filas


def resumen_de_receta(clave: str, valores: dict[str, str]) -> str:
    frases = "; ".join(frase for _, _, frase, _, _ in filas_de_rodaje(valores))
    return f"Así se graba «{clave}»: {frases}."


def _seccion_rodaje() -> None:
    opciones = {clave: molde.nombre for clave, molde in MOLDES.items()}
    opciones[RECETA_LIBRE] = "Sin molde"
    estado: dict = {"molde": next(iter(opciones)), "valores": {}}

    def cargar(clave: str) -> None:
        estado["molde"] = clave
        estado["valores"] = campos_de_receta(clave)

    def poner(mando: str, valor: str) -> None:
        estado["valores"][mando] = valor
        mandos.refresh()

    def guardar() -> None:
        try:
            guardar_receta(estado["molde"], estado["valores"])
        except ErrorMotor as e:
            ui.notify(f"{e.mensaje} {e.ayuda or ''}", type="negative", multi_line=True)
            return
        ui.notify("Receta guardada. La usa el próximo video que crees con ese molde.", type="positive")

    @ui.refreshable
    def mandos() -> None:
        for mando, nombre, frase, opciones_mando, activo in filas_de_rodaje(estado["valores"]):
            with ui.row().classes("w-full items-center gap-3 border-t pt-2"):
                ui.label(nombre).classes("text-sm font-bold w-36 shrink-0")
                ui.label(frase).classes("tpi-ayuda flex-1")
                for valor, _ in opciones_mando:
                    ui.button(valor.replace("_", " "), on_click=lambda v=valor, m=mando: poner(m, v)).props(
                        "dense no-caps unelevated" if valor == activo else "dense no-caps outline"
                    )  # fmt: skip
        ui.label(resumen_de_receta(estado["molde"], estado["valores"])).classes(
            "tpi-ayuda w-full rounded border border-dashed p-2"
        )

    cargar(estado["molde"])
    with _tarjeta(
        "Cómo se graba cada molde",
        "Lo que decide el motor al filmar: elige el molde y cambia sus mandos. Nada te bloquea.",
    ):
        ui.select(opciones, value=estado["molde"], label="Molde").props("outlined dense").classes(
            "w-72"
        ).on_value_change(lambda e: (cargar(e.value), mandos.refresh()) if e.value else None)
        mandos()
        with ui.row().classes("w-full items-center gap-3"):
            ui.button("Guardar receta", icon="save", on_click=guardar).props("outline")
            ui.label("mis_ajustes/rodaje.yaml · la tuya gana a la del motor").classes("tpi-ayuda")


def _seccion_stickers(al_subir: Callable[[], None] | None = None) -> None:
    @ui.refreshable
    def galeria() -> None:
        carpeta = stickers_dir()
        archivos = sorted(carpeta.glob("*.png")) if carpeta.exists() else []
        if not archivos:
            ui.label("Todavía no tienes stickers.").classes("tpi-ayuda")
            return
        with ui.row().classes("gap-3"):
            for archivo in archivos:
                with ui.card().classes("p-2 items-center gap-1").props("flat bordered"):
                    ui.image(url_medio(archivo)).classes("w-16 h-16").props("fit=contain")
                    ui.label(archivo.stem).classes("text-xs font-mono")

                    def borrar(a=archivo) -> None:
                        a.unlink(missing_ok=True)
                        galeria.refresh()

                    ui.button(icon="delete", on_click=lambda a=archivo: confirmar(f"¿Borrar el sticker «{a.stem}»?",
                                                                                lambda: borrar(a))).props(
                        "flat round dense color=grey-7")  # fmt: skip

    with _tarjeta(
        "Tus stickers",
        "Imágenes PNG con fondo transparente (tu logo, tu mascota). En el guion: emoji: nombre.",
    ):
        nombre = ui.input("Nombre del sticker", placeholder="mascota").props("outlined dense").classes("w-64")

        async def subir(e: events.UploadEventArguments) -> None:
            base = re.sub(r"[^a-z0-9_]+", "_", (nombre.value or e.file.name.rsplit(".", 1)[0]).lower()).strip(
                "_"
            )
            if not base:
                ui.notify("Escribe un nombre para el sticker.", type="warning")
                return
            stickers_dir().mkdir(parents=True, exist_ok=True)
            await e.file.save(stickers_dir() / f"{base}.png")
            nombre.value = ""
            ui.notify(f"Sticker «{base}» guardado. Úsalo con emoji: {base}", type="positive")
            galeria.refresh()
            if al_subir is not None:
                al_subir()

        ui.upload(label="Subir PNG", auto_upload=True, on_upload=subir).props('accept=".png" flat bordered')
        galeria()


def _seccion_diagnostico() -> None:
    with _tarjeta("Diagnóstico", "Revisa que todo esté instalado (lo mismo que ./tpi doctor)."):
        resultados = ui.column().classes("w-full gap-1")

        async def revisar() -> None:
            resultados.clear()
            with resultados:
                ui.spinner()
            try:  # en un proceso aparte, como ./tpi doctor (no carga Whisper dentro del panel)
                chequeos = (await consultar(["doctor"])).get("chequeos", [])
            except ErrorMotor as e:
                resultados.clear()
                ui.notify(e.mensaje, type="negative")
                return
            resultados.clear()
            iconos = {"ok": "✅", "falla": "❌", "opcional": "➖"}
            with resultados:
                for c in chequeos:
                    ui.label(f"{iconos.get(c['estado'], '•')} {c['nombre']}: {c['detalle']}").classes(
                        "text-sm"
                    )
                    if c.get("ayuda") and c["estado"] != "ok":
                        ui.label(f"   👉 {c['ayuda']}").classes("text-sm").style(
                            f"color:{PIEL['aviso_fuerte']}"
                        )

        ui.button("Revisar ahora", icon="health_and_safety", on_click=revisar).props("outline")


def cuerpo() -> None:
    """Las secciones de ajustes, sin ruta ni título: las pinta igual «Motor visual y ajustes»."""
    with ui.row().classes("w-full gap-6 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-6"):
            _seccion_clave()
            _seccion_voz()
            _seccion_tema()
        with ui.column().classes("flex-1 gap-6"):
            _seccion_marca()
            _seccion_publico()
            _seccion_stickers(_seccion_marca.refresh)
            _seccion_diagnostico()
    _seccion_rodaje()
