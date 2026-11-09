"""El vector metido en una caja: su sombra en el piso y su largo, con dos Pitágoras seguidos.

La idea que tiene que sostener el video: el largo de un vector en el espacio no sale de una fórmula
nueva, sale de dos triángulos rectángulos que se ven uno encima del otro.
"""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.visuales import MARCAS_VECTOR_3D, VISUALES, analizar_vector_3d

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:
    MANIM = False


class Vector3DTest(unittest.TestCase):
    def test_la_sombra_en_el_piso_es_el_primer_pitagoras(self):
        self.assertAlmostEqual(analizar_vector_3d([3, 4, 12]).piso, 5.0)

    def test_el_largo_del_vector_es_el_segundo_pitagoras(self):
        self.assertAlmostEqual(analizar_vector_3d([3, 4, 12]).norma, 13.0)

    def test_la_sombra_se_mide_sin_mirar_la_altura(self):
        # 3 y 4 son la base apoyada en el piso; el 12 entra recién en el segundo triángulo
        self.assertAlmostEqual(
            analizar_vector_3d([3, 4, 12]).piso, analizar_vector_3d([3, 4, 99]).piso
        )

    def test_una_componente_negativa_no_acorta_el_vector(self):
        self.assertAlmostEqual(analizar_vector_3d([-3, 4, 12]).norma, 13.0)

    def test_lleva_la_unidad_que_escribio_el_guion(self):
        self.assertEqual(analizar_vector_3d([3, 4, 12], unidad="m").unidad, "m")

    def test_sin_tres_componentes_lo_dice_en_espanol(self):
        with self.assertRaises(ValueError) as sube:
            analizar_vector_3d([3, 4])
        self.assertIn("tres componentes", str(sube.exception))

    def test_una_componente_que_no_es_numero_tambien_lo_dice_en_espanol(self):
        with self.assertRaises(ValueError) as sube:
            analizar_vector_3d([3, "cuatro", 12])
        self.assertIn("número", str(sube.exception))

    def test_el_vector_cero_no_se_dibuja(self):
        """(0, 0, 0) no tiene flecha ni caja: sin guarda salía una figura degenerada."""
        with self.assertRaises(ValueError) as sube:
            analizar_vector_3d([0, 0, 0])
        self.assertIn("(0, 0, 0)", str(sube.exception))


class ElGuionPideUnVectorTest(unittest.TestCase):
    """Que el guion pueda decir «vector_3d» y que el catálogo lo ofrezca con un ejemplo que funcione."""

    def test_trae_las_tres_componentes_con_su_unidad(self):
        visual = Visual(tipo="vector_3d", componentes=[3, 4, 12], unidad="m", anotar=list(MARCAS_VECTOR_3D))
        self.assertAlmostEqual(visual.vector_3d().piso, 5.0)
        self.assertAlmostEqual(visual.vector_3d().norma, 13.0)
        self.assertEqual(visual.vector_3d().unidad, "m")

    def test_sin_componentes_el_error_habla_del_vector(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="vector_3d", unidad="m")
        self.assertIn("componentes", str(error.exception))

    def test_una_marca_que_no_existe_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="vector_3d", componentes=[3, 4, 12], anotar=["seno"])
        self.assertIn("seno", str(error.exception))

    def test_pide_los_tres_ejes_coordenados(self):
        """"Ejes" es lo que él pidió: la flecha saliendo del origen con su x, su y y su z, no la caja."""
        visual = Visual(tipo="vector_3d", componentes=[3, 4, 12], anotar=["ejes", "piso", "norma"])
        self.assertIn("ejes", MARCAS_VECTOR_3D)
        self.assertEqual(list(visual.anotar), ["ejes", "piso", "norma"])

    def test_el_ejemplo_del_catalogo_es_un_guion_valido(self):
        """El panel y el redactor muestran ese ejemplo: si no valida, el tipo nuevo llega roto a pantalla."""
        visual = Visual(**{"tipo": "vector_3d", **VISUALES["vector_3d"].ejemplo})
        self.assertGreater(visual.vector_3d().norma, 0)


class ElYamlGuardaElVectorTest(unittest.TestCase):
    """El panel reescribe el guion con _visual_yaml: si no conoce el tipo, deja el visual vacío."""

    def test_el_yaml_guarda_las_tres_componentes_y_su_unidad(self):
        texto = "\n".join(
            _visual_yaml({"tipo": "vector_3d", "componentes": [3, 4, 12], "unidad": "cm", "anotar": ["piso"]})
        )
        self.assertIn("componentes: [3, 4, 12]", texto)
        self.assertIn("unidad: 'cm'", texto)
        self.assertIn("anotar: ['piso']", texto)


