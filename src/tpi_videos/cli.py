"""Comandos del motor. Se usan desde la carpeta del repo con ``./tpi <comando>``.

./tpi doctor                         ¿está todo instalado?
./tpi ideas "Teorema de Pitágoras"  la IA propone 3 ideas, tú eliges y el motor hace el video completo
./tpi producir "Un bus viaja a…"    guion revisado + video final + kit de publicación, en un comando
./tpi redactar foto.jpg --crear      la IA escribe el guion desde un enunciado (y crea el borrador)
./tpi clave                          guarda tu clave de Gemini
./tpi nuevo mi_ejercicio             crea guiones/mi_ejercicio.yaml desde la plantilla
./tpi revisar guiones/x.yaml         revisa el guion (duración, gancho, frases)
./tpi crear guiones/x.yaml           crea el video final
./tpi crear guiones/x.yaml --borrador    versión rápida para revisar
./tpi crear guiones/x.yaml --tema pizarra_nocturna   con otro estilo visual
./tpi subtitular video.mp4           subtítulos estilo CapCut para cualquier video
./tpi temas                          estilos visuales disponibles
./tpi emojis                         emojis 3D que puedes poner en el guion
./tpi voces                          voces disponibles en español
./tpi panel                          abre el panel de control en el navegador (solo en este Mac)
./tpi icono                          crea el ícono del panel en el Escritorio y te lo muestra en Finder
./tpi publicar salida/x/x.mp4        portada + título, descripción y hashtags para publicar
./tpi vista-previa --tema X          3 cuadros de muestra de un estilo
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import traceback
from pathlib import Path

from rich.console import Console
from rich.table import Table

from . import __version__
from .entorno import silenciar_avisos
from .errores import ErrorMotor

# soft_wrap: nunca cortar rutas ni comandos con saltos de línea (así se copian y pegan bien)
consola = Console(highlight=False, soft_wrap=True)

# Con --progreso-json (lo usa el panel), la salida estándar lleva solo líneas JSON
# ({"etapa": …, "avance": 0–1, "detalle": …}) y los mensajes para personas van a la salida de errores.
_JSON = {"activo": False}


def _emitir(**datos: object) -> None:
    sys.stdout.write(json.dumps(datos, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def _modo_json(args: argparse.Namespace) -> bool:
    if getattr(args, "progreso_json", False) and not _JSON["activo"]:
        _JSON["activo"] = True
        consola.file = sys.stderr
    return _JSON["activo"]


def _progreso_json(etapa: str, avance: float, detalle: str) -> None:
    _emitir(etapa=etapa, avance=avance, detalle=detalle)


def _ruta_amigable(ruta: Path) -> str:
    try:
        return str(ruta.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(ruta)


def _abrir(ruta: Path) -> None:
    comando = ["open", str(ruta)] if platform.system() == "Darwin" else ["xdg-open", str(ruta)]
    try:
        subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def _minutos(segundos: float) -> str:
    m, s = divmod(round(segundos), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def _dividir_voz(valor: str | None) -> tuple[str | None, str | None]:
    """``--voz`` acepta un servicio (edge | gtts | silencio) o el nombre de una voz."""
    from .voces import PROVEEDORES

    if not valor:
        return None, None
    return (valor, None) if valor in PROVEEDORES else ("edge", valor)


# ------------------------------------------------------------------------------------------
# Comandos
# ------------------------------------------------------------------------------------------


def cmd_doctor(args: argparse.Namespace) -> int:
    from dataclasses import asdict

    from .doctor import diagnosticar

    json_activo = _modo_json(args)
    consola.print("[bold]🩺 Diagnóstico del motor de video[/]\n")
    with consola.status("Revisando… (la primera vez puede tardar unos segundos)"):
        chequeos = diagnosticar(probar_red=args.red)
    if json_activo:
        _emitir(etapa="resultado", avance=1.0, chequeos=[asdict(c) for c in chequeos])
    iconos = {"ok": "[green]✅[/]", "falla": "[red]❌[/]", "opcional": "[yellow]➖[/]"}
    for c in chequeos:
        consola.print(f"{iconos[c.estado]} [bold]{c.nombre}[/]: {c.detalle}")
        if c.ayuda and c.estado != "ok":
            consola.print(f"     [yellow]→ {c.ayuda}[/]")
    fallas = [c for c in chequeos if c.estado == "falla"]
    if fallas:
        consola.print(f"\n[red]Hay {len(fallas)} cosa(s) por arreglar.[/] Sigue las flechas amarillas.")
        return 1
    consola.print(
        "\n[green bold]Todo listo para crear videos.[/] Prueba: ./tpi crear guiones/ejemplos/fisica_caida_libre.yaml --borrador"
    )
    return 0


def cmd_nuevo(args: argparse.Namespace) -> int:
    from .entorno import PLANTILLAS_DIR, raiz_proyecto
    from .render import slug

    nombre = slug(args.nombre).replace("-", "_")
    destino = raiz_proyecto() / "guiones" / f"{nombre}.yaml"
    if destino.exists() and not args.forzar:
        raise ErrorMotor(
            f"Ya existe {_ruta_amigable(destino)}.",
            ayuda="Usa otro nombre o agrega --forzar para reemplazarlo.",
        )
    plantilla = (PLANTILLAS_DIR / "guion_base.yaml").read_text(encoding="utf-8")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(plantilla.replace("materia: fisica", f"materia: {args.materia}"), encoding="utf-8")
    consola.print(f"[green]✅ Creado {_ruta_amigable(destino)}[/]")
    consola.print("Siguiente: edítalo con tu ejercicio y luego:")
    consola.print(f"  ./tpi revisar {_ruta_amigable(destino)}")
    consola.print(f"  ./tpi crear {_ruta_amigable(destino)} --borrador")
    return 0


def _mostrar_revision(ruta: str) -> bool:
    from .config import cargar_marca
    from .guion import cargar_guion
    from .revision import revisar

    guion = cargar_guion(ruta)
    rev = revisar(guion, cargar_marca().cierre.voz)
    n = len(guion.pasos)
    consola.print(
        f"[bold]📋 {guion.titulo}[/]  ({guion.etiqueta_materia.lower()}, {n} paso{'' if n == 1 else 's'})"
    )
    color = "green" if 30 <= rev.segundos <= 75 else "yellow"
    consola.print(
        f"[{color}]⏱  Duración estimada: ~{rev.segundos:.0f} s[/] ({rev.palabras} palabras, {rev.bloques} bloques de voz)"
    )
    if not rev.avisos:
        consola.print("[green]✅ Sin observaciones. ¡Buen guion![/]")
        return True
    tabla = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    tabla.add_column("")
    tabla.add_column("Dónde")
    tabla.add_column("Observación")
    for aviso in rev.avisos:
        icono = "⚠️ " if aviso.nivel == "advertencia" else "💡"
        tabla.add_row(icono, aviso.donde, aviso.mensaje)
    consola.print(tabla)
    return True


def cmd_revisar(args: argparse.Namespace) -> int:
    _mostrar_revision(args.guion)
    return 0


def cmd_crear(args: argparse.Namespace) -> int:
    from .render import crear_video

    json_activo = _modo_json(args)

    proveedor, voz = _dividir_voz(args.voz)

    if not getattr(args, "revisado", False):  # redactar ya mostró la revisión
        _mostrar_revision(args.guion)
    calidad = "borrador" if args.borrador else "final"
    consola.print(
        f"\n[bold]🎬 Creando video ({calidad})…[/] la voz se genera con internet; "
        "las animaciones pueden tardar unos minutos.\n"
    )
    resultado = crear_video(
        args.guion,
        calidad=calidad,
        proveedor=proveedor,
        voz=voz,
        velocidad=args.velocidad,
        subtitulos=not args.sin_subtitulos,
        sincronizar=args.sincronizar,
        modelo_whisper=args.modelo,
        carpeta_salida=Path(args.salida) if args.salida else None,
        tema=getattr(args, "tema", None),
        progreso=_progreso_json if json_activo else None,
    )
    if json_activo:
        _emitir(etapa="resultado", avance=1.0, video=resultado.video, srt=resultado.srt, tema=resultado.tema,
                duracion=round(resultado.duracion, 1), segundos=round(resultado.segundos_proceso))  # fmt: skip
    nombres = {"voz": "marcas exactas de la voz", "whisper": "Whisper", "estimado": "tiempos estimados"}
    fuentes = ", ".join(nombres[f] for f in sorted(resultado.fuentes_tiempo)) or "sin subtítulos"
    ruta = _ruta_amigable(resultado.video)
    consola.print(f"\n[green bold]✅ Video listo:[/] {ruta}")
    consola.print(
        f"   Estilo: {resultado.tema} · Duración: {resultado.duracion:.1f} s · "
        f"Proceso: {_minutos(resultado.segundos_proceso)} · Subtítulos: {fuentes}"
    )
    if resultado.srt:
        consola.print(f"   Subtítulos para YouTube: {_ruta_amigable(resultado.srt)}")
    consola.print(f'   Para verlo: [bold]open "{ruta}"[/]')
    if args.abrir:
        _abrir(resultado.video)
    return 0


def cmd_subtitular(args: argparse.Namespace) -> int:
    from .render import subtitular_video

    texto = Path(args.texto).read_text(encoding="utf-8") if args.texto else None
    with consola.status("Escuchando el audio con Whisper y quemando subtítulos…"):
        salida = subtitular_video(
            Path(args.video),
            texto=texto,
            modelo=args.modelo,
            carpeta_salida=Path(args.salida) if args.salida else None,
            tema=args.tema,
        )
    ruta = _ruta_amigable(salida)
    consola.print(f'[green bold]✅ Listo:[/] {ruta}\n   Para verlo: [bold]open "{ruta}"[/]')
    if args.abrir:
        _abrir(salida)
    return 0


def cmd_clave(args: argparse.Namespace) -> int:
    from getpass import getpass

    from .ia import URL_CLAVE, guardar_clave, probar_clave

    consola.print(f"🔑 Crea tu clave gratis en [bold]{URL_CLAVE}[/] (botón «Create API key») y cópiala.")
    clave = getpass("Pega aquí tu clave (no se verá mientras la pegas) y presiona Enter: ").strip()
    if not args.sin_probar:
        with consola.status("Probando la clave con Gemini…"):
            probar_clave(clave)
    ruta = guardar_clave(clave)
    consola.print(
        f"[green]✅ Clave guardada en {ruta.name}[/] (queda solo en este computador; nunca se sube a GitHub)."
    )
    consola.print('Prueba: ./tpi redactar "Una escalera de 5 m se apoya en una pared…" --crear --abrir')
    return 0


def cmd_redactar(args: argparse.Namespace) -> int:
    from .ia import MODELO_POR_DEFECTO
    from .redactor import redactar

    json_activo = _modo_json(args)

    def avisar(mensaje: str, estado=None) -> None:
        if json_activo:
            _emitir(etapa="redactando", avance=0.0, detalle=mensaje)
        if estado is not None:
            estado.update(mensaje)

    with consola.status("Preparando…") as estado:
        resultado = redactar(
            " ".join(args.enunciado),  # sin comillas, la terminal lo separa en palabras
            materia=args.materia,
            nivel=args.nivel,
            modelo=args.modelo or MODELO_POR_DEFECTO,
            nombre=args.nombre,
            forzar=args.forzar,
            revisar_con_ia=not args.sin_revision,
            avisar=lambda mensaje: avisar(mensaje, estado),
        )
    if json_activo:
        _emitir(etapa="guion", avance=1.0, guion=resultado.ruta, supuestos=resultado.supuestos,
                pendientes=resultado.pendientes, revisado_por_ia=resultado.revisado_por_ia)  # fmt: skip
    ruta = _ruta_amigable(resultado.ruta)
    consola.print(f"[green bold]✅ Guion listo:[/] {ruta}")
    if resultado.revisado_por_ia and not resultado.pendientes:
        consola.print("   Fórmulas compiladas y cálculos revisados por la IA: sin observaciones.")
    for supuesto in resultado.supuestos:
        consola.print(f"   [cyan]ℹ Supuesto de la IA:[/] {supuesto}")
    if resultado.pendientes:
        consola.print("[yellow]⚠️  Quedaron observaciones (también están al inicio del archivo):[/]")
        for p in resultado.pendientes:
            consola.print(f"   [yellow]• {p}[/]")
    consola.print()
    _mostrar_revision(str(resultado.ruta))
    consola.print("\n[bold]⚠️  Revisa la matemática antes de publicar:[/] la IA puede equivocarse.")
    if args.crear:
        consola.print()
        cmd_crear(
            argparse.Namespace(
                guion=str(resultado.ruta), borrador=True, voz=None, velocidad=None, sin_subtitulos=False,
                sincronizar="auto", modelo="base", salida=None, abrir=args.abrir, revisado=True, tema=None,
                progreso_json=json_activo,
            )
        )  # fmt: skip
    else:
        consola.print(f"   Para corregirlo: open -e {ruta}")
        consola.print(f"   Para verlo:      ./tpi crear {ruta} --borrador --abrir")
    return 0


# ------------------------------------------------------------------------------------------
# Ideas de video y producción completa (de la idea al video listo para publicar)
# ------------------------------------------------------------------------------------------


def _producir(
    args: argparse.Namespace,
    valor: str,
    materia: str | None = None,
    nivel: str | None = None,
    gancho: str | None = None,
    titulo: str | None = None,
    segundos: int | None = None,
) -> int:
    """Guion revisado + video + kit de publicación en un solo paso, y lo muestra."""
    from .ia import MODELO_POR_DEFECTO
    from .ideas import producir
    from .redactor import promesa_incumplida

    json_activo = _modo_json(args)
    proveedor, voz = _dividir_voz(getattr(args, "voz", None))

    def avisar(mensaje: str) -> None:
        if json_activo:
            _emitir(etapa="redactando", avance=0.0, detalle=mensaje)
        else:
            consola.print(f"[dim]→ {mensaje}[/dim]")

    def progreso(etapa: str, avance: float, detalle: str) -> None:
        _progreso_json(etapa, avance, detalle)

    prometido = segundos if segundos is not None else getattr(args, "segundos", None)
    resultado = producir(
        valor,
        materia=materia if materia is not None else getattr(args, "materia", None),
        nivel=nivel if nivel is not None else getattr(args, "nivel", None),
        modelo=getattr(args, "modelo", None) or MODELO_POR_DEFECTO,
        nombre=getattr(args, "nombre", None),
        forzar=getattr(args, "forzar", False),
        calidad="borrador" if getattr(args, "borrador", False) else "final",
        tema=getattr(args, "estilo", None),
        proveedor=proveedor,
        voz=voz,
        velocidad=getattr(args, "velocidad", None),
        subtitulos=not getattr(args, "sin_subtitulos", False),
        sincronizar=getattr(args, "sincronizar", "auto"),
        revisar_con_ia=not getattr(args, "sin_revision", False),
        con_kit=not getattr(args, "sin_kit", False),
        gancho=gancho if gancho is not None else getattr(args, "gancho", None),
        titulo=titulo if titulo is not None else getattr(args, "titulo", None),
        segundos=prometido,
        avisar=avisar,
        progreso=progreso if json_activo else None,
    )

    if json_activo:
        _emitir(
            etapa="resultado", avance=1.0,
            guion=resultado.ruta_guion, video=resultado.video, srt=resultado.srt,
            tema=resultado.tema, duracion=round(resultado.duracion, 1), prometido=prometido,
            portada=resultado.portada, publicacion=resultado.publicacion,
            supuestos=resultado.redaccion.supuestos, pendientes=resultado.redaccion.pendientes,
            revisado_por_ia=resultado.redaccion.revisado_por_ia,
        )  # fmt: skip
    rutas = {"guion": resultado.ruta_guion, "video": resultado.video, "portada": resultado.portada,
             "kit": resultado.publicacion}  # fmt: skip
    nombres = {"voz": "marcas exactas de la voz", "whisper": "Whisper", "estimado": "tiempos estimados"}
    fuentes = ", ".join(nombres[f] for f in sorted(resultado.fuentes_tiempo)) or "sin subtítulos"
    consola.print()
    for etiqueta, ruta in rutas.items():
        if ruta is not None:
            consola.print(f"[green]✅[/] [bold]{etiqueta.capitalize()}:[/] {_ruta_amigable(Path(ruta))}")
    consola.print(
        f"   Estilo: {resultado.tema} · Duración: {resultado.duracion:.1f} s · Subtítulos: {fuentes}"
    )
    if prometido:
        if promesa_incumplida(resultado.duracion, prometido):
            consola.print(
                f"   [yellow]⚠️ La idea prometió ≈{prometido} s y el video duró "
                f"{resultado.duracion:.1f} s: acorta pasos en el guion.[/]"
            )
        else:
            consola.print(f"   [dim]Prometido en la idea: ≈{prometido} s · cumplido.[/]")
    for supuesto in resultado.redaccion.supuestos:
        consola.print(f"   [cyan]ℹ Supuesto de la IA:[/] {supuesto}")
    for pendiente in resultado.redaccion.pendientes:
        consola.print(f"   [yellow]⚠️  Por revisar:[/] {pendiente}")
    if resultado.kit_aviso:
        consola.print(f"   [yellow]{resultado.kit_aviso}[/]")
    consola.print(f'   Para verlo: [bold]open "{_ruta_amigable(resultado.video)}"[/]')
    if resultado.publicacion:
        consola.print(f'   Para copiar los textos: open -e "{_ruta_amigable(resultado.publicacion)}"')
    if getattr(args, "abrir", False):
        _abrir(resultado.video)
    return 0


def cmd_producir(args: argparse.Namespace) -> int:
    _modo_json(args)
    consola.print(
        "[bold]🎬 Video completo[/] (guion revisado por IA → video final → kit de publicación).\n"
        "   Dura varios minutos: la animación se crea ahora, no hay que repetirla después.\n"
    )
    # sin comillas: la terminal separa el enunciado en palabras
    return _producir(args, " ".join(args.enunciado))


def _mostrar_ideas(ideas: list, tema: str | None) -> None:
    from .ideas import ANGULOS

    consola.print(f"\n[bold]🎬 3 ideas[/]{' para «' + tema + '»' if tema else ''}:\n")
    for n, idea in enumerate(ideas, 1):
        consola.print(f" [bold cyan]{n}[/]  [bold]{idea.emoji} {ANGULOS[idea.angulo]}[/] · {idea.titulo}")
        consola.print(f"    [bold]Gancho:[/] {idea.gancho}")
        consola.print(f"    [bold]El ejercicio:[/] {idea.enunciado}")
        consola.print(
            f"    [bold]Nivel:[/] {idea.nivel} · {idea.materia.upper()} · [yellow]≈{idea.segundos} s[/]"
        )
        consola.print(f"    [dim]{idea.porque}[/]\n")


def cmd_ideas(args: argparse.Namespace) -> int:
    from .ia import MODELO_POR_DEFECTO
    from .ideas import proponer_ideas

    json_activo = _modo_json(args)
    tema = " ".join(args.tema).strip() or None
    modelo = args.modelo or MODELO_POR_DEFECTO
    evitadas: list[str] = list(args.evitar or [])
    eleccion = args.elegir

    while True:
        ideas = proponer_ideas(
            tema=tema,
            materia=args.materia,
            nivel=args.nivel,
            modelo=modelo,
            evitar=evitadas,
            avisar=lambda m: _emitir(etapa="redactando", avance=0.0, detalle=m)
            if json_activo
            else consola.print(f"[dim]→ {m}[/dim]"),
        )  # fmt: skip
        if json_activo:
            # El panel muestra las tarjetas y sigue con `tpi producir`: sin preguntar, termina aquí.
            _emitir(
                etapa="resultado", avance=1.0, tema=tema or "",
                ideas=[i.model_dump() for i in ideas],
            )  # fmt: skip
            if eleccion is None:
                return 0
        else:
            _mostrar_ideas(ideas, tema)
            if args.sin_video:
                return 0
        if eleccion is None:
            try:
                respuesta = input("\nElige 1, 2 o 3 · [Enter] otras 3 ideas · [q] salir: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                consola.print("\n[yellow]Cancelado.[/]")
                return 130
            if respuesta in ("q", "salir", "s"):
                consola.print("Cancelado: ninguna idea te convenció.")
                return 130
            if respuesta == "":
                evitadas += [i.titulo for i in ideas]
                continue
            if not respuesta.isdigit() or not 1 <= int(respuesta) <= len(ideas):
                consola.print("[yellow]Escribe 1, 2 o 3 (Enter para ver otras 3, q para salir).[/]")
                continue
            eleccion = int(respuesta)
        if not 1 <= eleccion <= len(ideas):
            raise ErrorMotor(
                f"La idea {eleccion} no está en la lista (hay {len(ideas)}).",
                ayuda='Ej. ./tpi ideas "Porcentajes" --elegir 2',
            )
        elegida = ideas[eleccion - 1]
        consola.print(f"\n[bold]🎬 Voy con «{elegida.titulo}»[/] ({elegida.emoji})\n")
        return _producir(
            args,
            elegida.enunciado,
            materia=args.materia,
            nivel=elegida.nivel,
            gancho=elegida.gancho,
            titulo=elegida.titulo,
            segundos=elegida.segundos,
        )


def _mostrar_lote(items: list, tema: str | None) -> None:
    """La tabla del lote: qué salió, qué quedó con avisos y qué falló (con su motivo)."""
    from .ideas import ANGULOS

    consola.print(f"\n[bold]🎬 Lote[/]{' de «' + tema + '»' if tema else ''}: "
                  f"{sum(i.ok for i in items)} de {len(items)} video(s) listos.\n")  # fmt: skip
    for n, item in enumerate(items, 1):
        angulo = ANGULOS.get(item.idea.angulo, item.idea.angulo)
        guion = f"{item.idea.emoji} {angulo} · {item.idea.titulo}".strip()
        if not item.ok:
            consola.print(f" [bold]{n}[/]  [red]❌[/] {guion}")
            consola.print(f"    [red]{item.error}[/]")
            if item.ayuda:
                consola.print(f"    [dim]{item.ayuda}[/]")
            continue
        estado = "[green]✅[/]"
        if item.promesa_incumplida:
            estado = "[yellow]⚠️[/]"
        consola.print(f" [bold]{n}[/]  {estado} {guion}")
        consola.print(
            f"    [bold]Video:[/] {_ruta_amigable(Path(item.video))} · {item.duracion:.1f} s "
            f"(prometidos ≈{item.idea.segundos} s)"
        )
        if item.portada:
            consola.print(f"    [dim]Kit:[/] {_ruta_amigable(Path(item.publicacion))}")
        for pendiente in item.pendientes:
            consola.print(f"    [yellow]⚠️  Por revisar:[/] {pendiente}")
    faltan = [f"{n}. {item.idea.titulo}" for n, item in enumerate(items, 1) if not item.ok]
    if faltan:
        consola.print(
            "\n[yellow]Los que faltan quedan con su tarjeta en el panel[/] (Crear → Ideas → «Hacer este "
            'video»), o en la terminal con el enunciado: ./tpi producir "…"'
        )
    consola.print()


def cmd_lote(args: argparse.Namespace) -> int:
    """De un tema, los 3 videos de una pasada: guion revisado + video final + kit de cada idea."""
    from .ia import MODELO_POR_DEFECTO
    from .ideas import proponer_ideas
    from .lote import ideas_desde_json, producir_lote

    json_activo = _modo_json(args)
    proveedor, voz = _dividir_voz(args.voz)
    modelo = args.modelo or MODELO_POR_DEFECTO
    tema = " ".join(args.tema).strip() or None

    def avisar(mensaje: str) -> None:
        if json_activo:
            _emitir(etapa="redactando", avance=0.0, detalle=mensaje)
        else:
            consola.print(f"[dim]→ {mensaje}[/dim]")

    if args.ideas_json:
        ideas = ideas_desde_json(args.ideas_json)
    else:
        if not tema:
            raise ErrorMotor(
                "El lote necesita el tema.",
                ayuda='Ej. ./tpi lote "Porcentajes"   (o usa el botón «Hacer los 3 videos» del panel)',
            )
        ideas = proponer_ideas(
            tema=tema, materia=args.materia, nivel=args.nivel, modelo=modelo,
            evitar=list(args.evitar or []), avisar=avisar,
        )  # fmt: skip

    if not json_activo:
        consola.print(
            f"\n[bold]📦 Lote de {len(ideas)} videos[/] · de uno en uno, unos {len(ideas) * 3} minutos.\n"
            "   Si una idea falla el lote sigue con las otras; lo que salga queda en salida/."
        )

    items = producir_lote(
        ideas,
        materia=args.materia,
        nivel=args.nivel,
        modelo=modelo,
        calidad="borrador" if args.borrador else "final",
        estilo=args.estilo,
        proveedor=proveedor,
        voz=voz,
        velocidad=args.velocidad,
        subtitulos=not args.sin_subtitulos,
        sincronizar=args.sincronizar,
        revisar_con_ia=not args.sin_revision,
        con_kit=not args.sin_kit,
        espera=args.espera,
        avisar=avisar,
        progreso=_progreso_json if json_activo else None,
    )

    if json_activo:
        # Sale 0 aunque fallen ideas: el panel muestra esta tabla con sus motivos, no un error genérico.
        _emitir(etapa="resultado", avance=1.0, tema=tema or "", lote=[i.como_dict() for i in items])
    _mostrar_lote(items, tema)
    if args.abrir:
        for item in items:
            if item.ok:
                _abrir(Path(item.video))
    return 0


def cmd_temas(args: argparse.Namespace) -> int:
    from .config import cargar_marca
    from .temas import listar_temas, temas_usuario_dir

    actual = cargar_marca().tema
    tabla = Table("Tema (para --tema)", "Nombre", "Descripción", header_style="bold")
    for identificador, tema, propio in listar_temas():
        marca = " ⭐" if identificador == actual else ""
        origen = " (tuyo)" if propio else ""
        estilo = "bold green" if identificador == actual else ""
        tabla.add_row(f"{identificador}{marca}", f"{tema.nombre}{origen}", tema.descripcion, style=estilo)
    consola.print(tabla)
    consola.print("⭐ = el que se usa por defecto (cámbialo con «tema:» en marca.yaml).")
    consola.print("Para un solo video: ./tpi crear guiones/x.yaml --tema pizarra_nocturna")
    consola.print("   o escribe «tema: pizarra_nocturna» en el guion.")
    consola.print(f"Tus temas propios se guardan en {_ruta_amigable(temas_usuario_dir())}/")
    return 0


def cmd_emojis(args: argparse.Namespace) -> int:
    from .emojis import EMOJIS, stickers_dir

    columnas = 4
    tabla = Table(*(["Emoji", "Nombre"] * columnas), header_style="bold", box=None, padding=(0, 1))
    items = list(EMOJIS.items())
    for i in range(0, len(items), columnas):
        fila: list[str] = []
        for emoji, nombre in items[i : i + columnas]:
            fila += [emoji, nombre]
        tabla.add_row(*fila)
    consola.print(tabla)
    propios = sorted(p.stem for p in stickers_dir().glob("*.png")) if stickers_dir().exists() else []
    if propios:
        consola.print(f"\n[bold]Tus stickers:[/] {', '.join(propios)}")
    consola.print(
        '\nEn el guion: [bold]emoji: "🤯"[/] o [bold]emoji: explota[/] (en gancho, pasos, resultado, reto…).'
    )
    consola.print(
        f"Tus propias imágenes: guarda un PNG con fondo transparente en {_ruta_amigable(stickers_dir())}/ "
        "y usa su nombre (ej. emoji: mascota)."
    )
    return 0


def cmd_vista_previa(args: argparse.Namespace) -> int:
    from .vista_previa import crear_vista_previa

    json_activo = _modo_json(args)
    # Sin --progreso-json: un aviso que no hace nada (así Manim no dibuja sus barras bajo el «Creando…»)
    progreso = _progreso_json if json_activo else (lambda etapa, avance, detalle: None)
    with consola.status("Creando 3 cuadros de muestra (unos segundos)…"):
        cuadros = crear_vista_previa(args.tema, progreso=progreso, forzar=args.forzar)
    if json_activo:
        _emitir(etapa="resultado", avance=1.0, cuadros=cuadros)
    consola.print("[green bold]✅ Vista previa lista:[/]")
    for cuadro in cuadros:
        consola.print(f'   open "{_ruta_amigable(cuadro)}"')
    if args.abrir:
        for cuadro in cuadros:
            _abrir(cuadro)
    return 0


def cmd_publicar(args: argparse.Namespace) -> int:
    from .publicar import crear_kit

    json_activo = _modo_json(args)

    def avisar(mensaje: str, estado=None) -> None:
        if json_activo:
            _emitir(etapa="publicando", avance=0.0, detalle=mensaje)
        if estado is not None:
            estado.update(mensaje)

    with consola.status("Preparando el kit de publicación…") as estado:
        kit = crear_kit(Path(args.video), con_ia=not args.sin_ia, modelo=args.modelo,
                        avisar=lambda m: avisar(m, estado))  # fmt: skip
    if json_activo:
        _emitir(etapa="resultado", avance=1.0, portada=kit.portada, archivo=kit.archivo, con_ia=kit.con_ia,
                aviso=kit.aviso, **kit.textos.model_dump())  # fmt: skip
    t = kit.textos
    consola.print(
        f"[green bold]✅ Kit de publicación listo[/] ({'escrito con IA' if kit.con_ia else 'plantilla'})"
    )
    if kit.aviso:
        consola.print(f"   [yellow]{kit.aviso}[/]")
    consola.print(f"\n[bold]YouTube Shorts · título:[/] {t.titulo_youtube}\n{t.descripcion_youtube}")
    consola.print(f"\n[bold]TikTok:[/] {t.texto_tiktok}")
    consola.print(f"\n[bold]Instagram Reels:[/] {t.texto_instagram}")
    consola.print(f"\n[bold]Hashtags:[/] {' '.join(t.hashtags)}")
    consola.print(f'\n   Portada: open "{_ruta_amigable(kit.portada)}"')
    consola.print(f'   Todo junto para copiar: open -e "{_ruta_amigable(kit.archivo)}"')
    return 0


def cmd_panel(args: argparse.Namespace) -> int:
    import importlib.util

    if importlib.util.find_spec("nicegui") is None:
        raise ErrorMotor(
            "Falta instalar el panel de control.",
            ayuda="Ejecuta ./scripts/instalar_mac.sh (instala lo nuevo y no toca lo que ya tienes).",
        )
    from .panel import iniciar

    iniciar(puerto=args.puerto, abrir=not args.no_abrir)
    return 0


def cmd_icono(args: argparse.Namespace) -> int:
    from .icono import crear_icono, es_mac

    icono = crear_icono(mostrar=not args.sin_mostrar)
    consola.print(f"[green bold]✅ Ícono listo:[/] {icono.ruta}")
    if icono.con_imagen:
        consola.print("   Es el cuadrado azul con el engranaje amarillo y el ▶ rojo.")
    elif es_mac():
        consola.print("   (No pude ponerle la imagen de tu marca: se ve como un documento de la Terminal.)")
    if icono.mostrado:
        consola.print(
            "   Se abrió una ventana de Finder con el ícono marcado: doble clic en él para abrir el panel."
        )
    else:
        consola.print("   Doble clic en «Panel Tu Profe Industrial» de tu Escritorio para abrir el panel.")
    consola.print("   Tip: arrástralo al lado derecho del Dock (junto a la papelera) y lo abres con un clic.")
    consola.print(
        "   ¿No lo ves en el escritorio? Clic derecho en el escritorio → desmarca «Usar pilas», o en Ajustes "
        "del Sistema → Escritorio y Dock → «Mostrar ítems», marca «En el escritorio»."
    )
    consola.print("   La primera vez el Mac puede preguntar si quieres abrirlo: responde «Abrir».")
    return 0


def cmd_voces(args: argparse.Namespace) -> int:
    from .voces import listar_voces_es

    with consola.status("Consultando voces…"):
        voces = listar_voces_es()
    if not args.todas:
        voces = [
            v for v in voces if v["Locale"] in ("es-CL", "es-MX", "es-AR", "es-CO", "es-PE", "es-US", "es-ES")
        ]
    tabla = Table("Voz (para --voz)", "País", "Género", header_style="bold")
    for v in voces:
        estilo = "bold green" if v["Locale"] == "es-CL" else ""
        tabla.add_row(
            v["ShortName"], v["Locale"], "mujer" if v["Gender"] == "Female" else "hombre", style=estilo
        )
    consola.print(tabla)
    consola.print(
        "Ejemplo: ./tpi crear guiones/x.yaml --voz es-CL-CatalinaNeural   (cámbiala para siempre en marca.yaml)"
    )
    return 0


# ------------------------------------------------------------------------------------------


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tpi",
        description="Motor de video de Tu Profe Industrial: guion YAML → video vertical 9:16 con voz y subtítulos.",
    )
    p.add_argument("--version", action="version", version=f"tpi {__version__}")
    p.add_argument("--debug", action="store_true", help="muestra el detalle técnico si algo falla")
    sub = p.add_subparsers(title="comandos", metavar="<comando>")

    s = sub.add_parser("doctor", help="revisa que todo esté instalado")
    s.add_argument("--red", action="store_true", help="también prueba la voz por internet")
    s.add_argument("--progreso-json", action="store_true", help=argparse.SUPPRESS)  # para el panel
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("nuevo", help="crea un guion nuevo desde la plantilla")
    s.add_argument("nombre", help="nombre del archivo, ej. plano_inclinado")
    s.add_argument("--materia", choices=["matematica", "fisica", "ingenieria"], default="fisica")
    s.add_argument("--forzar", action="store_true", help="reemplaza si ya existe")
    s.set_defaults(func=cmd_nuevo)

    s = sub.add_parser("revisar", help="revisa un guion sin crear el video")
    s.add_argument("guion", help="ruta al .yaml")
    s.set_defaults(func=cmd_revisar)

    s = sub.add_parser("crear", help="crea el video a partir de un guion")
    s.add_argument("guion", help="ruta al .yaml")
    s.add_argument("--borrador", action="store_true", help="calidad baja y rápida para revisar")
    s.add_argument("--voz", help="edge | gtts | silencio, o el nombre de una voz (ver ./tpi voces)")
    s.add_argument("--velocidad", help="velocidad de la voz, ej. +10%% o -5%%")
    s.add_argument("--sin-subtitulos", action="store_true", help="no quemar subtítulos")
    s.add_argument(
        "--sincronizar",
        choices=["auto", "voz", "whisper", "estimado"],
        default="auto",
        help="de dónde salen los tiempos de los subtítulos (auto = el mejor disponible)",
    )
    s.add_argument("--modelo", default="base", help="modelo de Whisper: tiny, base, small, medium")
    s.add_argument("--salida", help="carpeta de salida (por defecto: salida/)")
    s.add_argument("--tema", help="estilo visual, ej. pizarra_nocturna (ver ./tpi temas)")
    s.add_argument("--abrir", action="store_true", help="abre el video al terminar")
    s.add_argument("--progreso-json", action="store_true", help=argparse.SUPPRESS)  # para el panel
    s.set_defaults(func=cmd_crear)

    s = sub.add_parser("subtitular", help="subtítulos estilo CapCut para cualquier video (usa Whisper)")
    s.add_argument("video", help="ruta al video")
    s.add_argument(
        "--texto", help="archivo .txt con el texto exacto que se dice (opcional, mejora la precisión)"
    )
    s.add_argument("--modelo", default="base", help="modelo de Whisper: tiny, base, small, medium")
    s.add_argument("--salida", help="carpeta de salida (por defecto: salida/subtitulados/)")
    s.add_argument("--tema", help="usa la letra y colores de subtítulos de este tema (ver ./tpi temas)")
    s.add_argument("--abrir", action="store_true", help="abre el video al terminar")
    s.set_defaults(func=cmd_subtitular)

    s = sub.add_parser(
        "redactar", help="escribe un guion con IA a partir de un enunciado (texto, foto o PDF)"
    )
    s.add_argument(
        "enunciado",
        nargs="+",
        help="el enunciado (mejor entre comillas) o un archivo .txt, .jpg, .png, .heic o .pdf",
    )
    s.add_argument(
        "--materia", choices=["matematica", "fisica", "ingenieria"], help="opcional: la IA la deduce"
    )
    s.add_argument("--nivel", help='opcional, ej. "1° medio" o "técnico en electricidad"')
    s.add_argument("--nombre", help="nombre del archivo del guion (por defecto, a partir del título)")
    s.add_argument("--modelo", default=None, help="modelo de Gemini (por defecto gemini-3.8-flash)")
    s.add_argument("--forzar", action="store_true", help="reemplaza el guion si ya existe")
    s.add_argument(
        "--sin-revision", action="store_true", help="no pedir la segunda revisión a la IA (más rápido)"
    )
    s.add_argument("--crear", action="store_true", help="crea también el video borrador al terminar")
    s.add_argument("--abrir", action="store_true", help="con --crear: abre el video al terminar")
    s.add_argument("--progreso-json", action="store_true", help=argparse.SUPPRESS)  # para el panel
    s.set_defaults(func=cmd_redactar)

    s = sub.add_parser(
        "ideas",
        help="la IA propone 3 ideas de video sobre un tema; eliges una y el motor hace el video completo",
    )
    s.add_argument("tema", nargs="*", help='de qué trata, ej. "Teorema de Pitágoras" o "ley de Ohm"')
    s.add_argument(
        "--materia", choices=["matematica", "fisica", "ingenieria"], help="opcional: la IA la deduce"
    )
    s.add_argument("--nivel", help='opcional, ej. "2° medio" o "técnico en electricidad"')
    s.add_argument("--modelo", default=None, help="modelo de Gemini (por defecto gemini-3.8-flash)")
    s.add_argument("--evitar", nargs="+", default=[], help="títulos ya vistos, para que salgan otras 3")
    s.add_argument("--elegir", type=int, help="hacer el video de esa idea (1, 2 o 3) sin preguntar")
    s.add_argument("--sin-video", action="store_true", help="solo mostrar las 3 ideas")
    s.add_argument(
        "--sin-revision", action="store_true", help="no pedir la segunda revisión a la IA (más rápido)"
    )
    s.add_argument("--borrador", action="store_true", help="crear un borrador rápido en vez del video final")
    s.add_argument("--estilo", help="estilo visual del video, ej. pizarra_nocturna (ver ./tpi temas)")
    s.add_argument("--voz", help="edge | gtts | silencio, o el nombre de una voz (ver ./tpi voces)")
    s.add_argument("--sin-kit", action="store_true", help="no armar el kit de publicación")
    s.add_argument("--abrir", action="store_true", help="abre el video al terminar")
    s.add_argument("--progreso-json", action="store_true", help=argparse.SUPPRESS)  # para el panel
    s.set_defaults(func=cmd_ideas)

    s = sub.add_parser(
        "producir",
        help="del enunciado al video completo: guion revisado + video final + kit de publicación",
    )
    s.add_argument(
        "enunciado", nargs="+", help="el enunciado (mejor entre comillas), o una ruta .txt/.jpg/.pdf"
    )
    s.add_argument(
        "--materia", choices=["matematica", "fisica", "ingenieria"], help="opcional: la IA la deduce"
    )
    s.add_argument("--nivel", help='opcional, ej. "2° medio" o "técnico en electricidad"')
    s.add_argument(
        "--gancho",
        help="gancho de la idea elegida: el guion lo mantiene en vez de escribir otro (lo usa el panel)",
    )
    s.add_argument(
        "--titulo", help="título de la idea elegida, para que el guion siga esa línea (lo usa el panel)"
    )
    s.add_argument(
        "--segundos",
        type=int,
        help="duración prometida al elegir la idea: el guion se achica para cumplirla (lo usa el panel)",
    )
    s.add_argument("--modelo", default=None, help="modelo de Gemini (por defecto gemini-3.8-flash)")
    s.add_argument("--nombre", help="nombre del archivo del guion")
    s.add_argument("--forzar", action="store_true", help="reemplaza el guion si ya existe")
    s.add_argument(
        "--sin-revision", action="store_true", help="no pedir la segunda revisión a la IA (más rápido)"
    )
    s.add_argument("--borrador", action="store_true", help="crea un borrador rápido en vez del video final")
    s.add_argument("--estilo", help="estilo visual del video, ej. pizarra_nocturna (ver ./tpi temas)")
    s.add_argument("--voz", help="edge | gtts | silencio, o el nombre de una voz (ver ./tpi voces)")
    s.add_argument("--velocidad", help="velocidad de la voz, ej. +10%% o -5%%")
    s.add_argument("--sin-subtitulos", action="store_true", help="no quemar subtítulos")
    s.add_argument(
        "--sincronizar",
        choices=["auto", "voz", "whisper", "estimado"],
        default="auto",
        help="de dónde salen los tiempos de los subtítulos (auto = el mejor disponible)",
    )
    s.add_argument("--sin-kit", action="store_true", help="no armar el kit de publicación")
    s.add_argument("--abrir", action="store_true", help="abre el video al terminar")
    s.add_argument("--progreso-json", action="store_true", help=argparse.SUPPRESS)  # para el panel
    s.set_defaults(func=cmd_producir)

    s = sub.add_parser(
        "lote",
        help="de un tema, los 3 videos de una pasada: guion + video final + kit de cada idea",
    )
    s.add_argument("tema", nargs="*", help='el tema (mejor entre comillas), ej. "Porcentajes"')
    s.add_argument(
        "--materia", choices=["matematica", "fisica", "ingenieria"], help="opcional: la IA la deduce"
    )
    s.add_argument("--nivel", help='opcional, ej. "2° medio" o "técnico en electricidad"')
    s.add_argument("--modelo", default=None, help="modelo de Gemini (por defecto gemini-3.8-flash)")
    s.add_argument("--evitar", nargs="+", default=[], help="títulos ya vistos, para que salgan otras 3")
    s.add_argument(
        "--espera",
        type=float,
        default=60.0,
        help="segundos de espera antes de reintentar una idea si Gemini está saturado (0 = no esperar)",
    )
    s.add_argument("--borrador", action="store_true", help="los 3 como borradores rápidos (en vez del final)")
    s.add_argument("--estilo", help="estilo visual de los videos, ej. pizarra_nocturna (ver ./tpi temas)")
    s.add_argument("--voz", help="edge | gtts | silencio, o el nombre de una voz (ver ./tpi voces)")
    s.add_argument("--velocidad", help="velocidad de la voz, ej. +10%% o -5%%")
    s.add_argument("--sin-subtitulos", action="store_true", help="no quemar subtítulos")
    s.add_argument(
        "--sincronizar",
        choices=["auto", "voz", "whisper", "estimado"],
        default="auto",
        help="de dónde salen los tiempos de los subtítulos (auto = el mejor disponible)",
    )
    s.add_argument("--sin-revision", action="store_true", help="no pedir la segunda revisión a la IA")
    s.add_argument("--sin-kit", action="store_true", help="no armar el kit de publicación")
    s.add_argument("--abrir", action="store_true", help="abre los videos al terminar")
    s.add_argument("--ideas-json", help=argparse.SUPPRESS)  # el panel ya tiene las 3 ideas en pantalla
    s.add_argument("--progreso-json", action="store_true", help=argparse.SUPPRESS)  # para el panel
    s.set_defaults(func=cmd_lote)

    s = sub.add_parser("clave", help="guarda tu clave de Gemini (para redactar con IA)")
    s.add_argument("--sin-probar", action="store_true", help="guardar sin probarla por internet")
    s.set_defaults(func=cmd_clave)

    s = sub.add_parser("voces", help="lista las voces en español")
    s.add_argument("--todas", action="store_true", help="todos los países de habla hispana")
    s.set_defaults(func=cmd_voces)

    s = sub.add_parser("temas", help="lista los estilos visuales (Hoja de desarrollo, Pizarra nocturna…)")
    s.set_defaults(func=cmd_temas)

    s = sub.add_parser("emojis", help="lista los emojis 3D que puedes usar en los guiones")
    s.set_defaults(func=cmd_emojis)

    s = sub.add_parser("panel", help="abre el panel de control en el navegador (solo en este Mac)")
    s.add_argument("--puerto", type=int, default=8765, help="puerto local (por defecto 8765)")
    s.add_argument("--no-abrir", action="store_true", help="no abrir el navegador automáticamente")
    s.set_defaults(func=cmd_panel)

    s = sub.add_parser("icono", help="crea el ícono del panel en el Escritorio y te lo muestra en Finder")
    s.add_argument("--sin-mostrar", action="store_true", help="no abrir Finder (lo usa el instalador)")
    s.set_defaults(func=cmd_icono)

    s = sub.add_parser("publicar", help="kit para publicar: portada + título, descripción y hashtags")
    s.add_argument("video", help="el video (.mp4), su carpeta en salida/ o el guion (.yaml)")
    s.add_argument("--sin-ia", action="store_true", help="textos con plantilla, sin usar Gemini")
    s.add_argument("--modelo", default=None, help="modelo de Gemini (por defecto gemini-3.8-flash)")
    s.add_argument("--progreso-json", action="store_true", help=argparse.SUPPRESS)
    s.set_defaults(func=cmd_publicar)

    s = sub.add_parser("vista-previa", help="3 cuadros de muestra de un estilo (unos segundos)")
    s.add_argument("--tema", help="estilo (por defecto, el de marca.yaml)")
    s.add_argument("--forzar", action="store_true", help="crearla de nuevo aunque no haya cambios")
    s.add_argument("--abrir", action="store_true", help="abre las imágenes al terminar")
    s.add_argument("--progreso-json", action="store_true", help=argparse.SUPPRESS)
    s.set_defaults(func=cmd_vista_previa)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    silenciar_avisos()  # antes de importar Manim: evita avisos técnicos que no aportan
    try:
        return int(args.func(args) or 0)
    except ErrorMotor as e:
        if _JSON["activo"]:
            _emitir(etapa="error", mensaje=e.mensaje, ayuda=e.ayuda)
        consola.print(f"\n[bold red]✖ {e.mensaje}[/]")
        if e.ayuda:
            consola.print(f"[yellow]→ {e.ayuda}[/]")
        return 1
    except KeyboardInterrupt:
        consola.print("\n[yellow]Cancelado.[/]")
        return 130
    except Exception as e:  # error inesperado: mensaje corto y, con --debug, el detalle
        if _JSON["activo"]:
            _emitir(
                etapa="error", mensaje=f"Error inesperado: {e}", ayuda="Repite; si sigue, avísale a Kiro."
            )
        if args.debug:
            traceback.print_exc()
        consola.print(f"\n[bold red]✖ Error inesperado: {e}[/]")
        consola.print(
            "[yellow]→ Vuelve a ejecutar con --debug (ej. ./tpi --debug crear …) y comparte el mensaje.[/]"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
