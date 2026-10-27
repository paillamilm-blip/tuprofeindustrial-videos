import unittest
from pathlib import Path

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:
    MANIM = False

from tpi_videos.componentes import marco_hoja
from tpi_videos.config import cargar_marca
from tpi_videos.temas import cargar_tema


@unittest.skipUnless(MANIM, "manim no esta instalado")
class HojaTest(unittest.TestCase):
    def _etiqueta(self, tema):
        marco = marco_hoja(tema)
        buscado = tema.hoja.etiqueta.strip()
        self.assertTrue(buscado, "el tema no pone etiqueta: nada que probar")
        return next(m for m in marco.get_family() if getattr(m, "text", "") == buscado)

    def test_sobre_fondo_oscuro_la_etiqueta_clarea(self):
        """El fondo de «hoja_de_desarrollo» es casi negro: la etiqueta va en el color del papel."""
        tema = cargar_tema("hoja_de_desarrollo", cargar_marca())
        self.assertEqual(str(self._etiqueta(tema).color).upper(), tema.hoja.color.upper())

    def test_sobre_fondo_claro_la_etiqueta_usa_el_tenue(self):
        """En papel claro el blanco desaparecía: «rotulador» tiene fondo #E9E7DF."""
        tema = cargar_tema("rotulador", cargar_marca())
        claro = tema.model_copy(update={"hoja": tema.hoja.model_copy(update={"etiqueta": "Clase"})})
        self.assertNotEqual(str(self._etiqueta(claro).color).upper(), "#FFFFFF")
        self.assertEqual(str(self._etiqueta(claro).color).upper(), tema.colores.tenue.upper())


class BordeSubtituloTest(unittest.TestCase):
    def _linea_estilo(self, tema) -> str:
        from tpi_videos.subtitulos import Palabra, escribir_ass

        ruta = Path("/tmp/borde_prueba.ass")
        escribir_ass([[Palabra(texto="Hola", inicio=0.0, fin=0.5)]], ruta, tema.subtitulos)
        return next(
            linea
            for linea in ruta.read_text(encoding="utf-8").splitlines()
            if linea.startswith("Style: CapCut")
        )

    def test_el_borde_del_subtitulo_usa_el_color_del_tema(self):
        tema = cargar_tema("kraft_claro", cargar_marca())
        tema.subtitulos = tema.subtitulos.model_copy(update={"color": "#2B2B2B", "color_borde": "#FBF7EC"})
        self.assertEqual(self._borde(self._linea_estilo(tema)), "&H00ECF7FB")  # &HAABBGGRR de #FBF7EC

    def test_sin_color_borde_sigue_saliendo_negro(self):
        from tpi_videos.config import EstiloSubtitulos

        class _Tema:
            subtitulos = EstiloSubtitulos()

        self.assertEqual(self._borde(self._linea_estilo(_Tema())), "&H00000000")

    @staticmethod
    def _borde(linea_estilo: str) -> str:
        """OutlineColour: Name, Fontname, Fontsize, Primary, Secondary, OUTLINE, Back…"""
        return [c.strip() for c in linea_estilo.split(",")][5]

    def test_los_temas_de_papel_claro_no_usan_borde_negro(self):
        """Seis temas tienen el fondo claro y el subtítulo oscuro: ahí el negro embarra."""
        from tpi_videos.temas import listar_temas

        claros = {
            "comic_azul",
            "cuaderno_con_sello",
            "cuaderno_tinta_roja",
            "kraft_claro",
            "rotulador",
            "rotulador_fucsia",
        }
        for ident, _, _ in listar_temas():
            if ident in claros:
                tema = cargar_tema(ident, cargar_marca())
                self.assertNotEqual(tema.subtitulos.color_borde, "#000000", ident)
                self.assertEqual(tema.subtitulos.color_borde.upper(), tema.colores.fondo.upper(), ident)


class LetrasTest(unittest.TestCase):
    def test_el_panel_ofrece_todas_las_letras_del_motor(self):
        from tpi_videos.tipografia import FAMILIAS, PARA_TEXTO, PARA_TITULOS

        self.assertEqual(set(PARA_TITULOS), set(FAMILIAS))
        self.assertEqual(set(PARA_TEXTO), set(FAMILIAS))
        for extra in ("Bangers", "Luckiest Guy", "Cinzel"):
            self.assertIn(extra, PARA_TITULOS)

    def test_ningun_tema_pide_una_letra_que_el_motor_no_trae(self):
        from tpi_videos.config import cargar_marca
        from tpi_videos.temas import cargar_tema, listar_temas
        from tpi_videos.tipografia import existe

        marca = cargar_marca()
        for ident, _, _ in listar_temas():
            tema = cargar_tema(ident, marca)
            self.assertTrue(existe(tema.tipografia.titulos.familia), f"{ident} titulos")
            self.assertTrue(existe(tema.tipografia.texto.familia), f"{ident} texto")


class PielTest(unittest.TestCase):
    """La piel del panel: los colores viven en un solo diccionario, no repartidos por las páginas."""

    def test_los_tokens_de_la_piel_existen_y_son_hex(self):
        from tpi_videos.panel.comun import PIEL

        for clave in (
            "muro",
            "tarjeta",
            "borde_muro",
            "texto_muro",
            "tenue_muro",
            "hoja",
            "tinta",
            "marca",
            "error",
            "exito",
            "gris",
            "costado_px",
        ):
            self.assertIn(clave, PIEL, clave)
        for clave, valor in PIEL.items():
            if clave.endswith("_px"):
                self.assertRegex(valor, r"^\d+$", clave)
            else:
                self.assertRegex(valor, r"^#[0-9A-Fa-f]{6}$", clave)

    def test_no_quedan_hexadecimales_sueltos_en_el_css_del_panel(self):
        import re

        fuente = Path("src/tpi_videos/panel/comun.py").read_text(encoding="utf-8")
        self.assertNotIn("AZUL = ", fuente)
        sueltos = re.findall(r"background:\s*#[0-9A-Fa-f]{6}", fuente)
        self.assertEqual(sueltos, [], f"colores escritos a mano: {sueltos}")

    def test_ningun_archivo_del_panel_usa_las_constantes_viejas(self):
        import re

        viejas = re.compile(r"\b(AZUL|ROJO|VERDE|GRIS)\b")
        raiz = Path("src/tpi_videos/panel")
        tocados = [
            str(p.relative_to(raiz))
            for p in sorted(raiz.rglob("*.py"))
            if viejas.search(p.read_text(encoding="utf-8"))
        ]
        self.assertEqual(tocados, [], f"todavía nombran una constante suelta: {tocados}")


if __name__ == "__main__":
    unittest.main()
