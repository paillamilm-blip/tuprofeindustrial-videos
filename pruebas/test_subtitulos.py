"""Las páginas de subtítulo estilo CapCut no parten un número hablado.

«uno coma diecinueve» es un solo dato (1,19); si el corte de página cae entre «uno» y
«coma», en pantalla queda «DIVIDIMOS POR UNO» y se lee como un error.
"""

from __future__ import annotations

import unittest

from tpi_videos.subtitulos import Palabra, agrupar, limpiar


def _palabras(texto: str) -> list[Palabra]:
    """Palabras seguidas, sin pausas: así sólo manda el límite de palabras/caracteres."""
    salida = []
    t = 0.0
    for w in texto.split():
        salida.append(Palabra(w, t, t + 0.4))
        t += 0.5
    return salida


def _paginas(grupos: list[list[Palabra]]) -> list[str]:
    return [" ".join(limpiar(p.texto) for p in g) for g in grupos]


class PruebasAgrupar(unittest.TestCase):
    def test_numero_con_coma_viaja_junto(self):
        grupos = agrupar(_palabras("Dividimos por uno coma diecinueve y obtenemos cincuenta mil pesos"), 3, 16)
        self.assertIn("uno coma diecinueve", " | ".join(_paginas(grupos)))

    def test_no_deja_uno_colgado_de_la_coma(self):
        grupos = agrupar(_palabras("Total equivale a ciento diecinueve por ciento de uno coma diecinueve neto"), 3, 16)
        for g in grupos[:-1]:
            ultima = limpiar(g[-1].texto).lower()
            siguiente = limpiar(grupos[grupos.index(g) + 1][0].texto).lower()
            self.assertFalse(ultima == "uno" and siguiente == "coma", "el número quedó partido")

    def test_sin_coma_respeta_el_limite_de_palabras(self):
        grupos = agrupar(_palabras("Restamos el neto al total y nos da nueve mil quinientos"), 3, 40)
        for g in grupos:
            self.assertLessEqual(len(g), 3, "sin número, el tope de palabras sigue mandando")


if __name__ == "__main__":
    unittest.main()
