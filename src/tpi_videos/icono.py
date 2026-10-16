"""El ícono del panel en el Escritorio: «Panel Tu Profe Industrial.command» (doble clic = abre el panel).

En el Mac se le pone la imagen de la marca (``assets/icono/panel.png``: cuadrado azul, engranaje amarillo y
▶ rojo) y se muestra en Finder para encontrarlo al tiro. Para la imagen se usan ``osascript`` y ``xattr``, que
vienen con macOS: no hay que instalar nada. Si algo de eso falla, el ícono igual funciona (con el dibujo de
siempre de un documento de la Terminal).
"""

from __future__ import annotations

import os
import platform
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .entorno import PAQUETE, raiz_proyecto

IMAGEN = PAQUETE / "assets" / "icono" / "panel.png"
NOMBRE = "Panel Tu Profe Industrial.command"


@dataclass
class Icono:
    ruta: Path
    con_imagen: bool  # se le puso la imagen de la marca
    mostrado: bool  # se abrió Finder con el ícono marcado


def es_mac() -> bool:
    return platform.system() == "Darwin"


def escritorio() -> Path:
    carpeta = Path.home() / "Desktop"  # en un Mac en español, Finder la muestra como «Escritorio»
    return carpeta if carpeta.is_dir() else Path.home()


# AppleScript con el puente a Cocoa: el mismo método que usa la herramienta «fileicon» (probada desde la
# Terminal en macOS recientes). Las rutas llegan como argumentos («argv»), nunca dentro del texto del script:
# así un espacio, una comilla o una tilde en la ruta no lo pueden romper.
SCRIPT_IMAGEN = (
    'use framework "Cocoa"',
    "on run argv",
    "set imagen to (current application's NSImage's alloc()'s initWithContentsOfFile:(item 1 of argv))",
    "(current application's NSWorkspace's sharedWorkspace()'s setIcon:imagen forFile:(item 2 of argv) options:2)",
    "end run",
)
# Así guarda macOS un ícono propio: el dibujo en «com.apple.ResourceFork» y, en «com.apple.FinderInfo», la marca
# «tiene ícono propio» (el byte 8 con el valor 0x04). Se revisa igual que «fileicon».
BYTE_MARCA, VALOR_MARCA = 8, 0x04


def comando_imagen(archivo: Path, imagen: Path = IMAGEN) -> list[str]:
    lineas = [parte for linea in SCRIPT_IMAGEN for parte in ("-e", linea)]
    return ["osascript", *lineas, str(imagen), str(archivo)]


def _xattr(*args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(["xattr", *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None


def _tiene_icono_propio(archivo: Path) -> bool | None:
    """¿macOS guardó el ícono? (setIcon responde «sí» incluso cuando falla). None = no se pudo revisar."""
    lista = _xattr(str(archivo))
    if lista is None or lista.returncode != 0:
        return None
    if "com.apple.ResourceFork" not in lista.stdout.split():
        return False
    info = _xattr("-px", "com.apple.FinderInfo", str(archivo))
    if info is None or info.returncode != 0:
        return False
    try:
        datos = bytes.fromhex("".join(info.stdout.split()))
    except ValueError:
        return None
    return len(datos) > BYTE_MARCA and bool(datos[BYTE_MARCA] & VALOR_MARCA)


def poner_imagen(archivo: Path, imagen: Path = IMAGEN) -> bool:
    if not es_mac() or not imagen.is_file():
        return False
    try:
        proceso = subprocess.run(comando_imagen(archivo, imagen), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    if proceso.returncode != 0:
        return False
    revisado = _tiene_icono_propio(archivo)
    if revisado:
        os.utime(archivo)  # aviso a Finder para que dibuje el ícono nuevo sin esperar
    return revisado is not False


def mostrar_en_finder(archivo: Path) -> bool:
    if not es_mac():
        return False
    try:
        subprocess.Popen(["open", "-R", str(archivo)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return True


def crear_icono(mostrar: bool = True) -> Icono:
    destino = escritorio() / NOMBRE
    destino.write_text(
        "#!/bin/bash\n"
        "# Abre el panel de control del motor de video (doble clic). Para cerrarlo: cierra esta ventana.\n"
        f"cd {shlex.quote(str(raiz_proyecto()))} && ./tpi panel\n",
        encoding="utf-8",
    )
    destino.chmod(0o755)
    con_imagen = poner_imagen(destino)
    mostrado = mostrar and mostrar_en_finder(destino)
    return Icono(ruta=destino, con_imagen=con_imagen, mostrado=mostrado)
