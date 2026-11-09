"""La física integrada se resuelve una sola vez por consulta, no tres.

El guion valida, la revisión estima la duración y el dibujo integra: los tres piden lo mismo.
Con la caché, ``solve_ivp`` corre una vez y las otras dos lecturas salen del mismo resultado.
"""

import unittest
from unittest import mock

from tpi_videos import simulacion, visuales


class CacheOsciladorTest(unittest.TestCase):
    def setUp(self):
        limpiar = getattr(visuales.analizar_oscilador, "cache_clear", None)
        if limpiar:
            limpiar()

    tearDown = setUp

    def test_la_misma_consulta_no_integra_dos_veces(self):
        with mock.patch.object(
            simulacion, "integrar_oscilador", wraps=simulacion.integrar_oscilador
        ) as espia:
            a = visuales.analizar_oscilador("2 kg", "8 N/m", "10 cm")
            b = visuales.analizar_oscilador("2 kg", "8 N/m", "10 cm")
        self.assertEqual(espia.call_count, 1)
        self.assertIs(a, b)
        self.assertEqual(a.x, b.x)

    def test_consultas_distintas_integran_cada_una(self):
        with mock.patch.object(
            simulacion, "integrar_oscilador", wraps=simulacion.integrar_oscilador
        ) as espia:
            visuales.analizar_oscilador("2 kg", "8 N/m", "10 cm")
            visuales.analizar_oscilador("3 kg", "8 N/m", "10 cm")
        self.assertEqual(espia.call_count, 2)


class CachePenduloDobleTest(unittest.TestCase):
    def setUp(self):
        limpiar = getattr(visuales.analizar_pendulo_doble, "cache_clear", None)
        if limpiar:
            limpiar()

    tearDown = setUp

    def test_la_misma_consulta_no_integra_dos_veces(self):
        with mock.patch.object(
            simulacion, "integrar_pendulo_doble", wraps=simulacion.integrar_pendulo_doble
        ) as espia:
            a = visuales.analizar_pendulo_doble("1 kg", "1 kg", "1 m", "1 m", 170, 170)
            b = visuales.analizar_pendulo_doble("1 kg", "1 kg", "1 m", "1 m", 170, 170)
        self.assertEqual(espia.call_count, 1)
        self.assertIs(a, b)
        self.assertEqual(a.traza, b.traza)


if __name__ == "__main__":
    unittest.main()
