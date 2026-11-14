"""Los cuerpos en 3D: el sólido vivo (malla proyectada con órbita, luz y despiece) y las láminas PNG.

El sólido (``dibujar_solido_3d``) se proyecta cuadro a cuadro: ver la sección «El sólido vivo». El vector
3D y la lámina quieta del sólido siguen siendo un PNG renderizado fuera de línea que la escena usa como
imagen; lo que sigue explica por qué esa receta es como es.

Manim 0.22 no tiene z-buffer: pinta cara por cara en el orden que le entregan, y para ordenar usa el
centroide proyectado de cada cara. Cada rareza de abajo (pintar por profundidad, reset_rotation_matrix(),
resolution=(48, 2), el contorno sacado de los píxeles) existe por eso y fue medida cuadro por cuadro.
Costo: 0,21 s por cuerpo.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from manim import (
    DEGREES,
    ORIGIN,
    Arrow,
    Circle,
    Cone,
    Cylinder,
    DashedLine,
    Group,
    ImageMobject,
    Line,
    ManimColor,
    Mobject,
    Prism,
    Sphere,
    ThreeDCamera,
    VGroup,
    VMobject,
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

PX = 1300  # ancho del PNG; con el zoom de cámara (0,84) sigue nítido, sin estirarse
LARGO_MARCO = 3.2  # lado corto del marco 3D, en unidades de Manim
LARGO_CAJA = 2.4  # la dimensión mayor del vector, en unidades de Manim
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


def _ruta_cache(figura, vista, corte, r, h, a, col, papel, aspect: float) -> Path:
    huella = hashlib.sha1(
        json.dumps(
            [
                figura,
                vista,
                # los ángulos y la versión van en la huella: si cambia VISTAS o el modo en que se pinta
                # una cara, el PNG viejo ya no coincide y hay que re-renderizarlo, no servirlo de cache
                list(VISTAS[vista]),
                __version__,
                PX,  # más resolución = otro PNG: el viejo no sirve para el zoom
                round(aspect, 3),  # la proporción de la banda: otro marco es otro PNG y otro recorte
                corte,
                round(r, 3),
                round(h, 3),
                a,
                col.tenue,
                col.cuadricula,
                col.acento,
                col.formulas,
                col.exito,  # la línea de «norma» se pinta con este color dentro del PNG
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
    destino = _ruta_cache(figura, vista, corte, r, h, a, col, papel, aspect=alto / ancho)
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


# ------------------------------------------------------------------------------------------
# El sólido vivo: malla proyectada cuadro a cuadro, con órbita, luz y despiece
# ------------------------------------------------------------------------------------------
#
# La escena es 2D (MovingCameraScene: la cámara de los pasos, los subtítulos y la franja del dibujo
# viven ahí), así que el 3D no pasa por ThreeDScene: el cuerpo es una malla real que se proyecta con
# una cámara propia en cada cuadro. Cada cara se sombrea con su normal (Lambert + brillo especular),
# las caras de espalda se descartan y el resto se pinta de atrás hacia adelante. En cuerpos convexos
# eso basta para que la oclusión sea exacta, sin el z-buffer que Cairo no tiene.

GIRO_ORBITA = 75.0  # grados que la cámara recorre antes de asentarse en la vista pedida
CABECEO_ORBITA = 25.0  # cuánto cambia la altura de la cámara durante la órbita
PARTE_ORBITA = 0.6  # con despiece, la órbita usa el 60 % del recorrido y la separación el resto


@dataclass
class _Cara:
    puntos: np.ndarray  # (k, 3)
    normal: np.ndarray  # hacia afuera del cuerpo
    clase: str  # "cuerpo" | "tapa" | "corte" | "anillo" (canto de un tubo) | "interior" (su hueco)


@dataclass
class _Pieza:
    caras: list[_Cara]
    salida: np.ndarray  # hacia dónde se va en el despiece (ya con su largo)
    cerrada: bool  # True: las caras de espalda nunca se ven
    lisa: bool  # True: se le dibuja la silueta (cilindro, cono, esfera); el cubo ya tiene aristas
    # El centro de la pieza, para ordenar el pintado entre piezas. En las de siempre queda en cero y
    # el orden es solo por cuánto se apartaron en el despiece.
    centro: np.ndarray = field(default_factory=lambda: np.zeros(3))


def _unitario(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def _caja(
    x0: float, x1: float, y0: float, y1: float, z0: float, z1: float, corte: str | None = None
) -> list[_Cara]:
    """Las seis caras de una caja; ``corte`` dice qué cara es la del corte ("arriba" o "abajo")."""
    v = {
        (i, j, k): np.array([(x0, x1)[i], (y0, y1)[j], (z0, z1)[k]])
        for i in (0, 1)
        for j in (0, 1)
        for k in (0, 1)
    }
    caras = [
        ([v[0, 0, 0], v[1, 0, 0], v[1, 0, 1], v[0, 0, 1]], [0, -1, 0], "frente"),
        ([v[1, 1, 0], v[0, 1, 0], v[0, 1, 1], v[1, 1, 1]], [0, 1, 0], "fondo"),
        ([v[0, 1, 0], v[0, 0, 0], v[0, 0, 1], v[0, 1, 1]], [-1, 0, 0], "izquierda"),
        ([v[1, 0, 0], v[1, 1, 0], v[1, 1, 1], v[1, 0, 1]], [1, 0, 0], "derecha"),
        ([v[0, 0, 1], v[1, 0, 1], v[1, 1, 1], v[0, 1, 1]], [0, 0, 1], "arriba"),
        ([v[0, 1, 0], v[1, 1, 0], v[1, 0, 0], v[0, 0, 0]], [0, 0, -1], "abajo"),
    ]
    return [
        _Cara(np.array(pts, dtype=float), np.array(n, dtype=float), "corte" if nombre == corte else "cuerpo")
        for pts, n, nombre in caras
    ]


def _anillo(radio: float, z: float, lados: int) -> np.ndarray:
    angulos = np.linspace(0.0, 2 * np.pi, lados, endpoint=False)
    return np.stack([radio * np.cos(angulos), radio * np.sin(angulos), np.full(lados, z)], axis=1)


def _piezas_vivas(figura: str, corte: str, despiece: bool, r: float, h: float, a: float) -> list[_Pieza]:
    """La malla del cuerpo, centrada en el origen y partida en las piezas que se separan."""
    lados = 48
    if figura == "cubo":
        s = a / 2
        if corte == "mitad":
            # Las dos mitades: la de arriba se levanta y deja ver la cara nueva que destapó el corte.
            return [
                _Pieza(_caja(-s, s, -s, s, -s, 0.0, corte="arriba"), np.zeros(3), True, False),
                _Pieza(
                    _caja(-s, s, -s, s, 0.0, s, corte="abajo"), np.array([0.0, 0.0, 0.85 * a]), True, False
                ),
            ]
        caras = _caja(-s, s, -s, s, -s, s)
        if not despiece:
            return [_Pieza(caras, np.zeros(3), True, False)]
        # Las seis caras se apartan cada una por su normal: el área son seis cuadrados, y se ven.
        return [_Pieza([cara], cara.normal * 0.45 * a, False, False) for cara in caras]
    if figura == "esfera":
        meridianos, paralelos = 28, 16
        caras = []
        for i in range(paralelos):
            t0, t1 = np.pi * i / paralelos, np.pi * (i + 1) / paralelos
            for j in range(meridianos):
                f0, f1 = 2 * np.pi * j / meridianos, 2 * np.pi * (j + 1) / meridianos

                def punto(t: float, f: float) -> np.ndarray:
                    return r * np.array([np.sin(t) * np.cos(f), np.sin(t) * np.sin(f), np.cos(t)])

                pts = np.array([punto(t0, f0), punto(t1, f0), punto(t1, f1), punto(t0, f1)])
                centro = pts.mean(axis=0)
                caras.append(_Cara(pts, _unitario(centro), "cuerpo"))
        return [_Pieza(caras, np.zeros(3), True, True)]
    abajo = _anillo(r, -h / 2, lados)
    base = _Cara(abajo[::-1].copy(), np.array([0.0, 0.0, -1.0]), "tapa")
    manto: list[_Cara] = []
    if figura == "cilindro":
        arriba = _anillo(r, h / 2, lados)
        for i in range(lados):
            j = (i + 1) % lados
            pts = np.array([abajo[i], abajo[j], arriba[j], arriba[i]])
            manto.append(_Cara(pts, _unitario(np.array([*pts.mean(axis=0)[:2], 0.0])), "cuerpo"))
        tapa = _Cara(arriba.copy(), np.array([0.0, 0.0, 1.0]), "tapa")
        if not despiece:
            return [_Pieza([base, *manto, tapa], np.zeros(3), True, True)]
        # El área del cilindro son dos círculos y un manto: las tapas se van por su eje y se ven solas.
        return [
            _Pieza([base], np.array([0.0, 0.0, -0.45 * h]), False, False),
            _Pieza(manto, np.zeros(3), False, True),
            _Pieza([tapa], np.array([0.0, 0.0, 0.45 * h]), False, False),
        ]
    punta = np.array([0.0, 0.0, h / 2])
    pendiente = r / h  # la normal del manto sube tanto como se abre el cono
    for i in range(lados):
        j = (i + 1) % lados
        pts = np.array([abajo[i], abajo[j], punta])
        medio = (abajo[i] + abajo[j]) / 2
        manto.append(_Cara(pts, _unitario(np.array([medio[0], medio[1], pendiente * r])), "cuerpo"))
    if not despiece:
        return [_Pieza([base, *manto], np.zeros(3), True, True)]
    return [
        _Pieza([base], np.array([0.0, 0.0, -0.5 * h]), False, False),
        _Pieza(manto, np.zeros(3), False, True),
    ]


def _ejes_de_camara(phi: float, theta: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(derecha, arriba, hacia la cámara) para phi desde el cenit y theta como en VISTAS."""
    p, t = np.radians(phi), np.radians(theta)
    hacia = np.array([np.sin(p) * np.cos(t), np.sin(p) * np.sin(t), np.cos(p)])
    derecha = np.array([-np.sin(t), np.cos(t), 0.0])
    arriba = np.cross(hacia, derecha)
    return derecha, arriba, hacia


