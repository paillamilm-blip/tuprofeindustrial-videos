import unittest

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:
    MANIM = False

from PIL import Image

from tpi_videos.componentes import ANCHO_UTIL
from tpi_videos.config import cargar_marca
from tpi_videos.dibujos import ALTO_DIBUJO, dibujar_visual
from tpi_videos.guion import Visual
from tpi_videos.temas import cargar_tema
from tpi_videos.visuales import SOLIDOS, VISUALES

COLORES = cargar_tema("hoja_de_desarrollo", cargar_marca()).colores
PAPEL = cargar_tema("hoja_de_desarrollo", cargar_marca()).hoja.color


def _visual(figura, vista, corte="sin_corte"):
    datos = dict(VISUALES["solido_3d"].ejemplo)
    datos.update({"tipo": "solido_3d", "figura": figura, "vista": vista, "corte": corte})
    if figura == "cubo":
        datos.pop("radio", None)
        datos.pop("altura", None)
        datos["lado"] = "4 cm"
    if figura == "esfera":
        datos.pop("altura", None)
    return Visual.model_validate(datos)


@unittest.skipUnless(MANIM, "manim no está instalado")
class LasDieciseisCombinacionesTest(unittest.TestCase):
    """El encuadre es el defecto que hay que evitar: un cuerpo que toca el borde del cuadro se ve
    cortado en el video y nadie se da cuenta mirando el log del render."""

    def _cuadro(self, visual):
        """El mismo camino de 2 líneas de la miniatura: dibujar_visual + Camera a 7,6 x 3,3."""
        from manim import Camera, tempconfig

        dibujo = dibujar_visual(visual, COLORES, ANCHO_UTIL, ALTO_DIBUJO, PAPEL)
        with tempconfig(
            {
                "pixel_width": 950,
                "pixel_height": 412,
                "frame_width": ANCHO_UTIL,
                "frame_height": ALTO_DIBUJO,
                "background_color": PAPEL,
                "verbosity": "ERROR",
                "disable_caching": True,
            }
        ):
            camara = Camera()
            camara.capture_mobject(dibujo.mobs)
            return camara.get_image()

    def test_ninguna_combinacion_toca_el_borde_y_todas_dejan_cuerpo(self):
        for figura in SOLIDOS:
            for vista in ("frente", "ala", "piso", "axonometrica"):
                im = self._cuadro(_visual(figura, vista))
                img = im.convert("RGB")
                px = list(img.getdata())
                fondo = img.getpixel((2, 2))
                tintados = [
                    (x, y)
                    for y in range(img.height)
                    for x in range(0, img.width, 2)
                    if sum(abs(a - b) for a, b in zip(px[y * img.width + x], fondo, strict=False)) > 60
                ]
                self.assertTrue(tintados, f"{figura}/{vista} salió en blanco")
                xs = [p[0] for p in tintados]
                ys = [p[1] for p in tintados]
                margen_x = min(min(xs), img.width - 1 - max(xs)) / img.width
                margen_y = min(min(ys), img.height - 1 - max(ys)) / img.height
                self.assertGreater(margen_x, 0.02, f"{figura}/{vista} toca el borde izquierdo/derecho")
                self.assertGreater(margen_y, 0.02, f"{figura}/{vista} toca el borde arriba/abajo")
                self.assertGreater(len(tintados) / (img.width * img.height / 2), 0.03, f"{figura}/{vista}")

    def test_frente_y_piso_no_salen_con_la_misma_silueta(self):
        """phi en Manim se mide desde el cenit: con las vistas invertidas el cilindro de frente sale
        un círculo (la vista de arriba) y ninguna prueba de márgenes lo agarra. Se mide el PNG del
        cuerpo solo, sin rótulos, sobre un cilindro esbelto: el alzado es alto y angosto, la planta
        un disco. Con el r=3 h=5 del ejemplo ambas vistas dan casi cuadrada y no distingue nada."""
        from tpi_videos.dibujos_3d import _render

        def silueta(vista):
            datos = dict(VISUALES["solido_3d"].ejemplo)
            datos.update(
                {"tipo": "solido_3d", "figura": "cilindro", "radio": "1 cm", "altura": "4 cm", "vista": vista}
            )
            ruta, _ = _render(Visual.model_validate(datos), COLORES, ANCHO_UTIL, ALTO_DIBUJO, PAPEL)
            x0, y0, x1, y1 = Image.open(ruta).getchannel("A").getbbox()
            return (x1 - x0) / (y1 - y0)

        frente, piso = silueta("frente"), silueta("piso")
        self.assertLess(frente, 0.7, f"de frente el cilindro esbelto es un rectángulo alto: {frente}")
        self.assertGreater(piso, 0.9, f"desde arriba el cilindro es un disco: {piso}")

    def test_el_corte_del_cubo_pinta_la_cara_en_acento(self):
        im = self._cuadro(_visual("cubo", "axonometrica", corte="mitad")).convert("RGB")
        acento = tuple(int(str(COLORES.acento).lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
        encontrados = sum(
            1
            for y in range(0, im.height, 3)
            for x in range(0, im.width, 3)
            if sum(abs(a - b) for a, b in zip(im.getpixel((x, y)), acento, strict=False)) < 40
        )
        self.assertGreater(encontrados, 200, "la cara del corte no se ve sombreada en el color de acento")
