import unittest

import yaml

from tpi_videos.guion import Guion, a_yaml, problemas_de_molde


def base(**extra):
    datos = {
        "titulo": "Mito de Pitágoras",
        "materia": "matematica",
        "nivel": "1° medio",
        "gancho": {"texto": "¿Pitágoras era a + b = c?", "voz": "¿Pitágoras era a más b igual a c?"},
        "enunciado": {"texto": "Calcula la hipotenusa de 3 y 4.", "voz": "Calcula la hipotenusa."},
        "pasos": [
            {"voz": "Casi todos suman.", "tex": "c = 3 + 4", "error": True, "nota": "Error típico"},
            {"voz": "En realidad es raíz.", "tex": r"c = \sqrt{3^2 + 4^2}", "nota": "Correcto"},
        ],
        "resultado": {"tex": "c = 5", "voz": "Cinco."},
    }
    datos.update(extra)
    return datos


class GuionMoldesTest(unittest.TestCase):
    def test_molde_se_normaliza(self):
        g = Guion.model_validate(base(molde="Mito vs realidad"))
        self.assertEqual(g.molde, "mito_realidad")

    def test_molde_desconocido_avisa_las_opciones(self):
        with self.assertRaises(Exception) as ctx:
            Guion.model_validate(base(molde="bailar"))
        self.assertIn("mito_realidad", str(ctx.exception))

    def test_regla_de_un_error(self):
        g = Guion.model_validate(base(molde="mito_realidad"))
        self.assertEqual(problemas_de_molde(g), [])
        sin_error = base(molde="mito_realidad")
        sin_error["pasos"][0].pop("error")
        self.assertTrue(problemas_de_molde(Guion.model_validate(sin_error)))

    def test_regla_de_tres_errores(self):
        datos = base(molde="tres_errores")
        datos["pasos"] = [
            {"voz": "Uno.", "tex": "1+1=3", "error": True},
            {"voz": "Dos.", "tex": "2+2=5", "error": True},
            {"voz": "Tres.", "tex": "3+3=7", "error": True},
            {"voz": "Bien.", "tex": "3+3=6"},
        ]
        self.assertEqual(problemas_de_molde(Guion.model_validate(datos)), [])

    def test_regla_de_reto_y_verificacion(self):
        self.assertTrue(problemas_de_molde(Guion.model_validate(base(molde="reto"))))
        con_reto = base(
            molde="reto", reto={"texto": "Intenta con 6 y 8.", "voz": "Intenta con seis y ocho."}
        )
        self.assertEqual(problemas_de_molde(Guion.model_validate(con_reto)), [])
        self.assertTrue(problemas_de_molde(Guion.model_validate(base(molde="nadie_te_enseno"))))

    def test_variantes_y_vuelta_a_yaml(self):
        datos = base(
            molde="mito_realidad",
            gancho_variantes=[
                {"texto": "El error que casi todos cometen", "voz": "El error que casi todos cometen."},
                {"texto": "3 y 4 no dan 7", "tex": r"3 + 4 \neq 7"},
            ],
        )
        texto = a_yaml(datos)
        self.assertIn("molde: mito_realidad", texto)
        self.assertIn("gancho_variantes:", texto)
        g = Guion.model_validate(yaml.safe_load(texto))
        self.assertEqual(g.molde, "mito_realidad")
        self.assertEqual(len(g.gancho_variantes), 2)
        self.assertEqual(g.gancho_variantes[1].tex, r"3 + 4 \neq 7")

    def test_sin_campos_nuevos_el_yaml_no_cambia(self):
        texto = a_yaml(base())
        self.assertNotIn("molde:", texto)
        self.assertNotIn("gancho_variantes:", texto)

    def test_tres_errores_no_sugiere_quitar_errores(self):
        from tpi_videos.revision import revisar

        datos = base(molde="tres_errores")
        datos["pasos"] = [
            {"voz": "Uno.", "tex": "1+1=3", "error": True},
            {"voz": "Dos.", "tex": "2+2=5", "error": True},
            {"voz": "Tres.", "tex": "3+3=7", "error": True},
            {"voz": "Bien.", "tex": "3+3=6"},
        ]
        revision = revisar(Guion.model_validate(datos), "Sígueme.")
        self.assertFalse(any("con uno basta" in a.mensaje for a in revision.avisos))


if __name__ == "__main__":
    unittest.main()