def _tono(base: Any, hacia: str, cuanto: float) -> ManimColor:
    return ManimColor(base).interpolate(ManimColor(hacia), float(min(max(cuanto, 0.0), 1.0)))


def dibujar_solido_3d(visual: Any, col: Any, ancho: float, alto: float, papel: str = "#FFFFFF") -> d.Dibujo:
    """El cuerpo en 3D de verdad: la cámara orbita hasta la vista pedida y, si toca, se despieza.

    La pose final (``vivo(1)``) es la vista que pidió el guion: la miniatura y el último cuadro del
    paso muestran lo mismo que mostraba la lámina. Los rótulos de medida viajan pegados a su arista.
    """
    cuerpo = visual.solido()
    r, h, a = _medidas(visual)
    corte = visual.corte if cuerpo.figura == "cubo" else "sin_corte"
    despiece = bool(getattr(visual, "despiece", False)) and cuerpo.figura != "esfera"
    piezas = _piezas_vivas(cuerpo.figura, corte, despiece, r, h, a)
    unidad = cuerpo.unidad or ""

    def mide(clave: str, valor: float) -> str:
        return f"{clave} = {d._numero_latex(valor)} {unidad}".strip()

    if cuerpo.figura == "cubo":
        medidas = [(mide("a", cuerpo.lado or a), [0, -a / 2, -a / 2], 0, "abajo")]
    elif cuerpo.figura == "cilindro":
        medidas = [
            (mide("r", cuerpo.radio or 0.0), [r / 2, 0, h / 2], 2 if despiece else 0, "arriba"),
            (mide("h", cuerpo.altura or 0.0), [-r, 0, 0], 1 if despiece else 0, "izquierda"),
        ]
    elif cuerpo.figura == "cono":
        medidas = [
            (mide("r", cuerpo.radio or 0.0), [r / 2, 0, -h / 2], 0, "abajo"),
            (mide("h", cuerpo.altura or 0.0), [0, 0, 0], 1 if despiece else 0, "izquierda"),
        ]
    else:
        medidas = [(mide("r", cuerpo.radio or 0.0), [r / 2, 0, 0], 0, "arriba")]
    notas = []
    for marca in visual.anotar[:2]:
        valor = cuerpo.volumen if marca == "volumen" else cuerpo.area
        sufijo = "³" if marca == "volumen" else "²"
        notas.append(
            f"{'V' if marca == 'volumen' else 'A'} = {d._numero_latex(valor)} {unidad}{sufijo}".strip()
        )
    cotas = None
    if cuerpo.figura == "cubo":
        s = a / 2
        cotas = [(medidas[0][0], [-s, -s, -s], [s, -s, -s], 0, "abajo")]
    return _cuerpo_vivo(
        piezas, visual.vista, corte == "mitad" or despiece, col, ancho, alto, papel,
        medidas, notas, cotas=cotas,
    )