def _vector(componentes, anotar=("piso", "norma"), unidad="cm"):
    return Visual(tipo="vector_3d", componentes=list(componentes), unidad=unidad, anotar=list(anotar))


@unittest.skipUnless(MANIM, "manim no está instalado")
class ElDibujoDelVectorTest(unittest.TestCase):
    """Lo que tiene que verse: la caja, su diagonal apoyada en el piso y el vector saliendo del origen."""

    def _textos(self, visual):
        from tpi_videos.componentes import ANCHO_UTIL
        from tpi_videos.config import cargar_marca
        from tpi_videos.dibujos import ALTO_DIBUJO, dibujar_visual
        from tpi_videos.temas import cargar_tema

        col = cargar_tema("hoja_de_desarrollo", cargar_marca()).colores
        papel = cargar_tema("hoja_de_desarrollo", cargar_marca()).hoja.color
        dibujo = dibujar_visual(visual, col, ANCHO_UTIL, ALTO_DIBUJO, papel)
        # manim guarda Text sin espacios («x = 3 cm» → «x=3cm»): se compara igual, sin espacios.
        return [m.text for m in dibujo.mobs.get_family() if hasattr(m, "text")], dibujo

    def test_las_tres_componentes_y_las_dos_longitudes_estan_escritas(self):
        textos, _ = self._textos(_vector([3, 4, 12]))
        for falta in ("x=3", "y=4", "z=12", "piso=5", "v=13"):
            self.assertTrue(any(falta in t for t in textos), f"falta «{falta}» en {textos}")

    def test_sin_la_marca_piso_no_sale_su_longitud(self):
        textos, _ = self._textos(_vector([3, 4, 12], anotar=["norma"]))
        self.assertFalse(any("piso" in t for t in textos), textos)
        self.assertTrue(any("v=13" in t for t in textos), textos)

    def test_la_unidad_del_guion_llega_a_los_rotulos(self):
        textos, _ = self._textos(_vector([3, 4, 12], unidad="m"))
        self.assertTrue(any("=13m" in t for t in textos), textos)
        self.assertFalse(any("=13cm" in t for t in textos), textos)

    def test_con_la_marca_ejes_no_hay_caja_sino_tres_flechas(self):
        """El esqueleto de 12 aristas se cambia por los tres ejes: es lo que él pidió ver."""
        import manim

        from tpi_videos.config import cargar_marca
        from tpi_videos.dibujos_3d import _piezas_vector
        from tpi_videos.temas import cargar_tema

        col = cargar_tema("hoja_de_desarrollo", cargar_marca()).colores
        detras, _ = _piezas_vector(1.0, 1.33, 4.0, ["ejes"], col)
        self.assertEqual(len([m for m in detras if isinstance(m, manim.Arrow)]), 3, "los tres ejes")
        self.assertEqual(len([m for m in detras if not isinstance(m, manim.Arrow)]), 0, "sin caja")
        caja, _ = _piezas_vector(1.0, 1.33, 4.0, [], col)
        self.assertEqual(len(caja), 12, "sin la marca sigue siendo la caja de alambre")

    def test_los_tres_ejes_estan_nombrados_en_la_lamina(self):
        textos, _ = self._textos(_vector([3, 4, 12], anotar=["ejes"]))
        self.assertEqual({t for t in textos if t in {"x", "y", "z"}}, {"x", "y", "z"}, textos)


