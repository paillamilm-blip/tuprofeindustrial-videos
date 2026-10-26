import unittest

from tpi_videos.ideas import GanchoIdea, Idea
from tpi_videos.lote import ItemLote


class LoteTest(unittest.TestCase):
    def test_payload_incluye_molde_y_ganchos(self):
        idea = Idea(
            angulo="reto",
            titulo="Reto de Ohm",
            gancho="¿Cuánto vale la corriente?",
            enunciado="Un circuito de 12 V y 4 ohm.",
            materia="fisica",
            nivel="2° medio",
            porque="Porque reta.",
            segundos=45,
            molde="reto",
            ganchos=[
                GanchoIdea(texto="¿Cuánto vale la corriente?", estilo="curiosidad"),
                GanchoIdea(texto="No es 3 amperes", estilo="error"),
                GanchoIdea(texto="Resuélvelo en 5 segundos", estilo="reto"),
            ],
        )
        datos = ItemLote(idea=idea, ok=False, error="x").como_dict()
        self.assertEqual(datos["molde"], "reto")
        self.assertEqual(len(datos["idea"]["ganchos"]), 3)


if __name__ == "__main__":
    unittest.main()
