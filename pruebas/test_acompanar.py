"""El dibujo acompaña la explicación: avisos de `tpi revisar` (sin Manim ni pydantic)."""

import unittest

from tpi_videos.acompanar import PasoParaRevisar, faltas_de_acompanamiento

CUBO = {"tipo": "solido_3d", "figura": "cubo", "lado": "4 cm"}


def _paso(tex="V = a^3", visual=None, error=False):
    return PasoParaRevisar(tex=tex, error=error, visual=visual)


class AcompanarTest(unittest.TestCase):
    def test_un_guion_sin_dibujos_no_recibe_avisos(self):
        self.assertEqual(faltas_de_acompanamiento([_paso(), _paso()], ejercicio=True), [])

    def test_el_mismo_dibujo_en_cada_paso_no_es_un_problema(self):
        pasos = [
            _paso(visual={**CUBO, "anotar": ["volumen"]}),
            _paso(visual={**CUBO, "vista": "frente", "anotar": ["area"]}),
            _paso(visual={**CUBO, "corte": "mitad"}),
        ]
        self.assertEqual(faltas_de_acompanamiento(pasos, ejercicio=True), [])

    def test_un_paso_con_formula_sin_dibujo_se_avisa(self):
        pasos = [_paso(visual=CUBO), _paso(tex="A = 6a^2"), _paso(visual=CUBO)]
        faltas = faltas_de_acompanamiento(pasos, ejercicio=True)
        self.assertEqual([(f.nivel, f.donde) for f in faltas], [("sugerencia", "paso 2")])

    def test_los_pasos_hablados_y_los_errores_no_necesitan_dibujo(self):
        pasos = [_paso(visual=CUBO), _paso(tex=""), _paso(tex="V = 3a", error=True)]
        self.assertEqual(faltas_de_acompanamiento(pasos, ejercicio=True), [])

    def test_mezclar_tipos_en_un_ejercicio_es_una_advertencia(self):
        pasos = [_paso(visual=CUBO), _paso(visual={"tipo": "grafico_funcion", "funcion": "x^2"})]
        faltas = faltas_de_acompanamiento(pasos, ejercicio=True)
        self.assertEqual(faltas[0].nivel, "advertencia")
        self.assertIn("solido_3d, grafico_funcion", faltas[0].mensaje)

    def test_cambiarle_los_numeros_al_dibujo_se_avisa(self):
        pasos = [_paso(visual=CUBO), _paso(visual={**CUBO, "lado": "5 cm"})]
        faltas = faltas_de_acompanamiento(pasos, ejercicio=True)
        self.assertEqual(len(faltas), 1)
        self.assertIn("lado", faltas[0].mensaje)

    def test_un_dato_o_mito_puede_mezclar_ejemplos(self):
        pasos = [_paso(visual=CUBO), _paso(tex="x = 1"), _paso(visual={"tipo": "barras"})]
        self.assertEqual(faltas_de_acompanamiento(pasos, ejercicio=False), [])


if __name__ == "__main__":
    unittest.main()