def _cuerpo_vivo(
    piezas: list[_Pieza],
    vista: str,
    separa: bool,
    col: Any,
    ancho: float,
    alto: float,
    papel: str,
    medidas: list[tuple[str, list[float], int | None, str]],
    notas: list[str],
    ancho_cuerpo: float = 0.50,
    cotas: list[tuple[str, list[float], list[float], int, str]] | None = None,
) -> d.Dibujo:
    """El motor común de los cuerpos 3D: órbita, luz, despiece, silueta y rótulos que viajan.

    ``medidas`` son (texto, punto 3D, pieza a la que va pegado, lado donde se apoya: arriba, abajo,
    izquierda o derecha). ``notas`` se escriben quietas a la derecha del cuerpo (V, A, sección…).
    Las piezas se pintan de atrás hacia adelante según su centro: en piezas coaxiales apiladas a lo
    largo del eje (tolva, tubería, eje) ese orden es exacto, porque las separa un plano.
    """
    phi_f, theta_f = VISTAS[vista]
    cabeceo = CABECEO_ORBITA if phi_f <= 60 else -CABECEO_ORBITA
    # El mismo cuerpo del paso anterior: la cámara parte de donde quedó (por el lado corto) y no da la
    # vuelta de nuevo; con la misma vista ni se mueve (solo se separan las piezas, si hay despiece).
    desde = d.desde_vista.get()
    if desde is not None:
        giro_desde = ((desde[1] - theta_f + 180.0) % 360.0) - 180.0
        cabeceo_desde = desde[0] - phi_f

    def momento(t: float) -> tuple[float, float, float]:
        """(phi, theta, separación 0..1) del instante t del recorrido."""
        orbita = d._suave(t / PARTE_ORBITA if separa else t)
        separacion = d._suave((t - PARTE_ORBITA) / (1 - PARTE_ORBITA)) if separa else 0.0
        if desde is not None and desde[2] and separa:
            separacion = 1.0  # ya venía desarmado: no se vuelve a cerrar para abrirse otra vez
        if desde is not None:
            return phi_f + cabeceo_desde * (1 - orbita), theta_f + giro_desde * (1 - orbita), separacion
        return phi_f + cabeceo * (1 - orbita), theta_f + GIRO_ORBITA * (1 - orbita), separacion

    # La luz es del estudio, no de la cámara: al orbitar el brillo resbala por el cuerpo y se lee el
    # volumen. El mismo cuerpo del paso anterior conserva la luz con que se lo vio, así al girar la
    # cámara no se reilumina la escena; sin paso anterior se fija con la vista final.
    der_f, arr_f, hacia_f = _ejes_de_camara(phi_f, theta_f)
    encuadre = d.desde_encuadre.get()
    if encuadre is not None and encuadre[1] is not None:
        luz = np.asarray(encuadre[1], dtype=float)
    else:
        luz = _unitario(-0.45 * der_f + 0.7 * arr_f + 0.55 * hacia_f)

    # Una sola escala para todo el recorrido: el cuerpo no puede crecer ni encogerse al girar.
    vistos = []
    for t in np.linspace(0.0, 1.0, 17):
        phi, theta, sep = momento(float(t))
        der, arr, _ = _ejes_de_camara(phi, theta)
        for pieza in piezas:
            for cara in pieza.caras:
                pts = cara.puntos + pieza.salida * sep
                vistos.append(np.stack([pts @ der, pts @ arr], axis=1))
    plano = np.vstack(vistos)
    bajo, alto_ = plano.min(axis=0), plano.max(axis=0)
    centro_2d = (bajo + alto_) / 2
    k = min(0.80 * alto / max(alto_[1] - bajo[1], 1e-6), ancho_cuerpo * ancho / max(alto_[0] - bajo[0], 1e-6))

    tecnico = cotas is not None
    oscuro = _tono(col.tenue, "#000000", 0.15 if tecnico else 0.22)
    claro = _tono(col.tenue, "#FFFFFF", 0.55 if tecnico else 0.78)
    canto = _tono(col.formulas, col.tenue, 0.35) if tecnico else ManimColor(col.formulas)
    limites = [np.zeros(4)]
    poligonos = [[VMobject() for _ in pieza.caras] for pieza in piezas]
    siluetas = [VMobject().set_stroke(canto, 1.8 if tecnico else 3.5) if pieza.lisa else None for pieza in piezas]
    rayados = [
        [VMobject().set_fill(opacity=0).set_stroke(col.acento, 1.5)
         if tecnico and cara.clase == "corte" else None for cara in pieza.caras]
        for pieza in piezas
    ]
    cuerpo_mob = VGroup(
        *[m for fila in poligonos for m in fila],
        *[s for s in siluetas if s is not None],
        *[r for fila in rayados for r in fila if r is not None],
    )
    aristas = [_aristas(pieza) if pieza.lisa else [] for pieza in piezas]

    def color_de(cara: _Cara, normal: np.ndarray, hacia: np.ndarray, de_espalda: bool) -> ManimColor:
        if cara.clase == "corte":
            return _tono(col.acento, papel, 0.85) if tecnico else ManimColor(col.acento)
        if de_espalda:
            return _tono(oscuro, "#000000", 0.25)  # el interior de una pieza abierta
        lambert = max(float(normal @ luz), 0.0)
        brillo = max(float(normal @ _unitario(luz + hacia)), 0.0) ** (18 if tecnico else 28)
        base = oscuro.interpolate(claro, 0.2 + 0.8 * lambert)
        if cara.clase == "interior":
            # Por dentro del tubo llega poca luz: el hueco se lee oscuro, como en la pieza real.
            return _tono(base, "#000000", 0.45)
        return _tono(base, "#FFFFFF", (0.18 if tecnico else 0.7) * brillo)

    def pose(t: float, llevar: Any) -> None:
        phi, theta, sep = momento(t)
        der, arr, hacia = _ejes_de_camara(phi, theta)

        def pantalla(p3: np.ndarray) -> np.ndarray:
            x, y = (p3 @ der - centro_2d[0]) * k, (p3 @ arr - centro_2d[1]) * k
            return llevar(np.array([x, y, 0.0]))

        orden = sorted(
            range(len(piezas)), key=lambda i: float((piezas[i].centro + piezas[i].salida * sep) @ hacia)
        )
        todos = np.vstack([cara.puntos + pieza.salida * sep for pieza in piezas for cara in pieza.caras])
        xs, ys = (todos @ der - centro_2d[0]) * k, (todos @ arr - centro_2d[1]) * k
        limites[0] = np.array([xs.min(), xs.max(), ys.min(), ys.max()])
        nuevos: list[Mobject] = []
        for i in orden:
            pieza, salida = piezas[i], piezas[i].salida * sep
            filas = []
            visibles = []
            for cara, mob, rayado in zip(pieza.caras, poligonos[i], rayados[i], strict=True):
                if rayado is not None:
                    rayado.clear_points()
                de_frente = float(cara.normal @ hacia) > 1e-4
                visibles.append(de_frente)
                pts = cara.puntos + salida
                if not de_frente and pieza.cerrada:
                    mob.set_fill(opacity=0.0).set_stroke(width=0.0, opacity=0.0)
                    filas.append((-1e9, mob))
                    continue
                mob.set_points_as_corners([pantalla(q) for q in [*pts, pts[0]]])
                tinte = color_de(cara, cara.normal, hacia, not de_frente)
                if pieza.lisa and cara.clase in ("cuerpo", "anillo", "interior"):
                    mob.set_fill(tinte, 1.0).set_stroke(tinte, 1.2, 1.0)  # borde del mismo tono: sin rendijas
                else:
                    mob.set_fill(tinte, 1.0).set_stroke(canto, 1.6 if tecnico else 3.0, 1.0)
                # El hueco de un tubo se ve solo por la boca: se pinta antes que la cáscara de afuera.
                profundidad = float(pts.mean(axis=0) @ hacia) - (1e6 if cara.clase == "interior" else 0.0)
                filas.append((profundidad, mob))
                if rayado is not None:
                    x0, y0, z = cara.puntos.min(axis=0)
                    x1, y1, _ = cara.puntos.max(axis=0)
                    for suma in np.linspace(x0 + y0, x1 + y1, 17)[1:-1]:
                        inicio = np.array([max(x0, suma - y1), min(y1, suma - x0), z])
                        fin = np.array([min(x1, suma - y0), max(y0, suma - x1), z])
                        rayado.start_new_path(pantalla(inicio + salida))
                        rayado.add_line_to(pantalla(fin + salida))
                    filas.append((profundidad, rayado))
            nuevos += [mob for _, mob in sorted(filas, key=lambda par: par[0])]
            silueta = siluetas[i]
            if silueta is not None:
                silueta.clear_points()
                for cara_i, q0, q1, vecina in aristas[i]:
                    # Silueta: la arista separa una cara que se ve de una que da la espalda (o es el
                    # borde abierto de una pieza suelta). Es el contorno que dibujaría un lápiz. Entre
                    # el canto de un anillo y su manto (o su hueco) además va el pliegue.
                    if not visibles[cara_i]:
                        continue
                    pliegue = vecina is not None and _pliegue(pieza.caras[cara_i], pieza.caras[vecina])
                    if vecina is None or not visibles[vecina] or pliegue:
                        silueta.start_new_path(pantalla(q0 + salida))
                        silueta.add_line_to(pantalla(q1 + salida))
                nuevos.append(silueta)
        # El orden de pintado va en z_index y no en el orden de los hijos: Manim fija la lista de lo
        # que pinta al empezar cada animación, pero la reordena por z_index en cada cuadro. Todo el
        # cuerpo cabe bajo 0,5 para que los rótulos (0,55) y las fórmulas (1) queden siempre encima.
        for rango, mob in enumerate(nuevos):
            mob.z_index = 0.02 + 0.46 * rango / max(len(nuevos), 1)

    pose(1.0, lambda q: q)

    # —— Rótulos: las medidas pegadas al cuerpo; las notas a un costado, quietas ——————————————
    parches, rótulos = VGroup(), VGroup()
    # (cartón, rótulo, punto 3D, pieza a la que va pegado, lado del cuerpo donde se apoya)
    viajeros: list[tuple[Mobject, Mobject, np.ndarray, int | None, str]] = []

    def etiqueta(texto: str, donde: np.ndarray, tam: int = 26) -> tuple[Mobject, Mobject]:
        rotulo = c.texto(texto, tam, c.SEMIBOLD, col.texto).move_to(donde)
        fondo, rotulo = d._parche(rotulo, papel, 0.16)
        parches.add(fondo)
        rótulos.add(rotulo)
        return fondo, rotulo

    for texto, punto, pieza, lado in ([] if tecnico else medidas):
        fondo, rotulo = etiqueta(texto, np.zeros(3))
        viajeros.append((fondo, rotulo, np.array(punto, dtype=float), pieza, lado))

    lineas_cota = VGroup()
    acotadas = []
    for texto, inicio, fin, pieza, lado in cotas or []:
        fondo, rotulo = etiqueta(texto, np.zeros(3))
        lineas = VGroup(*[Line(np.zeros(3), np.array([1.0, 0.0, 0.0]),
                              color=col.acento, stroke_width=1.5) for _ in range(5)])
        lineas_cota.add(lineas)
        delta = np.array(fin) - np.array(inicio)
        proyectada = np.array([delta @ der_f, delta @ arr_f, 0.0])
        if np.linalg.norm(proyectada) < 1e-5:
            phi, theta, _ = momento(0.0)
            der, arr, _ = _ejes_de_camara(phi, theta)
            proyectada = np.array([delta @ der, delta @ arr, 0.0])
        afuera = {"izquierda": [-1, 0, 0], "derecha": [1, 0, 0],
                  "arriba": [0, 1, 0], "abajo": [0, -1, 0]}[lado]
        normal = np.array([-proyectada[1], proyectada[0], 0.0])
        signo = -1 if normal @ afuera < 0 else 1
        acotadas.append((fondo, rotulo, lineas, np.array(inicio), np.array(fin), pieza, signo))

    def mover_rotulos(t: float, llevar: Any) -> None:
        """Cada medida sigue a su arista, pero apoyada por fuera del cuerpo: nunca encima de él.

        El borde se mide en la pose del instante (``limites``), así un rótulo no queda atrapado
        sobre el manto cuando la cámara gira y el cuerpo se ensancha.
        """
        phi, theta, sep = momento(t)
        der, arr, _ = _ejes_de_camara(phi, theta)
        x0, x1, y0, y1 = limites[0]
        factor = float(np.linalg.norm(llevar(np.array([1.0, 0.0, 0.0])) - llevar(np.zeros(3)))) or 1.0
        for fondo, rotulo, punto, pieza, lado in viajeros:
            p3 = punto + (piezas[pieza].salida * sep if pieza is not None else 0.0)
            x, y = (p3 @ der - centro_2d[0]) * k, (p3 @ arr - centro_2d[1]) * k
            medio_ancho, medio_alto = fondo.width / factor / 2, fondo.height / factor / 2
            if lado == "izquierda":
                sitio = np.array([x0 - 0.12 - medio_ancho, y, 0.0])
            elif lado == "derecha":
                sitio = np.array([x1 + 0.12 + medio_ancho, y, 0.0])
            elif lado == "arriba":
                sitio = np.array([x, y1 + 0.1 + medio_alto, 0.0])
            else:
                sitio = np.array([x, y0 - 0.1 - medio_alto, 0.0])
            fondo.move_to(llevar(sitio))
            rotulo.move_to(llevar(sitio))
        for fondo, rotulo, lineas, inicio, fin, pieza, signo in acotadas:
            salida = piezas[pieza].salida * sep
            puntos = np.array([inicio + salida, fin + salida])
            p, q = np.column_stack(((puntos @ der - centro_2d[0]) * k,
                                    (puntos @ arr - centro_2d[1]) * k, np.zeros(2)))
            largo = float(np.linalg.norm(q - p))
            visible = largo > 1e-5
            opacidad = float(visible)
            if inicio[2] != fin[2]:
                alto_rotulo = rotulo.height / factor
                opacidad = d._suave((largo - alto_rotulo) / alto_rotulo)
            lineas.set_stroke(opacity=opacidad)
            fondo.set_fill(opacity=opacidad)
            rotulo.set_opacity(opacidad)
            if not visible:
                sitio = llevar((p + q) / 2)
                fondo.move_to(sitio)
                rotulo.move_to(sitio)
                for linea in lineas:
                    linea.put_start_and_end_on(sitio, sitio + np.array([1e-8, 0.0, 0.0]))
                continue
            direccion = (q - p) / largo
            normal = np.array([-direccion[1], direccion[0], 0.0]) * signo
            esquinas = np.array([[x0, y0, 0], [x0, y1, 0], [x1, y0, 0], [x1, y1, 0]])
            distancia = max(float((esquinas @ normal).max() - min(p @ normal, q @ normal)), 0) + 0.12
            a, b = p + normal * distancia, q + normal * distancia
            marca = _unitario(direccion + normal) * 0.045
            segmentos = [(p, a + normal * 0.045), (q, b + normal * 0.045),
                         (a, b), (a - marca, a + marca), (b - marca, b + marca)]
            for linea, (desde, hasta) in zip(lineas, segmentos, strict=True):
                linea.put_start_and_end_on(llevar(desde), llevar(hasta))
            margen = (abs(normal[0]) * fondo.width + abs(normal[1]) * fondo.height) / factor / 2 + 0.1
            sitio = llevar((a + b) / 2 + normal * margen)
            fondo.move_to(sitio)
            rotulo.move_to(sitio)
        for fondo, rotulo, lineas, inicio, fin, _, _ in acotadas:
            if inicio[2] != fin[2]:
                continue
            opacidad = float(rotulo.get_fill_opacity())
            for otro, altura, _, p0, p1, _, _ in acotadas:
                if p0[2] == p1[2] or altura.get_fill_opacity() < 0.01:
                    continue
                espacio_x = max(fondo.get_left()[0] - otro.get_right()[0],
                                otro.get_left()[0] - fondo.get_right()[0])
                espacio_y = max(fondo.get_bottom()[1] - otro.get_top()[1],
                                otro.get_bottom()[1] - fondo.get_top()[1])
                opacidad = min(opacidad, d._suave(max(espacio_x, espacio_y) / (0.15 * factor)))
            lineas.set_stroke(opacity=opacidad)
            fondo.set_fill(opacity=opacidad)
            rotulo.set_opacity(opacidad)

    mover_rotulos(1.0, lambda q: q)
    # Las notas van a la derecha, donde siempre hubo hueco; si el cuerpo es largo (una tubería, un eje)
    # se corren lo justo para no pisar su punta en ninguna pose de la órbita.
    punta_derecha = (alto_[0] - centro_2d[0]) * k
    quietas = []
    for pie, texto in enumerate(notas[:3]):
        fondo, rotulo = etiqueta(texto, np.array([ancho * 0.30, 0.42 - pie * 0.62, 0.0]), 28)
        quietas.append((fondo, rotulo))
        minimo = punta_derecha + 0.3 + fondo.width / 2
        if fondo.get_x() < minimo:
            corrimiento = np.array([minimo - fondo.get_x(), 0.0, 0.0])
            fondo.shift(corrimiento)
            rotulo.shift(corrimiento)

    lineas_cota.set_z_index(0.52)
    parches.set_z_index(0.55)
    rótulos.set_z_index(0.56)
    todo = VGroup(cuerpo_mob, lineas_cota, parches, rótulos)
    envolvente = None
    if tecnico:
        extremos = []
        for t in np.linspace(0.0, 1.0, 65):
            pose(float(t), lambda q: q)
            mover_rotulos(float(t), lambda q: q)
            punta_derecha = max(punta_derecha, lineas_cota.get_right()[0],
                                *(fondo.get_right()[0] for fondo, *_ in acotadas))
            extremos.extend([todo.get_corner(np.array([-1, -1, 0])),
                             todo.get_corner(np.array([1, 1, 0]))])
        for fondo, rotulo in quietas:
            minimo = punta_derecha + 0.3 + fondo.width / 2
            if fondo.get_x() < minimo:
                corrimiento = np.array([minimo - fondo.get_x(), 0.0, 0.0])
                fondo.shift(corrimiento)
                rotulo.shift(corrimiento)
        extremos.extend([todo.get_corner(np.array([-1, -1, 0])),
                         todo.get_corner(np.array([1, 1, 0]))])
        bajo_total, alto_total = np.min(extremos, axis=0), np.max(extremos, axis=0)
        envolvente = VMobject().set_points_as_corners([
            bajo_total, [alto_total[0], bajo_total[1], 0],
            alto_total, [bajo_total[0], alto_total[1], 0], bajo_total,
        ]).set_fill(opacity=0).set_stroke(width=0)
        # El marco invisible conserva el centro de toda la órbita cuando la escena coloca el dibujo.
        todo.add(envolvente)
        pose(1.0, lambda q: q)
        mover_rotulos(1.0, lambda q: q)
    corrido = -todo.get_center()
    todo.shift(corrido)
    factor_encaje = d.factor_de_encaje(todo.width, todo.height, ancho * 0.94, alto * 0.94)
    fijo, desplazamiento = d._encaje(todo, ancho * 0.94, alto * 0.94)
    # El mismo cuerpo conserva el porte del paso anterior: la cámara gira, el cuerpo no se reencuadra.
    # Solo baja si la vista nueva no cabe entero con ese porte (de lado un cilindro ocupa más alto que
    # la base vista desde arriba); nunca sube, porque agrandarlo lo sacaría de la franja.
    escala = k * factor_encaje
    achique = 1.0
    if encuadre is not None and encuadre[0] and escala > 0:
        achique = min(1.0, encuadre[0] / escala)
    escala *= achique
    centro = todo.get_center().copy()
    if achique != 1.0:
        # Las notas quietas no pasan por ``llevar``: se achican con el grupo, o quedarían sueltas.
        todo.scale(achique, about_point=centro)

    def llevar(q: np.ndarray) -> np.ndarray:
        # El desplazamiento se suma al final, sin achicarlo: ``place`` corre el dibujo ya armado.
        return centro + (fijo(q + corrido) - centro - desplazamiento[0]) * achique + desplazamiento[0]

    def vivo(t: float) -> None:
        pose(t, llevar)
        mover_rotulos(t, llevar)

    vivo(1.0)
    return d.Dibujo(
        mobs=todo,
        trazo=[],
        aparece=[cuerpo_mob, *lineas_cota, *rótulos],
        vivo=vivo,
        duracion=d.SEGUNDOS_RECORRIDO,
        fisico=False,
        desplazamiento=desplazamiento,
        vista_final=(phi_f, theta_f),
        separado_final=separa,
        escala_3d=float(escala),
        luz_3d=(float(luz[0]), float(luz[1]), float(luz[2])),
    )


