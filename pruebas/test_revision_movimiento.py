"""Un péndulo doble de diez segundos no cabe en una voz de siete: se avisa antes del render."""

import unittest

from tpi_videos.guion import Guion
from tpi_videos.revision import revisar


def _guion(visual, voz="Mira cómo se mueve."):
    return Guion.model_validate(
        {
            "titulo": "El péndulo doble no repite su camino",
            "materia": "fisica",
            "gancho": {"texto": "¿Se repite?", "voz": "¿Se repite?"},
            "enunciado": {"texto": "Dos brazos.", "voz": "Dos brazos."},
            "pasos": [{"voz": voz, "visual": visual}],
            "resultado": {"tex": "E = 29", "voz": "Veintinueve joules."},
        }
    )


def _avisos(visual, voz="Mira cómo se mueve."):
    revision = revisar(_guion(visual, voz), "Sígueme.")
    return [a for a in revision.avisos if "visual" in a.donde]


DOBLE = {
    "tipo": "pendulo_doble",
    "masa_1": "1 kg",
    "masa_2": "1 kg",
    "longitud_1": "1 m",
    "longitud_2": "1 m",
    "angulo_1": 170,
    "angulo_2": 170,
}


class MovimientoLargoTest(unittest.TestCase):
    def test_el_doble_de_diez_segundos_no_cabe_en_una_voz_corta(self):
        avisos = _avisos(DOBLE, voz="Mira.")
        self.assertTrue(avisos)
        self.assertIn("10", avisos[0].mensaje)
        self.assertIn("no comprime", avisos[0].mensaje)

    def test_si_el_guion_pide_dos_segundos_cabe(self):
        self.assertEqual(_avisos({**DOBLE, "duracion": 2}, voz="Mira. " * 40), [])

    def test_un_dibujo_quieto_no_avisa_de_movimiento(self):
        self.assertEqual(_avisos({"tipo": "poligono_regular", "lados": 5, "lado": "12 cm"}, voz="Mira."), [])


if __name__ == "__main__":
    unittest.main()
