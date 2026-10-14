"""Comandos del motor. Se usan desde la carpeta del repo con ``./tpi <comando>``.

./tpi doctor                         ¿está todo instalado?
./tpi nuevo mi_ejercicio             crea guiones/mi_ejercicio.yaml desde la plantilla
./tpi revisar guiones/x.yaml         revisa el guion (duración, gancho, frases)
./tpi crear guiones/x.yaml           crea el video final
./tpi crear guiones/x.yaml --borrador    versión rápida para revisar
./tpi subtitular video.mp4           subtítulos estilo CapCut para cualquier video
./tpi voces                          voces disponibles en español
"""

from __future__ import annotations

import argparse
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
    from .doctor import diagnosticar

    consola.print("[bold]🩺 Diagnóstico del motor de video[/]\n")
    with consola.status("Revisando… (la primera vez puede tardar unos segundos)"):
        chequeos = diagnosticar(probar_red=args.red)
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

    proveedor, voz = None, None
    if args.voz:
        proveedor, voz = (args.voz, None) if args.voz in PROVEEDORES else ("edge", args.voz)

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
    )
    nombres = {"voz": "marcas exactas de la voz", "whisper": "Whisper", "estimado": "tiempos estimados"}
    fuentes = ", ".join(nombres[f] for f in sorted(resultado.fuentes_tiempo)) or "sin subtítulos"
    ruta = _ruta_amigable(resultado.video)
    consola.print(f"\n[green bold]✅ Video listo:[/] {ruta}")
    consola.print(
        f"   Duración: {resultado.duracion:.1f} s · Proceso: {_minutos(resultado.segundos_proceso)} · "
        f"Subtítulos: {fuentes}"
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
        )
    ruta = _ruta_amigable(salida)
    consola.print(f'[green bold]✅ Listo:[/] {ruta}\n   Para verlo: [bold]open "{ruta}"[/]')
    if args.abrir:
        _abrir(salida)
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
    s.add_argument("--abrir", action="store_true", help="abre el video al terminar")
    s.set_defaults(func=cmd_crear)

    s = sub.add_parser("subtitular", help="subtítulos estilo CapCut para cualquier video (usa Whisper)")
    s.add_argument("video", help="ruta al video")
    s.add_argument(
        "--texto", help="archivo .txt con el texto exacto que se dice (opcional, mejora la precisión)"
    )
    s.add_argument("--modelo", default="base", help="modelo de Whisper: tiny, base, small, medium")
    s.add_argument("--salida", help="carpeta de salida (por defecto: salida/subtitulados/)")
    s.add_argument("--abrir", action="store_true", help="abre el video al terminar")
    s.set_defaults(func=cmd_subtitular)

    s = sub.add_parser("voces", help="lista las voces en español")
    s.add_argument("--todas", action="store_true", help="todos los países de habla hispana")
    s.set_defaults(func=cmd_voces)
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
        consola.print(f"\n[bold red]✖ {e.mensaje}[/]")
        if e.ayuda:
            consola.print(f"[yellow]→ {e.ayuda}[/]")
        return 1
    except KeyboardInterrupt:
        consola.print("\n[yellow]Cancelado.[/]")
        return 130
    except Exception as e:  # error inesperado: mensaje corto y, con --debug, el detalle
        if args.debug:
            traceback.print_exc()
        consola.print(f"\n[bold red]✖ Error inesperado: {e}[/]")
        consola.print(
            "[yellow]→ Vuelve a ejecutar con --debug (ej. ./tpi --debug crear …) y comparte el mensaje.[/]"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