# ------------------------------------------------------------------------------------------
# Piezas industriales: tolva, tubería con bridas y eje escalonado
# ------------------------------------------------------------------------------------------
#
# Las tres son cuerpos de revolución hechos de tramos coaxiales: cada tramo es convexo (o un tubo
# hueco) y está separado del vecino por un plano perpendicular al eje, así que el orden de pintado
# por centro es exacto con o sin despiece.

LADOS_REVOLUCION = 48


def _tramo(r0: float, r1: float, z0: float, z1: float, lados: int = LADOS_REVOLUCION) -> list[_Cara]:
    """Un tronco de cono cerrado (o un cilindro si r0 == r1) entre z0 y z1, con sus dos tapas."""
    abajo, arriba = _anillo(r0, z0, lados), _anillo(r1, z1, lados)
    dr, dz = r1 - r0, z1 - z0
    caras = []
    for i in range(lados):
        j = (i + 1) % lados
        angulo = 2 * np.pi * (i + 0.5) / lados
        # La normal del manto: hacia afuera y, si el tramo se angosta hacia arriba, también hacia arriba.
        normal = _unitario(np.array([np.cos(angulo) * dz, np.sin(angulo) * dz, -dr]))
        caras.append(_Cara(np.array([abajo[i], abajo[j], arriba[j], arriba[i]]), normal, "cuerpo"))
    caras.append(_Cara(abajo[::-1].copy(), np.array([0.0, 0.0, -1.0]), "tapa"))
    caras.append(_Cara(arriba.copy(), np.array([0.0, 0.0, 1.0]), "tapa"))
    return caras


