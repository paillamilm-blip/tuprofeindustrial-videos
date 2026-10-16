"""Comandos del motor. Se usan desde la carpeta del repo con ``./tpi <comando>``.

./tpi doctor                         ¿está todo instalado?
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
./tpi icono                          crea un ícono en el Escritorio para abrir el panel
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
    from .voces import PROVEEDORES

    json_activo = _modo_json(args)

    proveedor, voz = None, None
    if args.voz:
        proveedor, voz = (args.voz, None) if args.voz in PROVEEDORES else ("edge", args.voz)

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
    import shlex

    from .entorno import raiz_proyecto

    escritorio = Path.home() / "Desktop"
    if not escritorio.is_dir():
        escritorio = Path.home()
    destino = escritorio / "Panel Tu Profe Industrial.command"
    raiz = raiz_proyecto()
    destino.write_text(
        "#!/bin/bash\n"
        "# Abre el panel de control del motor de video (doble clic). Para cerrarlo: cierra esta ventana.\n"
        f"cd {shlex.quote(str(raiz))} && ./tpi panel\n",
        encoding="utf-8",
    )
    destino.chmod(0o755)
    consola.print(f"[green bold]✅ Ícono creado:[/] {destino}")
    consola.print("   Haz doble clic en «Panel Tu Profe Industrial» de tu Escritorio para abrir el panel.")
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

    s = sub.add_parser("icono", help="crea un ícono en el Escritorio para abrir el panel con doble clic")
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
