"""Un sólido con relieve, renderizado fuera de línea a un PNG que la escena 2D usa como imagen.

Manim 0.22 no tiene z-buffer: pinta cara por cara en el orden que le entregan, y para ordenar usa el
centroide proyectado de cada cara. Cada rareza de abajo (pintar por profundidad, reset_rotation_matrix(),
resolution=(48, 2), el contorno sacado de los píxeles) existe por eso y fue medida cuadro por cuadro.
Costo: 0,21 s por cuerpo.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from manim import (
    DEGREES,
    ORIGIN,
    Circle,
    Cone,
    Cylinder,
    Group,
    ImageMobject,
    Prism,
    Sphere,
    ThreeDCamera,
    VGroup,
)
from PIL import Image

from . import __version__
from . import componentes as c
from . import dibujos as d
from .entorno import raiz_proyecto
from .errores import ErrorMotor

# (phi, theta) en grados. phi es el ángulo desde el CENIT, no desde el piso: phi=90 mira de costado
# (alzado) y phi=0 mira desde arriba (planta). Con phi=0 «de frente» el cilindro salía un círculo.
VISTAS: dict[str, tuple[float, float]] = {
    "frente": (90.0, -90.0),
    "ala": (90.0, 0.0),
    "piso": (0.0, -90.0),
    "axonometrica": (60.0, -55.0),
}

PX = 950  # ancho del PNG; el alto sale de la razón ancho/alto del cuadro de dibujo
LARGO_MARCO = 3.2  # lado corto del marco 3D, en unidades de Manim
OBJETIVO = 0.80  # cuánto del lado corto ocupa el cuerpo
MARGEN_PX = 6  # aire que se deja al recortar, para no comerse el trazo


def _rgb(color: Any) -> tuple[int, int, int]:
    hexa = str(color).lstrip("#")
    return int(hexa[0:2], 16), int(hexa[2:4], 16), int(hexa[4:6], 16)


def _puntos(grupo: VGroup) -> np.ndarray:
    return np.vstack([m.points for m in grupo.get_family() if len(m.points)])


@dataclass
class Cuadro3D:
    """El PNG recortado y la cámara que lo generó, para poder anclar los rótulos sobre el cuerpo."""

    camara: ThreeDCamera
    ancho_px: int
    alto_px: int
    marco_ancho: float
    marco_alto: float
    recorte: tuple[int, int, int, int]  # x0, y0, ancho, alto dentro del PNG sin recortar
    centro: np.ndarray  # el centro 3D que se le restó al cuerpo
    factor: float  # la escala que se le aplicó para que entrara en el marco

    def pixeles(self, punto: Any) -> tuple[float, float]:
        """Un punto en las coordenadas 3D originales → (x, y) en píxeles del PNG recortado."""
        p = (np.asarray(punto, dtype=float) - self.centro) * self.factor
        pro = self.camara.project_point(p)
        x = (pro[0] / self.marco_ancho + 0.5) * self.ancho_px - self.recorte[0]
        y = (0.5 - pro[1] / self.marco_alto) * self.alto_px - self.recorte[1]
        return float(x), float(y)


def _piezas(figura: str, corte: str, r: float, h: float, a: float, col: Any):
    """(lo que va detrás del todo, lo que se ordena por profundidad, lo que va al frente).

    Las tapas del cilindro y la base del cono se dibujan a mano: con show_ends=True Manim las pinta
    en el orden de la familia y el cuerpo sale abierto como una taza.
    """
    linea = col.formulas
    if figura == "cubo":
        dims = [a, a, a / 2] if corte == "mitad" else [a, a, a]
        caja = Prism(dimensions=dims).set_fill(col.tenue, 1).set_stroke(linea, 3)
        # La cara +Z (submobjects[1]): con corte es la que queda expuesta y se pinta de acento;
        # sin corte es la tapa, y aclararla es lo único que le da relieve al cubo sin sombreado.
        caja.submobjects[1].set_fill(col.acento if corte == "mitad" else col.cuadricula, 1)
        return [], [m for m in caja.get_family() if len(m.points)], []
    if figura == "cilindro":
        manto = (
            Cylinder(radius=r, height=h, show_ends=False, resolution=(48, 2))
            .set_fill(col.tenue, 1)
            .set_stroke(linea, 0)
        )
        abajo = Circle(radius=r, num_components=48).set_fill(col.tenue, 1).set_stroke(linea, 3)
        abajo.move_to([0, 0, -h / 2])
        arriba = Circle(radius=r, num_components=48).set_fill(col.cuadricula, 1).set_stroke(linea, 3)
        arriba.move_to([0, 0, h / 2])
        return [abajo], [manto], [arriba]
    if figura == "cono":
        manto = (
            Cone(base_radius=r, height=h, show_base=False, resolution=(48, 2))
            .set_fill(col.tenue, 1)
            .set_stroke(linea, 0)
        )
        base = Circle(radius=r, num_components=48).set_fill(col.tenue, 1).set_stroke(linea, 3)
        base.move_to([0, 0, -h])  # el cono de Manim cuelga bajo el origen: su base no está en z=0
        return [base], [manto], []
    bola = Sphere(radius=r, resolution=(36, 24)).set_fill(col.tenue, 1).set_stroke(linea, 0)
    return [], [bola], []


def _contorno(cuerpo: np.ndarray, grosor: int = 3) -> np.ndarray:
    """El borde exterior de la máscara: la silueta que las superficies de Manim no traen.

    Trazar cada quad de la superficie dibuja una malla sobre el cuerpo, y sin trazo el cilindro y el
    cono no tienen lados. Los píxeles ya renderizados sí dicen dónde termina el cuerpo.
    """
    interior = cuerpo.copy()
    for dy in range(-grosor, grosor + 1):
        for dx in range(-grosor, grosor + 1):
            interior &= np.roll(cuerpo, (dy, dx), (0, 1))
    return cuerpo & ~interior


def _png_transparente(rgb: np.ndarray, papel, linea, con_contorno: bool):
    """Recorta el cuerpo a su caja con el papel transparente. Devuelve (RGBA, (x0, y0, w, h))."""
    if con_contorno:
        rgb = rgb.copy()
        cuerpo = np.abs(rgb.astype(int) - np.array(papel)).max(axis=2) > 10
        rgb[_contorno(cuerpo)] = linea
    cuerpo = np.abs(rgb.astype(int) - np.array(papel)).max(axis=2) > 10
    ys, xs = np.nonzero(cuerpo)
    if len(xs) == 0:
        raise ErrorMotor("el sólido 3D salió en blanco: revisa los colores del estilo.")
    x0 = max(int(xs.min()) - MARGEN_PX, 0)
    y0 = max(int(ys.min()) - MARGEN_PX, 0)
    x1 = min(int(xs.max()) + MARGEN_PX + 1, rgb.shape[1])
    y1 = min(int(ys.max()) + MARGEN_PX + 1, rgb.shape[0])
    recorte = rgb[y0:y1, x0:x1]
    alpha = (np.abs(recorte.astype(int) - np.array(papel)).max(axis=2) > 10) * 255
    return np.dstack([recorte, alpha.astype(np.uint8)]), (x0, y0, x1 - x0, y1 - y0)


def _medidas(visual: Any) -> tuple[float, float, float]:
    """(radio, altura, arista) del dibujo, con la proporción real que dijo el guion.

    Un cilindro r=1 h=4 se dibuja esbelto y uno r=3 h=5 pancigordo: el número en pantalla y la forma
    tienen que decir lo mismo. El cubo y la esfera no tienen proporción que respetar.
    """
    cuerpo = visual.solido()
    if cuerpo.figura == "cubo":
        return 1.0, 1.0, 2.6
    if cuerpo.figura == "esfera":
        return 1.5, 0.0, 0.0
    r = 3.0 * float(cuerpo.radio) / float(cuerpo.altura) if cuerpo.radio and cuerpo.altura else 1.15
    return min(max(r, 0.35), 1.9), 3.0, 0.0


def _ruta_cache(figura, vista, corte, r, h, a, col, papel) -> Path:
    huella = hashlib.sha1(
        json.dumps(
            [
                figura,
                vista,
                # los ángulos y la versión van en la huella: si cambia VISTAS o el modo en que se pinta
                # una cara, el PNG viejo ya no coincide y hay que re-renderizarlo, no servirlo de cache
                list(VISTAS[vista]),
                __version__,
                corte,
                round(r, 3),
                round(h, 3),
                a,
                col.tenue,
                col.cuadricula,
                col.acento,
                col.formulas,
                papel,
            ],
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:16]
    carpeta = raiz_proyecto() / "salida" / "_3d"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / f"{figura}_{vista}_{corte}_{huella}.png"


def _render(visual: Any, col: Any, ancho: float, alto: float, papel: str) -> tuple[Path, Cuadro3D]:
    figura, corte, vista = visual.figura, visual.corte, visual.vista
    r, h, a = _medidas(visual)
    destino = _ruta_cache(figura, vista, corte, r, h, a, col, papel)
    phi, theta = VISTAS[vista]
    if ancho >= alto:
        marco_alto, marco_ancho = LARGO_MARCO, LARGO_MARCO * ancho / alto
    else:
        marco_ancho, marco_alto = LARGO_MARCO, LARGO_MARCO * alto / ancho
    alto_px = int(round(PX * alto / ancho))
    # La cámara y el encuadre se arman siempre, haya o no PNG en cache: los rótulos se anclan
    # proyectando sobre esta misma cámara, y construirlos cuesta milisegundos contra capturar.
    camara = _camara(phi, theta, marco_ancho, marco_alto, alto_px, papel)
    detras, cuerpo, encima = _piezas(figura, corte, r, h, a, col)
    grupo = VGroup(*detras, *cuerpo, *encima)
    centro, factor = _encuadrar(camara, grupo, marco_ancho, marco_alto)
    lado = destino.with_suffix(".json")
    if destino.exists() and lado.exists():
        recorte = tuple(json.loads(lado.read_text(encoding="utf-8"))["recorte"])
        return destino, Cuadro3D(camara, PX, alto_px, marco_ancho, marco_alto, recorte, centro, factor)

    def profundidad(m):
        return float(camara.project_points(m.points)[:, 2].mean())

    for m in VGroup(*detras).get_family():
        camara.capture_mobject(m)
    for m in sorted([x for x in VGroup(*cuerpo).get_family() if len(x.points)], key=profundidad):
        camara.capture_mobject(m)
    for m in VGroup(*encima).get_family():
        camara.capture_mobject(m)
    imagen = camara.get_image()  # PIL: si se pasa a np.asarray() se pierde .save y .convert
    rgba, recorte = _png_transparente(
        np.array(imagen.convert("RGB")), _rgb(papel), _rgb(col.formulas), con_contorno=figura != "cubo"
    )
    Image.fromarray(rgba, "RGBA").save(destino)
    # El recorte va al lado del PNG: sin él, la segunda vez que se pide el mismo cuerpo los rótulos
    # se anclarían como si el PNG no estuviera recortado y saldrían corridos.
    lado.write_text(json.dumps({"recorte": list(recorte)}), encoding="utf-8")
    return destino, Cuadro3D(camara, PX, alto_px, marco_ancho, marco_alto, recorte, centro, factor)


def _camara(phi, theta, marco_ancho, marco_alto, alto_px, papel) -> ThreeDCamera:
    camara = ThreeDCamera(
        pixel_width=PX,
        pixel_height=alto_px,
        frame_width=marco_ancho,
        frame_height=marco_alto,
        background_color=papel,
        should_apply_shading=False,  # con sombreado el manto sale a franjas
    )
    camara.set_phi(phi * DEGREES)
    camara.set_theta(theta * DEGREES)
    camara.set_gamma(0.0)
    # set_phi/set_theta solo mueven trackers: sin esto la rotación queda la de la cámara recién creada
    # y las cuatro vistas salen idénticas.
    camara.reset_rotation_matrix()
    return camara


def _encuadrar(camara, grupo, marco_ancho, marco_alto) -> tuple[np.ndarray, float]:
    """Centra el cuerpo en su propia caja 3D y lo escala hasta OBJETIVO del lado corto."""
    pts = _puntos(grupo)
    centro = (pts.max(axis=0) + pts.min(axis=0)) / 2
    grupo.shift(-centro)
    factor = 1.0
    for _ in range(6):
        pro = camara.project_points(_puntos(grupo))  # todos los puntos: muestrear de a 7 se salta esquinas
        excede = (
            max(
                (pro[:, 0].max() - pro[:, 0].min()) / marco_ancho,
                (pro[:, 1].max() - pro[:, 1].min()) / marco_alto,
            )
            / OBJETIVO
        )
        if excede <= 1.0:
            break
        grupo.scale(1.0 / excede)
        factor /= excede
    return centro, factor


def dibujar_solido_3d(visual: Any, col: Any, ancho: float, alto: float, papel: str = "#FFFFFF") -> d.Dibujo:
    """El cuerpo en relieve como imagen, con su medida y su V y A escritos al lado."""
    ruta, cuadro = _render(visual, col, ancho, alto, papel)
    imagen = ImageMobject(str(ruta))
    imagen.scale(OBJETIVO * min(alto / imagen.height, ancho / imagen.width))
    imagen.move_to(ORIGIN)

    s = imagen.width / cuadro.recorte[2]  # unidades de escena por píxel del PNG

    def ancla(punto_3d, dx: float = 0.0, dy: float = 0.0) -> np.ndarray:
        x, y = cuadro.pixeles(punto_3d)
        return np.array([(x - cuadro.recorte[2] / 2) * s + dx, (cuadro.recorte[3] / 2 - y) * s + dy, 0.0])

    cuerpo = visual.solido()
    r, h, a = _medidas(visual)
    unidad = cuerpo.unidad or ""
    parches, rótulos = VGroup(), VGroup()

    def etiqueta(texto: str, donde: np.ndarray, tam: int = 26) -> None:
        rotulo = c.texto(texto, tam, c.SEMIBOLD, col.texto).move_to(donde)
        fondo, rotulo = d._parche(rotulo, papel, 0.16)  # el mismo cartón que usa la lámina 2D
        parches.add(fondo)
        rótulos.add(rotulo)

    def mide(clave: str, valor: float, punto, dx: float, dy: float) -> None:
        etiqueta(f"{clave} = {d._numero_latex(valor)} {unidad}".strip(), ancla(punto, dx, dy))

    if cuerpo.figura == "cubo":
        mide("a", cuerpo.lado or a, [0, -a / 2, -a / 2], 0.0, -0.42)
    elif cuerpo.figura == "cilindro":
        mide("r", cuerpo.radio or 0.0, [r / 2, 0, h / 2], 0.0, 0.34)
        mide("h", cuerpo.altura or 0.0, [-r, 0, 0], -0.85, 0.0)
    elif cuerpo.figura == "cono":
        mide("r", cuerpo.radio or 0.0, [r / 2, 0, -h], 0.0, -0.34)
        mide("h", cuerpo.altura or 0.0, [0, 0, -h / 2], -0.95, 0.0)
    else:
        mide("r", cuerpo.radio or 0.0, [r / 2, 0, 0], 0.0, 0.30)

    # El volumen y el área al costado, donde siempre hay hueco: el cuerpo mide ~2,6 de 7,6 de ancho.
    pie = 0
    for marca in visual.anotar[:2]:
        valor = cuerpo.volumen if marca == "volumen" else cuerpo.area
        sufijo = "³" if marca == "volumen" else "²"
        etiqueta(
            f"{'V' if marca == 'volumen' else 'A'} = {d._numero_latex(valor)} {unidad}{sufijo}".strip(),
            np.array([ancho * 0.30, 0.42 - pie * 0.62, 0.0]),
            28,
        )
        pie += 1

    # El cuerpo se centró en el origen y los rótulos cuelgan debajo: sin centrar el conjunto, el
    # rótulo del cubo de frente se sale del cuadro por abajo (medido: y = -1,684 contra -1,65).
    todo = Group(imagen, parches, rótulos)  # ImageMobject es raster: no entra en un VGroup
    todo.move_to(ORIGIN)
    todo = d._encajar(todo, ancho * 0.94, alto * 0.94)
    return d.Dibujo(mobs=todo, trazo=[], aparece=[imagen, *rótulos])