def _tubo(ri: float, re: float, z0: float, z1: float, lados: int = LADOS_REVOLUCION) -> list[_Cara]:
    """Un tubo hueco: cáscara de afuera, hueco de adentro y los dos cantos (anillos) de las bocas."""
    e0, e1 = _anillo(re, z0, lados), _anillo(re, z1, lados)
    i0, i1 = _anillo(ri, z0, lados), _anillo(ri, z1, lados)
    caras = []
    for i in range(lados):
        j = (i + 1) % lados
        angulo = 2 * np.pi * (i + 0.5) / lados
        radial = np.array([np.cos(angulo), np.sin(angulo), 0.0])
        caras.append(_Cara(np.array([e0[i], e0[j], e1[j], e1[i]]), radial, "cuerpo"))
        caras.append(_Cara(np.array([i0[j], i0[i], i1[i], i1[j]]), -radial, "interior"))
        caras.append(_Cara(np.array([e0[j], e0[i], i0[i], i0[j]]), np.array([0.0, 0.0, -1.0]), "anillo"))
        caras.append(_Cara(np.array([e1[i], e1[j], i1[j], i1[i]]), np.array([0.0, 0.0, 1.0]), "anillo"))
    return caras


def _a_lo_largo_de_x(p: np.ndarray) -> np.ndarray:
    """Gira el eje z al eje x (un cuarto de vuelta en torno a y): las tuberías y los ejes van acostados."""
    p = np.asarray(p, dtype=float)
    return np.stack([p[..., 2], p[..., 1], -p[..., 0]], axis=-1)


