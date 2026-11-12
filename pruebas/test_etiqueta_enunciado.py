"""Reescribir un guion (editor, elegir gancho, redactar) no le borra el rótulo del enunciado."""

import unittest
from pathlib import Path

import yaml

from tpi_videos.guion import Guion, a_yaml, cargar_guion

RAIZ = Path(__file__).resolve().parents[1]


class EtiquetaTest(unittest.TestCase):
    def test_un_rotulo_propio_sobrevive_a_la_reescritura(self):
        for nombre in ("f_3_mas_1_no_es_10.yaml", "tu_gps_te_miente.yaml"):
            g = cargar_guion(RAIZ / "guiones" / nombre)
            self.assertEqual(g.enunciado.etiqueta, "LA RESPUESTA", nombre)
            de_nuevo = Guion.model_validate(yaml.safe_load(a_yaml(g.model_dump(exclude_none=True))))
            self.assertEqual(de_nuevo.enunciado.etiqueta, "LA RESPUESTA", nombre)

    def test_el_rotulo_de_fabrica_no_se_escribe(self):
        g = cargar_guion(RAIZ / "guiones" / "ejemplos" / "fisica_caida_libre.yaml")
        self.assertEqual(g.enunciado.etiqueta, "PROBLEMA")
        self.assertNotIn("etiqueta:", a_yaml(g.model_dump(exclude_none=True)))


if __name__ == "__main__":
    unittest.main()
