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

    def test_la_cinta_se_puede_disolver_con_la_camara(self):
        """La escena la apaga al acercarse: si fuera un Group, la opacidad no bajaría a los hijos."""
        tema = cargar_tema("hoja_de_desarrollo", cargar_marca())
        cinta = marco_hoja(tema).cinta
        self.assertTrue(len(cinta))
        cinta.set_opacity(0.0)
        self.assertEqual({m.get_fill_opacity() for m in cinta.get_family()}, {0.0})


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


class PortadaTest(unittest.TestCase):
    """«Mis videos» nunca muestra un cuadro gris: si falta el fotograma, se arma la portada con el gancho."""

    def test_sin_cuadro_del_video_se_arma_una_portada_con_el_gancho(self):
        from PIL import Image

        from tpi_videos.panel.biblioteca import portada_de_reserva

        destino = Path("/tmp/portada_reserva.png")
        destino.unlink(missing_ok=True)
        ruta = portada_de_reserva("¿Pitágoras era a + b = c?", "#0B1220", "#F8FAFC", destino)
        self.assertTrue(ruta.exists())
        im = Image.open(ruta)
        self.assertEqual(im.size[0] * 16, im.size[1] * 9)  # 9:16 de verdad
        gris = im.convert("L")
        self.assertGreater(len({p for p in gris.getdata() if p > 40}), 1, "la portada no tiene tinta")

    def test_un_titulo_bajado_no_rompe_la_portada(self):
        from tpi_videos.panel.biblioteca import portada_de_reserva

        self.assertTrue(portada_de_reserva("", "#FFFFFF", "#000000", Path("/tmp/portada_vacia.png")).exists())

    def test_la_clave_del_estilo_viaja_en_la_linea_de_tiempo(self):
        """El nombre visible no sirve para cargar los colores: hace falta la clave con la que se creó."""
        fuente = Path("src/tpi_videos/render.py").read_text(encoding="utf-8")
        self.assertIn('"tema_clave"', fuente)

    def test_un_video_sin_miniatura_devuelve_la_portada_de_reserva(self):
        from tpi_videos.panel import biblioteca

        video = biblioteca.Video(
            carpeta=Path("/tmp/sin_miniatura"),
            titulo="Un gancho cualquiera",
            tema="Neón cian",
            tema_clave=None,
            materia="",
            molde="",
            duracion=0.0,
            fecha=0.0,
            final=None,
            borrador=None,
            guion=None,
            kit=None,
        )
        self.assertTrue(biblioteca.miniatura(video))


class MuroDeVideosTest(unittest.TestCase):
    """Buscador, filtro y grilla: la pila de 24 tarjetas se vuelve un muro que se recorre de un vistazo."""

    def _video(self, titulo: str, materia: str, borrador: bool) -> object:
        from tpi_videos.panel.biblioteca import Video

        return Video(
            carpeta=Path("/tmp"),
            titulo=titulo,
            tema="Pizarra nocturna",
            tema_clave=None,
            materia=materia,
            molde="",
            duracion=12.0,
            fecha=0.0,
            final=None if borrador else Path("/tmp/x.mp4"),
            borrador=Path("/tmp/x_borrador.mp4") if borrador else None,
            guion=None,
            kit=None,
        )

    def test_el_buscador_lee_el_titulo_y_la_materia(self):
        from tpi_videos.panel.paginas.videos import filtrar

        videos = [self._video("El cubo partido", "geometria", False), self._video("Rampas", "fisica", True)]
        self.assertEqual([v.titulo for v in filtrar(videos, "cubo", "todo")], ["El cubo partido"])
        self.assertEqual([v.titulo for v in filtrar(videos, "FISICA", "todo")], ["Rampas"])

    def test_el_filtro_deja_ver_solo_borradores_o_solo_publicables(self):
        from tpi_videos.panel.paginas.videos import filtrar

        videos = [self._video("Uno", "matematica", False), self._video("Dos", "matematica", True)]
        self.assertEqual([v.titulo for v in filtrar(videos, "", "borrador")], ["Dos"])
        self.assertEqual([v.titulo for v in filtrar(videos, "", "publicable")], ["Uno"])
        self.assertEqual(len(filtrar(videos, "", "todo")), 2)

    def test_la_etiqueta_de_la_familia_sale_del_molde_del_guion(self):
        from tpi_videos.panel.paginas.videos import etiqueta_familia

        self.assertEqual(etiqueta_familia("mito_realidad"), "Desafíos y trampas cognitivas")
        self.assertEqual(etiqueta_familia(""), "Molde libre")


class NotaTest(unittest.TestCase):
    def test_el_editor_de_estilos_deja_elegir_la_nota(self):
        import inspect

        from tpi_videos.panel.paginas import estilos

        fuente = inspect.getsource(estilos)
        self.assertIn("nota", fuente)
        self.assertIn('"materia"', fuente)  # las tres opciones reales de Nota.color


if __name__ == "__main__":
    unittest.main()
