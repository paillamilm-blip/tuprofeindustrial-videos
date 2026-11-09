"""Su público de siempre, guardado en Ajustes: la tarjeta lo ofrece, pero nunca obliga.

El YAML es lo que el panel escribe con `guardar_ajustes_marca` (valida antes de guardar), así que acá
se prueba que esas tres claves existan y que un valor vacío signifique «que decida la IA».
"""

import tempfile
import unittest
from pathlib import Path

from tpi_videos.config import Cierre, Marca, Publico, cargar_marca


class PublicoDeLaMarcaTest(unittest.TestCase):
    def test_sin_publico_guardado_no_hay_predeterminado(self) -> None:
        """El vacío es el estado inicial: sin él la tarjeta dice «lo deduce la IA»."""
        self.assertEqual(Publico().materia, "")
        self.assertEqual(Publico().nivel, "")
        self.assertEqual(Publico().dificultad, "")

    def test_la_marca_saca_su_publico_del_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "marca.yaml"
            ruta.write_text(
                "publico:\n  materia: matematica\n  nivel: 2° medio\n  dificultad: media\n", encoding="utf-8"
            )
            publico = cargar_marca(ruta).publico
            self.assertEqual(publico.materia, "matematica")
            self.assertEqual(publico.nivel, "2° medio")
            self.assertEqual(publico.dificultad, "media")

    def test_guardar_solo_el_nivel_no_borra_lo_demas(self) -> None:
        """El panel manda la sección completa, pero un YAML escrito a medias sigue siendo válido."""
        marca = Marca.model_validate({"publico": {"nivel": "técnico en electricidad"}, "cierre": Cierre().model_dump()})
        self.assertEqual(marca.publico.materia, "")  # fmt: skip
        self.assertEqual(marca.publico.nivel, "técnico en electricidad")

    def test_el_publico_no_choca_con_los_colores_de_las_materias(self) -> None:
        """`materias` ya existe y son colores: el público va en su propia sección."""
        marca = Marca.model_validate({"publico": {"materia": "fisica"}})
        self.assertEqual(marca.publico.materia, "fisica")
        self.assertTrue(hasattr(marca.materias, "matematica"))
