import unittest

from tpi_videos.guion import Guion
from tpi_videos.revision import revisar


def guion(**visual):
    datos = {
        "tipo": "poligono_regular",
        "lados": 5,
        "lado": "12 cm",
        **visual,
    }
    return {
        "titulo": "La apotema del pentágono",
        "materia": "matematica",
        "gancho": {"texto": "¿Cuánto mide la apotema?", "voz": "¿Cuánto mide la apotema?"},
        "enunciado": {"texto": "Un pentágono de 12 cm de lado.", "voz": "Un pentágono de doce centímetros."},
        "pasos": [{"voz": "Mira la figura.", "visual": datos}],
        "resultado": {"tex": "a = 8,26", "voz": "Ocho coma veintiséis."},
    }


class RevisorPoligonoTest(unittest.TestCase):
    """El polígono que no se puede ver en el celular tiene que avisarse antes de gastar el render."""

    def _avisos(self, **visual):
        revision = revisar(Guion.model_validate(guion(**visual)), "Sígueme.")
        return [a for a in revision.avisos if "visual" in a.donde]

    def test_un_poligono_bien_no_molesta(self):
        self.assertEqual(self._avisos(), [])

    def test_una_figura_de_quince_lados_parece_una_pelota(self):
        mensajes = " | ".join(a.mensaje for a in self._avisos(lados=15))
        self.assertIn("8 lados", mensajes)

    def test_con_cuatro_marcas_ya_no_se_lee(self):
        avisos = self._avisos(anotar=["apotema", "radio", "angulo_central", "angulo_interior"])
        self.assertTrue(avisos, "cuatro marcas en una figura de 3,3 de alta merecen un aviso")
        self.assertIn("2", avisos[0].mensaje)


if __name__ == "__main__":
    unittest.main()
