import unittest

from tpi_videos.ideas import GanchoIdea, Idea, _limpiar, _texto


def idea(titulo, molde, textos, estilos=None, **extra):
    estilos = estilos or ["dolor", "curiosidad", "dato"]
    estilos = [estilos[i % len(estilos)] for i in range(len(textos))]
    return Idea(
        angulo="error_tipico",
        titulo=titulo,
        gancho=textos[0],
        enunciado=f"Resuelve el ejercicio de {titulo} con números concretos y unidades.",
        materia="matematica",
        nivel="1° medio",
        porque="Porque frena el scroll.",
        segundos=45,
        molde=molde,
        ganchos=[
            GanchoIdea(texto=t, estilo=e, emoji="")
            for t, e in zip(textos, estilos, strict=False)
        ],
        **extra,
    )


class IdeasTest(unittest.TestCase):
    def test_conserva_tres_ideas_con_moldes_distintos(self):
        ideas = [
            idea("A", "mito_realidad", ["a", "b", "c"]),
            idea("B", "reto", ["d", "e", "f"]),
            idea("C", "pov", ["g", "h", "i"]),
        ]
        limpias = _limpiar(ideas, None, None)
        self.assertEqual(len(limpias), 3)
        self.assertEqual({i.molde for i in limpias}, {"mito_realidad", "reto", "pov"})
        self.assertEqual(limpias[0].gancho, "a")

    def test_descarta_gancho_de_once_palabras(self):
        largo = "uno dos tres cuatro cinco seis siete ocho nueve diez once"
        ideas = [idea("A", "mito_realidad", [largo, "b", "c", "d"]),
                 idea("B", "reto", ["e", "f", "g"]),
                 idea("C", "pov", ["h", "i", "j"])]  # fmt: skip
        limpias = _limpiar(ideas, None, None)
        self.assertEqual(len(limpias), 3)  # la de 4 válidos queda con 3; la de 3 queda igual
        self.assertNotIn(largo, [g.texto for g in limpias[0].ganchos])

    def test_descarta_idea_con_menos_de_tres_ganchos(self):
        ideas = [idea("A", "mito_realidad", ["a", "b"]), idea("B", "reto", ["d", "e", "f"])]
        limpias = _limpiar(ideas, None, None)
        self.assertEqual([i.titulo for i in limpias], ["B"])

    def test_descarta_emoji_dentro_del_texto(self):
        ideas = [idea("A", "mito_realidad", ["a 🔥", "b", "c", "d"]),
                 idea("B", "reto", ["d", "e", "f"])]  # fmt: skip
        limpias = _limpiar(ideas, None, None)
        self.assertEqual(limpias[0].ganchos[0].texto, "b")

    def test_exige_dos_estilos_distintos(self):
        ideas = [idea("A", "mito_realidad", ["a", "b", "c"], ["dolor", "dolor", "dolor"]),
                 idea("B", "reto", ["d", "e", "f"])]  # fmt: skip
        self.assertEqual([i.titulo for i in _limpiar(ideas, None, None)], ["B"])

    def test_no_repite_molde(self):
        ideas = [idea("A", "reto", ["a", "b", "c"]), idea("B", "reto", ["d", "e", "f"])]
        self.assertEqual([i.titulo for i in _limpiar(ideas, None, None)], ["A"])

    def test_idea_guardada_sin_ganchos_sintetiza_uno(self):
        vieja = Idea(
            angulo="reto", titulo="Vieja", gancho="¿Cuánto pesa?", enunciado="Un ejercicio con números.",
            materia="fisica", nivel="2° medio", porque="Porque sí.", segundos=40,
        )  # fmt: skip
        self.assertEqual(len(vieja.ganchos), 1)
        self.assertEqual(vieja.ganchos[0].texto, "¿Cuánto pesa?")

    def test_texto_limpia_espacios(self):
        self.assertEqual(_texto("  hola   mundo  "), "hola mundo")


if __name__ == "__main__":
    unittest.main()
