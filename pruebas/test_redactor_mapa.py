"""El redactor escribe el mapa de color (gramática XCris) y descarta lo que no está en la fórmula."""

import unittest

from tpi_videos.guion import Guion
from tpi_videos.redactor import EJEMPLO, MapaIA, a_guion


def _con_mapa(mapa: list[MapaIA], error: bool = False):
    g = EJEMPLO.model_copy(deep=True)
    paso = next(p for p in g.pasos if p.tex and not p.error)
    paso.mapa = mapa
    paso.error = error
    return g, g.pasos.index(paso)


class MapaDelRedactorTest(unittest.TestCase):
    def test_un_termino_de_la_formula_llega_al_guion_y_valida(self):
        g, i = _con_mapa([])
        termino = g.pasos[i].tex.split("=")[0].strip() or g.pasos[i].tex
        g.pasos[i].mapa = [MapaIA(termino=termino, concepto="lo que se busca")]
        datos = a_guion(g)
        self.assertEqual(datos["pasos"][i]["mapa"], [{"termino": termino, "concepto": "lo que se busca"}])
        Guion.model_validate(datos)  # el mismo criterio que la validación del guion

    def test_un_termino_inventado_se_descarta_sin_botar_el_guion(self):
        g, i = _con_mapa([MapaIA(termino="zzz_inventado", concepto="nada")])
        datos = a_guion(g)
        self.assertNotIn("mapa", datos["pasos"][i])
        Guion.model_validate(datos)

    def test_tope_de_tres_sin_repetidos_y_concepto_corto(self):
        g, i = _con_mapa([])
        termino = g.pasos[i].tex.split("=")[0].strip() or g.pasos[i].tex
        g.pasos[i].mapa = [MapaIA(termino=termino, concepto="un concepto larguísimo que no cabe en el chip")] * 5
        mapa = a_guion(g)["pasos"][i]["mapa"]
        self.assertEqual(len(mapa), 1)
        self.assertLessEqual(len(mapa[0]["concepto"]), 28)

    def test_un_paso_con_error_no_lleva_mapa(self):
        g, i = _con_mapa([])
        termino = g.pasos[i].tex.split("=")[0].strip() or g.pasos[i].tex
        g.pasos[i].mapa = [MapaIA(termino=termino, concepto="x")]
        g.pasos[i].error = True
        self.assertNotIn("mapa", a_guion(g)["pasos"][i])


if __name__ == "__main__":
    unittest.main()