def _pieza(caras: list[_Cara], salida: np.ndarray, acostada: bool = False) -> _Pieza:
    if acostada:
        caras = [
            _Cara(_a_lo_largo_de_x(cara.puntos), _a_lo_largo_de_x(cara.normal), cara.clase) for cara in caras
        ]
        salida = _a_lo_largo_de_x(salida)
    centro = np.vstack([cara.puntos for cara in caras]).mean(axis=0)
    return _Pieza(caras, np.asarray(salida, dtype=float), True, True, centro)


def _piezas_tolva(t: Any, despiece: bool) -> list[_Pieza]:
    """El cilindro arriba (z de 0 a H) y el cono truncado abajo (de la boca r a z = −h)."""
    cilindro = _tramo(t.radio, t.radio, 0.0, t.altura)
    cono = _tramo(t.radio_salida, t.radio, -t.altura_cono, 0.0)
    sube = np.array([0.0, 0.0, 0.4 * t.altura]) if despiece else np.zeros(3)
    baja = np.array([0.0, 0.0, -0.4 * t.altura_cono]) if despiece else np.zeros(3)
    return [_pieza(cilindro, sube), _pieza(cono, baja)]


def dibujar_tolva_3d(visual: Any, col: Any, ancho: float, alto: float, papel: str = "#FFFFFF") -> d.Dibujo:
    """La tolva de un silo: cilindro y cono truncado. Con despiece, el cilindro sube y el cono baja."""
    t = visual.tolva()
    u = t.unidad

    def m(clave: str, valor: float) -> str:
        return f"{clave} = {d._numero_latex(valor)} {u}".strip()

    medidas = [
        (m("R", t.radio), [t.radio / 2, 0.0, t.altura], 0, "arriba"),
        (m("H", t.altura), [-t.radio, 0.0, t.altura / 2], 0, "izquierda"),
        (m("h", t.altura_cono), [-(t.radio + t.radio_salida) / 2, 0.0, -t.altura_cono / 2], 1, "izquierda"),
        (m("r", t.radio_salida), [0.0, 0.0, -t.altura_cono], 1, "abajo"),
    ]
    notas = []
    if "volumen" in visual.anotar:
        notas.append(f"V = {d._numero_latex(t.volumen)} {u}³".strip())
    if "chapa" in visual.anotar:
        notas.append(f"Chapa = {d._numero_latex(t.chapa)} {u}²".strip())
    piezas = _piezas_tolva(t, visual.despiece)
    cotas = [
        (m("R", t.radio), [0, 0, t.altura], [t.radio, 0, t.altura], 0, "arriba"),
        (m("H", t.altura), [-t.radio, 0, 0], [-t.radio, 0, t.altura], 0, "izquierda"),
        (m("h", t.altura_cono), [-t.radio_salida, 0, -t.altura_cono], [-t.radio_salida, 0, 0], 1, "izquierda"),
        (m("r", t.radio_salida), [0, 0, -t.altura_cono], [t.radio_salida, 0, -t.altura_cono], 1, "abajo"),
    ]
    return _cuerpo_vivo(
        piezas, visual.vista, visual.despiece, col, ancho, alto, papel, medidas, notas, cotas=cotas,
    )


# La brida se dibuja en proporción al tubo: el guion no la mide y no entra en las cuentas.
RADIO_BRIDA = 1.55
GRUESO_BRIDA = 0.32


def _piezas_tuberia(t: Any, bridas: bool, despiece: bool) -> list[_Pieza]:
    mitad = t.longitud / 2
    piezas = [_pieza(_tubo(t.radio_interior, t.radio, -mitad, mitad), np.zeros(3), acostada=True)]
    if bridas:
        grueso = min(GRUESO_BRIDA * t.radio, 0.12 * t.longitud)
        aparte = 0.22 * t.longitud if despiece else 0.0
        rb = RADIO_BRIDA * t.radio
        piezas.append(
            _pieza(_tubo(t.radio_interior, rb, -mitad - grueso, -mitad), np.array([0, 0, -aparte]), True)
        )
        piezas.append(
            _pieza(_tubo(t.radio_interior, rb, mitad, mitad + grueso), np.array([0, 0, aparte]), True)
        )
    return piezas


def dibujar_tuberia_3d(visual: Any, col: Any, ancho: float, alto: float, papel: str = "#FFFFFF") -> d.Dibujo:
    """Un tramo de ducto hueco: por la boca se ve el interior. Con despiece, las bridas se apartan."""
    t = visual.tuberia()
    u = t.unidad

    def m(clave: str, valor: float) -> str:
        return f"{clave} = {d._numero_latex(valor)} {u}".strip()

    medidas = [
        (m("Ø", 2 * t.radio), _a_lo_largo_de_x(np.array([0.0, 0.0, -t.longitud / 4])).tolist(), 0, "arriba"),
        (m("L", t.longitud), _a_lo_largo_de_x(np.array([0.0, 0.0, 0.0])).tolist(), 0, "abajo"),
    ]
    notas = [m("e", t.espesor)]
    if "seccion" in visual.anotar:
        notas.append(f"A = {d._numero_latex(t.seccion)} {u}²".strip())
    if "material" in visual.anotar:
        notas.append(f"V = {d._numero_latex(t.material)} {u}³".strip())
    despiece = visual.despiece and visual.bridas
    piezas = _piezas_tuberia(t, visual.bridas, despiece)
    return _cuerpo_vivo(piezas, visual.vista, despiece, col, ancho, alto, papel, medidas, notas, 0.56)


