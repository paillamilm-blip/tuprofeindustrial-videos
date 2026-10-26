import unittest

from tpi_videos.redactor import _aplicar_eleccion


def datos_base():
    return {
        "gancho": {"texto": "Del modelo", "voz": "Del modelo.", "emoji": "🤔", "tex": "x = 1"},
    }


class RedactorVariantesTest(unittest.TestCase):
    def test_sobrescribe_texto_tex_y_emoji(self):
        elegido = {"texto": "El elegido", "tex": "x = 2", "emoji": "🔥", "voz": "El elegido."}
        datos = _aplicar_eleccion(datos_base(), "reto", elegido, [elegido])
        self.assertEqual(datos["gancho"]["texto"], "El elegido")
        self.assertEqual(datos["gancho"]["tex"], "x = 2")
        self.assertEqual(datos["gancho"]["emoji"], "🔥")
        self.assertEqual(datos["gancho"]["voz"], "El elegido.")
        self.assertEqual(datos["molde"], "reto")

    def test_sin_voz_en_la_variante_respeta_la_del_modelo(self):
        elegido = {"texto": "El elegido"}
        datos = _aplicar_eleccion(datos_base(), None, elegido, [elegido])
        self.assertEqual(datos["gancho"]["voz"], "Del modelo.")

    def test_alternativas_sin_duplicar_el_elegido(self):
        elegido = {"texto": "El elegido"}
        otras = [elegido, {"texto": "Otra"}, {"texto": "EL ELEGIDO"}]
        datos = _aplicar_eleccion(datos_base(), None, elegido, otras)
        self.assertEqual([v["texto"] for v in datos["gancho_variantes"]], ["Otra"])

    def test_maximo_cinco_alternativas(self):
        elegido = {"texto": "El elegido"}
        otras = [elegido] + [{"texto": f"Otra {n}"} for n in range(1, 9)]
        datos = _aplicar_eleccion(datos_base(), None, elegido, otras)
        self.assertEqual(len(datos["gancho_variantes"]), 5)


if __name__ == "__main__":
    unittest.main()
