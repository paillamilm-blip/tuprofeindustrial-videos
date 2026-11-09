"""El diagrama de fuerzas tiene que recibir el color del papel, como los otros 27 dibujos.

Si el dispatch no se lo pasa, los parches de las etiquetas salen blancos (#FFFFFF) y sobre la
pizarra oscura se ven como cuadrados blancos alrededor de cada fuerza.
"""

import inspect
import unittest
from unittest import mock

from tpi_videos.guion import Visual
from tpi_videos.temas import ColoresTema

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from manim import VGroup

    from tpi_videos import dibujos

PAPEL_OSCURO = "#101418"


@unittest.skipUnless(MANIM, "sin Manim no hay dibujo")
class PapelDelDiagramaTest(unittest.TestCase):
    def test_el_dispatch_le_pasa_el_papel_al_diagrama_de_fuerzas(self):
        visual = Visual(tipo="diagrama_fuerzas", vectores=["P", "N"])
        firma = inspect.signature(dibujos.diagrama_fuerzas)
        with mock.patch.object(
            dibujos, "diagrama_fuerzas", return_value=dibujos.Dibujo(mobs=VGroup())
        ) as espia:
            dibujos._dibujar_visual(visual, ColoresTema(), 7.0, 3.3, papel=PAPEL_OSCURO)
        espia.assert_called_once()
        ligado = firma.bind(*espia.call_args.args, **espia.call_args.kwargs)
        ligado.apply_defaults()
        self.assertEqual(ligado.arguments["papel"], PAPEL_OSCURO)


if __name__ == "__main__":
    unittest.main()