def _piezas_eje(e: Any, despiece: bool) -> tuple[list[_Pieza], list[float]]:
    """Los tramos uno tras otro, centrados; devuelve también el centro de cada uno a lo largo del eje."""
    z = -e.largo / 2
    piezas, centros = [], []
    n = len(e.radios)
    for i, (r, largo) in enumerate(zip(e.radios, e.largos, strict=True)):
        aparte = (i - (n - 1) / 2) * 0.1 * e.largo if despiece else 0.0
        piezas.append(_pieza(_tramo(r, r, z, z + largo), np.array([0.0, 0.0, aparte]), acostada=True))
        centros.append(z + largo / 2)
        z += largo
    return piezas, centros


def dibujar_eje_3d(visual: Any, col: Any, ancho: float, alto: float, papel: str = "#FFFFFF") -> d.Dibujo:
    """Un eje de transmisión escalonado. Con despiece, los tramos se separan a lo largo del eje."""
    e = visual.eje()
    u = e.unidad
    piezas, centros = _piezas_eje(e, visual.despiece)
    medidas = [
        (
            f"Ø {d._numero_latex(2 * r)} {u}".strip(),
            _a_lo_largo_de_x(np.array([0.0, 0.0, zc])).tolist(),
            i,
            "arriba" if i % 2 == 0 else "abajo",
        )
        for i, (r, zc) in enumerate(zip(e.radios, centros, strict=True))
    ]
    notas = []
    if "largo" in visual.anotar:
        notas.append(f"L = {d._numero_latex(e.largo)} {u}".strip())
    if "volumen" in visual.anotar:
        notas.append(f"V = {d._numero_latex(e.volumen)} {u}³".strip())
    return _cuerpo_vivo(piezas, visual.vista, visual.despiece, col, ancho, alto, papel, medidas, notas, 0.56)


def _pliegue(cara: _Cara, vecina: _Cara) -> bool:
    """Si la arista entre dos caras visibles es un canto que se dibuja (anillo contra manto o hueco)."""
    if cara.clase == vecina.clase or "tapa" in (cara.clase, vecina.clase):
        return False
    return "anillo" in (cara.clase, vecina.clase)


def _aristas(pieza: _Pieza) -> list[tuple[int, np.ndarray, np.ndarray, int | None]]:
    """Cada arista de las caras del manto (o de la esfera) con la cara vecina que la comparte.

    Las vecinas se encuentran por coordenadas redondeadas: el anillo del manto y el de la tapa salen
    del mismo cálculo, así que la arista de abajo del manto reconoce a la base como vecina.
    """

    def clave(q: np.ndarray) -> tuple[float, ...]:
        return tuple(np.round(q, 5).tolist())

    duenos: dict[tuple, list[int]] = {}
    for i, cara in enumerate(pieza.caras):
        pts = cara.puntos
        for q0, q1 in zip(pts, np.roll(pts, -1, axis=0), strict=True):
            if float(np.linalg.norm(q1 - q0)) < 1e-9:
                continue  # el polo de la esfera: una arista sin largo
            duenos.setdefault(tuple(sorted((clave(q0), clave(q1)))), []).append(i)
    salida = []
    for i, cara in enumerate(pieza.caras):
        if cara.clase not in ("cuerpo", "anillo"):
            continue
        pts = cara.puntos
        for q0, q1 in zip(pts, np.roll(pts, -1, axis=0), strict=True):
            if float(np.linalg.norm(q1 - q0)) < 1e-9:
                continue
            otras = [j for j in duenos[tuple(sorted((clave(q0), clave(q1))))] if j != i]
            salida.append((i, q0, q1, otras[0] if otras else None))
    return salida


def dibujar_solido_3d_lamina(
    visual: Any, col: Any, ancho: float, alto: float, papel: str = "#FFFFFF"
) -> d.Dibujo:
    """El cuerpo en relieve como imagen (PNG renderizado fuera de línea), con su medida y su V y A.

    Es la lámina quieta de antes: queda para quien la pida explícitamente (y la usa el vector 3D).
    """
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


def _dimensiones(visual: Any) -> tuple[float, float, float]:
    """Las tres componentes llevadas a unidades de escena, con su signo y en proporción real.

    Un vector (3, 4, 12) es una aguja parada y un (12, 4, 3) es una losa: si la caja siempre sale
    del mismo tamaño relativo, el dibujo desmiente el número que está al lado.
    """
    v = visual.vector_3d()
    k = LARGO_CAJA / (max(abs(v.x), abs(v.y), abs(v.z)) or 1.0)
    return v.x * k, v.y * k, v.z * k


def _puntas_ejes(x: float, y: float, z: float) -> list[np.ndarray]:
    """Dónde termina cada eje: un poco más allá de su componente, para que la flecha no la tape.

    Con una componente chica (o nula) el eje igual asoma su muñón: sin los tres muñones no hay
    sistema de referencia, hay dos líneas y una flecha suelta.
    """
    minimo = 0.35 * LARGO_CAJA
    puntas = []
    for eje, valor in enumerate((x, y, z)):
        punto = np.zeros(3)
        punto[eje] = max(abs(valor) * 1.12, minimo) * (1 if valor >= 0 else -1)
        puntas.append(punto)
    return puntas


def _piezas_vector(x: float, y: float, z: float, marcas: list[str], col: Any):
    """(lo que va detrás del todo, lo que va al frente): los ejes o la caja, y el vector encima.

    Las aristas se pintan tenues y las de atrás no se borran: sin z-buffer, una caja de alambre ya
    dice dónde está cada esquina. Con la marca «ejes» el alambre se va: los tres ejes saliendo del
    origen son lo que el alumno tiene que reconocer, y la caja sobraba. Lo que hay que seguir con el
    ojo va encima, y por eso se pinta al final de todo.
    """
    detras = []
    if "ejes" in marcas:
        for punta_eje in _puntas_ejes(x, y, z):
            detras.append(
                Arrow(
                    np.array([0.0, 0.0, 0.0]),
                    punta_eje,
                    buff=0,
                    stroke_width=4,
                    color=col.tenue,
                    max_tip_length_to_length_ratio=0.22,
                )
            )
    else:
        esquinas = [np.array([sx * x, sy * y, sz * z]) for sx in (0, 1) for sy in (0, 1) for sz in (0, 1)]
        for i in range(8):
            for j in range(i + 1, 8):
                if sum(a != b for a, b in zip(esquinas[i], esquinas[j])) == 1:
                    detras.append(Line(esquinas[i], esquinas[j]).set_stroke(col.tenue, 2, 0.55))
    origen = np.array([0.0, 0.0, 0.0])
    proyeccion = np.array([x, y, 0.0])
    punta = np.array([x, y, z])
    encima = []
    if "piso" in marcas:
        # cuadricula es el color de la grilla: en la hoja de papel sale gris pálido y la diagonal
        # desaparece. El acento es el único que se impone sobre el alambre de la caja.
        encima.append(Line(origen, proyeccion).set_stroke(col.acento, 6))
    if "norma" in marcas:
        encima.append(DashedLine(proyeccion, punta, dash_length=0.14).set_stroke(col.exito, 4))
    encima.append(
        Arrow(
            origen,
            punta,
            buff=0,
            stroke_width=7,
            color=col.formulas,
            max_tip_length_to_length_ratio=0.14,
        )
    )
    return detras, encima


