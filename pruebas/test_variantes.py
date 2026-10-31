"""Las variantes de la vista «Un video»: qué se marca y qué comando sale.

Puras, sin navegador: la pantalla sólo puede prometer un `tpi lote` que el motor reciba de verdad.
"""

from __future__ import annotations

import json
import unittest

from tpi_videos.panel.sugerencia import args_compilacion, variantes_seleccionadas


def _idea(titulo: str) -> dict:
    return {"titulo": titulo, "idea": f"{titulo} explicado en 40 s", "molde": "paso_a_paso"}


LAS_TRES = [_idea("Uno"), _idea("Dos"), _idea("Tres")]


class VariantesSeleccionadas(unittest.TestCase):
    def test_devuelve_solo_las_marcadas_en_orden(self):
        elegidas = variantes_seleccionadas(LAS_TRES, [True, False, True])
        self.assertEqual([i["titulo"] for i in elegidas], ["Uno", "Tres"])

    def test_con_todas_marcadas_salen_las_tres(self):
        self.assertEqual(len(variantes_seleccionadas(LAS_TRES, [True, True, True])), 3)

    def test_sin_ninguna_marcada_no_sale_nada(self):
        self.assertEqual(variantes_seleccionadas(LAS_TRES, [False, False, False]), [])

    def test_si_las_marcas_no_cuadran_con_las_ideas_es_error(self):
        with self.assertRaises(ValueError):
            variantes_seleccionadas(LAS_TRES, [True, False])


class ArgsCompilacion(unittest.TestCase):
    def test_el_comando_es_un_lote_con_ideas_json(self):
        elegidas = variantes_seleccionadas(LAS_TRES, [True, False, True])
        args = args_compilacion(elegidas)
        self.assertEqual(args[:2], ["lote", "--ideas-json"])
        self.assertEqual(len(args), 3)

    def test_el_json_lee_de_vuelta_las_mismas_ideas(self):
        elegidas = variantes_seleccionadas(LAS_TRES, [False, True, False])
        _lote, _bandera, texto = args_compilacion(elegidas)
        self.assertEqual(json.loads(texto), elegidas)

    def test_los_acentos_viajan_completos_no_con_escapes(self):
        _lote, _bandera, texto = args_compilacion([_idea("Porcentajes sin trampa")])
        self.assertIn("Porcentajes sin trampa", texto)
        self.assertNotIn("\\u", texto)


if __name__ == "__main__":
    unittest.main()
