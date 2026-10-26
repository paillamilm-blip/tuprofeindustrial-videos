import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual


class VisualPoligonoTest(unittest.TestCase):
    """Lo que el guion deja escribir (y lo que rechaza) antes de que el dibujo exista."""

    def _poligono(self, **cambios):
        datos = {"tipo": "poligono_regular", "lados": 5, "lado": "12 cm"}
        return Visual(**{**datos, **cambios})

    def test_un_poligono_regular_se_lee_desde_el_guion(self):
        figura = self._poligono().poligono()
        self.assertEqual(figura.lados, 5)
        self.assertAlmostEqual(figura.apotema, 8.26, places=2)

    def test_saca_la_marca_extra_de_la_lista_del_guion(self):
        self.assertEqual(self._poligono(anotar="apotema").anotar, ["apotema"])

    def test_sin_medida_no_sabe_que_anotar(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="poligono_regular", lados=5)
        self.assertIn("lado", str(error.exception))

    def test_un_poligono_de_dos_lados_lo_rechaza_el_guion(self):
        with self.assertRaises(ValidationError) as error:
            self._poligono(lados=2)
        self.assertIn("3 lados", str(error.exception))

    def test_una_marca_inventada_dice_cuales_son(self):
        with self.assertRaises(ValidationError) as error:
            self._poligono(anotar=["hipotenusa"])
        mensaje = str(error.exception)
        self.assertIn("hipotenusa", mensaje)
        self.assertIn("apotema", mensaje)

    def test_el_poligono_tarda_lo_que_tarda_un_dibujo(self):
        self.assertEqual(self._poligono().segundos, 3.0)

    def test_al_escribir_el_guion_no_lo_confunde_con_un_circuito(self):
        import yaml

        from tpi_videos.guion import Guion, a_yaml

        texto = a_yaml(
            {
                "titulo": "figura",
                "materia": "matematica",
                "gancho": {"texto": "¿Cuánto mide?", "voz": "¿Cuánto mide?"},
                "enunciado": {"texto": "El pentágono.", "voz": "El pentágono."},
                "pasos": [
                    {
                        "voz": "Miramos la figura.",
                        "visual": {
                            "tipo": "poligono_regular",
                            "lados": 6,
                            "lado": "4 cm",
                            "anotar": ["apotema"],
                        },
                    }
                ],
                "resultado": {"tex": "a = 2", "voz": "Dos."},
            }
        )
        self.assertIn("poligono_regular", texto)
        self.assertIn("4 cm", texto)
        self.assertNotIn("resistencias", texto)
        # lo que se escribe debe volver a leerse como el mismo polígono
        visual = Guion.model_validate(yaml.safe_load(texto)).pasos[0].visual
        self.assertEqual(
            (visual.tipo, visual.lados, visual.lado, visual.anotar),
            ("poligono_regular", 6, "4 cm", ["apotema"]),
        )


if __name__ == "__main__":
    unittest.main()