def _render_vector(visual: Any, col: Any, ancho: float, alto: float, papel: str) -> tuple[Path, Cuadro3D]:
    x, y, z = _dimensiones(visual)
    # Las marcas entran en la clave: con «piso» la diagonal va en el PNG y sin ella no, así que
    # servir el cuerpo viejo con otro anotar mostraría una línea que el guion no pidió.
    marcas = "+".join(visual.anotar) or "vector"
    destino = _ruta_cache("vector_3d", "axonometrica", marcas, x, y, z, col, papel, aspect=alto / ancho)
    phi, theta = VISTAS["axonometrica"]
    if ancho >= alto:
        marco_alto, marco_ancho = LARGO_MARCO, LARGO_MARCO * ancho / alto
    else:
        marco_ancho, marco_alto = LARGO_MARCO, LARGO_MARCO * alto / ancho
    alto_px = int(round(PX * alto / ancho))
    # La cámara y el encuadre se arman siempre, haya o no PNG en cache: las letras de los ejes se
    # anclan proyectando sobre esta misma cámara, y construirlos cuesta milisegundos contra capturar.
    camara = _camara(phi, theta, marco_ancho, marco_alto, alto_px, papel)
    detras, encima = _piezas_vector(x, y, z, list(visual.anotar), col)
    centro, factor = _encuadrar(camara, VGroup(*detras, *encima), marco_ancho, marco_alto)
    lado = destino.with_suffix(".json")
    if destino.exists() and lado.exists():
        recorte = tuple(json.loads(lado.read_text(encoding="utf-8"))["recorte"])
        return destino, Cuadro3D(camara, PX, alto_px, marco_ancho, marco_alto, recorte, centro, factor)

    for m in VGroup(*detras).get_family():
        camara.capture_mobject(m)
    for m in VGroup(*encima).get_family():
        camara.capture_mobject(m)
    imagen = camara.get_image()
    rgba, recorte = _png_transparente(
        np.array(imagen.convert("RGB")), _rgb(papel), _rgb(col.formulas), con_contorno=False
    )
    Image.fromarray(rgba, "RGBA").save(destino)
    # El recorte se guarda junto al PNG: si cambia el encuadre, el archivo viejo ya no sirve.
    lado.write_text(json.dumps({"recorte": list(recorte)}), encoding="utf-8")
    return destino, Cuadro3D(camara, PX, alto_px, marco_ancho, marco_alto, recorte, centro, factor)


def dibujar_vector_3d(visual: Any, col: Any, ancho: float, alto: float, papel: str = "#FFFFFF") -> d.Dibujo:
    """El vector con punta sobre sus tres ejes (o su caja), la diagonal del piso y la subida.

    Las medidas van pegadas al cuerpo; con la marca «ejes» además salen las letras x, y, z en la punta
    de cada eje, que es lo que hace que se lea como un sistema de referencia y no como un dibujo raro.
    """
    ruta, cuadro = _render_vector(visual, col, ancho, alto, papel)
    imagen = ImageMobject(str(ruta))
    cuerpo = visual.vector_3d()
    unidad = cuerpo.unidad or ""

    # (clave, valor, columna, altura relativa) — el orden de la lista es el orden en que aparecen.
    filas = [("x", cuerpo.x, True, 0.30), ("y", cuerpo.y, True, 0.00), ("z", cuerpo.z, True, -0.30)]
    if "piso" in visual.anotar:
        filas.append(("piso", cuerpo.piso, False, -0.30))
    if "norma" in visual.anotar:
        filas.append(("v", cuerpo.norma, False, 0.30))
    rótulos = []
    for clave, valor, izquierda, _ in filas:
        texto = f"{clave} = {d._numero_latex(valor)} {unidad}".strip()
        rótulos.append(c.texto(texto, 24 if izquierda else 26, c.SEMIBOLD, col.texto))

    # El cuerpo llena el alto de la franja: en el video la franja mide ~2 unidades y con el 80 % de
    # OBJETIVO la caja quedaba como un juguete perdido en medio de la hoja.
    imagen.scale(min(0.94 * alto / imagen.height, ancho / imagen.width))
    imagen.move_to(ORIGIN)

    parches, columna = VGroup(), VGroup()
    # El hueco y el cartón salen del presupuesto, no del gusto: el dibujo anotado tiene que caber en
    # 0,75 de la franja y en una aguja (3, 4, 12) el cuerpo es angosto, así que lo que manda es el
    # texto. Con el cuerpo y las dos columnas ya adentro sólo quedan ~0,34 para los dos lados juntos,
    # y subir cualquiera de estos dos números a ojo saca el dibujo del presupuesto.
    hueco_columna = 0.10
    carton = 0.08
    for rotulo, (_, _, izquierda, y) in zip(rótulos, filas):
        # Las columnas pegan al cuerpo, no al borde de la franja: en una aguja (3, 4, 12) el hueco de
        # tres unidades entre la caja y su propia medida se lee como si fueran dos dibujos distintos.
        # Se miden contra la franja de dibujo, no contra el frame de manim: la miniatura y el video
        # usan cuadros distintos y to_edge() correría las columnas según dónde se llame.
        hueco = imagen.width / 2 + hueco_columna
        centro = -(hueco + rotulo.width / 2) if izquierda else hueco + rotulo.width / 2
        rotulo.move_to([centro, y * alto, 0.0])
        fondo, rotulo = d._parche(rotulo, papel, carton)  # el mismo cartón que usa la lámina 2D
        parches.add(fondo)
        columna.add(rotulo)

    if "ejes" in visual.anotar:
        # Las letras del sistema ancladas a la punta de cada eje: sin ellas son tres flechas grises
        # y el alumno no sabe cuál es la x. Se proyectan sobre la misma cámara que pintó el PNG.
        escala = imagen.width / cuadro.recorte[2]  # unidades de escena por píxel del PNG recortado

        def en_escena(punto: np.ndarray) -> np.ndarray:
            px, py = cuadro.pixeles(punto)
            return np.array(
                [(px - cuadro.recorte[2] / 2) * escala, (cuadro.recorte[3] / 2 - py) * escala, 0.0]
            )

        raiz = en_escena(np.zeros(3))
        for nombre, punta_eje in zip(("x", "y", "z"), _puntas_ejes(*_dimensiones(visual))):
            sitio = en_escena(punta_eje)
            direccion = sitio - raiz
            norma = float(np.linalg.norm(direccion[:2])) or 1.0
            rotulo = c.texto(nombre, 22, c.SEMIBOLD, col.tenue)
            rotulo.move_to(sitio + 0.30 * direccion / norma)  # asoma más allá de la punta, no encima
            fondo, rotulo = d._parche(rotulo, papel, 0.10)
            parches.add(fondo)
            columna.add(rotulo)

    todo = Group(imagen, parches, columna)  # ImageMobject es raster: no entra en un VGroup
    todo.move_to(ORIGIN)
    todo = d._encajar(todo, ancho * 0.94, alto * 0.94)
    return d.Dibujo(mobs=todo, trazo=[], aparece=[imagen, *columna])