@unittest.skipUnless(MANIM, "manim no está instalado")
class ElVectorNoSeSaleDelCuadroTest(unittest.TestCase):
    """Un vector 12:1:1 es una aguja vertical: si el encuadre se arma para la caja, la flecha y los
    rótulos toca el borde y se corta en el video. Es el defecto que no se ve en el log del render."""

    def _cuadro(self, visual):
        from manim import Camera, tempconfig

        from tpi_videos.componentes import ANCHO_UTIL
        from tpi_videos.config import cargar_marca
        from tpi_videos.dibujos import ALTO_DIBUJO, dibujar_visual
        from tpi_videos.temas import cargar_tema

        col = cargar_tema("hoja_de_desarrollo", cargar_marca()).colores
        papel = cargar_tema("hoja_de_desarrollo", cargar_marca()).hoja.color
        dibujo = dibujar_visual(visual, col, ANCHO_UTIL, ALTO_DIBUJO, papel)
        with tempconfig(
            {
                "pixel_width": 950,
                "pixel_height": 412,
                "frame_width": ANCHO_UTIL,
                "frame_height": ALTO_DIBUJO,
                "background_color": papel,
                "verbosity": "ERROR",
                "disable_caching": True,
            }
        ):
            camara = Camera()
            camara.capture_mobject(dibujo.mobs)
            return camara.get_image().convert("RGB")

    def test_formas_extremas_dejan_aire_en_el_borde(self):
        for componentes in ([3, 4, 12], [12, 3, 4], [1, 1, 1], [12, 12, 1], [-3, 4, 12], [1, 12, 12]):
            img = self._cuadro(_vector(componentes))
            px = list(img.getdata())
            fondo = img.getpixel((2, 2))
            tintados = [
                (x, y)
                for y in range(img.height)
                for x in range(0, img.width, 2)
                if sum(abs(a - b) for a, b in zip(px[y * img.width + x], fondo, strict=False)) > 60
            ]
            crudo = "; ".join(str(c) for c in componentes)
            self.assertTrue(tintados, f"el vector {crudo} salió en blanco")
            xs = [p[0] for p in tintados]
            ys = [p[1] for p in tintados]
            margen_x = min(min(xs), img.width - 1 - max(xs)) / img.width
            margen_y = min(min(ys), img.height - 1 - max(ys)) / img.height
            self.assertGreater(margen_x, 0.02, f"el vector {crudo} toca el borde izquierdo/derecho")
            self.assertGreater(margen_y, 0.02, f"el vector {crudo} toca el borde arriba/abajo")

    def test_la_caja_llena_la_altura_de_la_franja(self):
        """En el video la franja mide ~2 unidades: si el cuerpo ocupara solo el 80 %, la caja se ve
        como un juguete en medio de la hoja. La caja tiene que llenarla."""
        from tpi_videos.componentes import ANCHO_UTIL
        from tpi_videos.config import cargar_marca
        from tpi_videos.dibujos import ALTO_DIBUJO, dibujar_visual
        from tpi_videos.temas import cargar_tema

        col = cargar_tema("hoja_de_desarrollo", cargar_marca()).colores
        papel = cargar_tema("hoja_de_desarrollo", cargar_marca()).hoja.color
        for anotar in ([], ["ejes", "piso", "norma"]):
            dibujo = dibujar_visual(_vector([3, 4, 12], anotar=anotar), col, ANCHO_UTIL, ALTO_DIBUJO, papel)
            crudo = ", ".join(anotar) or "sin marcas"
            self.assertGreaterEqual(dibujo.mobs.height, 0.90 * ALTO_DIBUJO, f"chico con {crudo}")


    def test_los_rotulos_pegan_al_cuerpo_en_vez_de_huir_a_los_bordes(self):
        """Una aguja (3,4,12) proyecta una caja angosta: con los rótulos clavados en el borde de la
        franja quedan tres islas separadas. Compacto = se lee como un solo dibujo anotado."""
        from tpi_videos.componentes import ANCHO_UTIL
        from tpi_videos.config import cargar_marca
        from tpi_videos.dibujos import ALTO_DIBUJO, dibujar_visual
        from tpi_videos.temas import cargar_tema

        col = cargar_tema("hoja_de_desarrollo", cargar_marca()).colores
        papel = cargar_tema("hoja_de_desarrollo", cargar_marca()).hoja.color
        dibujo = dibujar_visual(_vector([3, 4, 12]), col, ANCHO_UTIL, ALTO_DIBUJO, papel)
        self.assertLessEqual(dibujo.mobs.width, 0.75 * ANCHO_UTIL)


@unittest.skipUnless(MANIM, "manim no está instalado")
class LaCacheSabeDeAspectosTest(unittest.TestCase):
    def _col(self, exito="#555555"):
        from types import SimpleNamespace

        return SimpleNamespace(
            tenue="#111111", cuadricula="#222222", acento="#333333", formulas="#444444", exito=exito
        )

    def test_dos_bandas_distintas_no_comparten_png(self):
        """El PNG se pinta con la proporción de la banda: servir el viejo en una banda más alta
        descalibra las letras de los ejes, que se anclan proyectando sobre la cámara nueva."""
        from tpi_videos.dibujos_3d import _ruta_cache

        args = ("vector_3d", "axonometrica", "ejes", 3.0, 4.0, 12.0, self._col(), "#FFFFFF")
        self.assertNotEqual(_ruta_cache(*args, aspect=0.43), _ruta_cache(*args, aspect=0.57))

    def test_dos_colores_de_exito_no_comparten_png(self):
        """La línea de «norma» va pintada con `exito` dentro de la imagen: si no entra en la
        huella, cambiar de estilo sirve el PNG viejo con el color del estilo anterior."""
        from tpi_videos.dibujos_3d import _ruta_cache

        args = ("vector_3d", "axonometrica", "norma", 3.0, 4.0, 12.0)
        verde = _ruta_cache(*args, self._col("#22C55E"), "#FFFFFF", aspect=0.43)
        azul = _ruta_cache(*args, self._col("#2563EB"), "#FFFFFF", aspect=0.43)
        self.assertNotEqual(verde, azul)

