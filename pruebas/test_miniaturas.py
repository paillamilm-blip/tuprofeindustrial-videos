"""La miniatura del dibujo: un fotograma encuadrado, cacheado por huella, sin voz y sin IA."""

import unittest
from pathlib import Path

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:
    MANIM = False

from tpi_videos.panel.miniaturas import dibujar_miniatura, marco_para, ruta_miniatura
from tpi_videos.visuales import VISUALES


class EncuadreTest(unittest.TestCase):
    def test_el_marco_9a16_contiene_un_dibujo_ancho(self):
        ancho, alto = marco_para(6.0, 2.0)
        self.assertAlmostEqual(alto / ancho, 16 / 9, places=5)
        self.assertGreaterEqual(ancho, 6.0)
        self.assertGreaterEqual(alto, 2.0)

    def test_el_marco_9a16_contiene_un_dibujo_alto(self):
        ancho, alto = marco_para(1.0, 5.0)
        self.assertGreaterEqual(alto, 5.0)
        self.assertAlmostEqual(alto / ancho, 16 / 9, places=5)

    def test_dibujo_degenerado_no_rompe_el_marco(self):
        ancho, alto = marco_para(0.0, 0.0)
        self.assertGreater(ancho, 0)
        self.assertGreater(alto, 0)


@unittest.skipUnless(MANIM, "manim no esta instalado")
class DibujarTest(unittest.TestCase):
    def _ocupacion(self, ruta: Path) -> tuple[float, float]:
        """Cuánto del ancho y del alto del cuadro ocupa la tinta. En un retrato 9:16 un dibujo ancho
        llena el ancho y no el alto: medir solo el alto condenaría a la mitad del catálogo."""
        from PIL import Image

        im = Image.open(ruta).convert("L")
        fondo = im.getpixel((2, 2))

        def tinta(i: int, eje: str) -> bool:
            paso = range(im.height) if eje == "x" else range(im.width)
            puntos = ((i, y) for y in paso) if eje == "x" else ((x, i) for x in paso)
            return any(abs(im.getpixel(p) - fondo) > 24 for p in puntos)

        columnas = [x for x in range(im.width) if tinta(x, "x")]
        filas = [y for y in range(im.height) if tinta(y, "y")]
        if len(columnas) < 3 or len(filas) < 3:
            return (0.0, 0.0)
        return (
            (columnas[-1] - columnas[0]) / im.width,
            (filas[-1] - filas[0]) / im.height,
        )

    def test_tipos_de_ejemplo_producen_un_png_usable(self):
        for clave in ("engranaje", "poligono_regular", "viga", "torta", "mohr", "solido"):
            ruta = dibujar_miniatura({"tipo": clave, **VISUALES[clave].ejemplo})
            self.assertTrue(ruta.exists(), clave)
            ancho, alto = self._ocupacion(ruta)
            # La dimensión que manda (la de mayor ocupación) tiene que llenar el cuadro: medido en los
            # 24 dibujos, ninguna baja de 0,68. Una recta numérica es ancha y delgada por naturaleza.
            self.assertGreater(
                max(ancho, alto), 0.65, f"{clave} llega muy chico: {ancho:.2f} x {alto:.2f} — {ruta}"
            )

    def test_la_huella_repite_archivo_si_no_cambia_nada(self):
        v = {"tipo": "barras", "categorias": ["A 3", "B 5"]}
        primera = dibujar_miniatura(v)
        self.assertEqual(primera, ruta_miniatura(v))
        self.assertEqual(primera.stat().st_mtime, dibujar_miniatura(v).stat().st_mtime)

    def test_un_tipo_inventado_avisa_en_vez_de_devolver_nada(self):
        with self.assertRaises(Exception) as sube:
            dibujar_miniatura({"tipo": "dibujo_imposible"})
        self.assertIn("dibujo_imposible", str(sube.exception))


if __name__ == "__main__":
    unittest.main()
