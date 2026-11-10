"""Completar los niveles: encontrar lo que falta, elegir ramo y carrera, y escribirlo con la IA."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tpi_videos.errores import ErrorMotor

GUION = """titulo: "{titulo}"
materia: {materia}
nivel: "{nivel}"
{extra}
gancho:
  texto: "¿Sí?"

enunciado:
  texto: "E"

pasos:
  - voz: "Una voz."
    tex: 'x = 1'

resultado:
  tex: 'x = 1'
  voz: "Listo."
"""


class CompletarTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.viejo = os.environ.get("TPI_RAIZ")
        os.environ["TPI_RAIZ"] = self.tmp.name
        self.raiz = Path(self.tmp.name).resolve()
        (self.raiz / "salida").mkdir()
        (self.raiz / "guiones").mkdir()

    def tearDown(self) -> None:
        if self.viejo is None:
            os.environ.pop("TPI_RAIZ", None)
        else:
            os.environ["TPI_RAIZ"] = self.viejo
        self.tmp.cleanup()

    def _guion(self, nombre, materia, nivel, extra=""):
        ruta = self.raiz / "guiones" / f"{nombre}.yaml"
        ruta.write_text(
            GUION.format(titulo=nombre, materia=materia, nivel=nivel, extra=extra), encoding="utf-8"
        )
        return ruta

    def test_los_huecos_son_lo_que_falta_por_nivel(self):
        from tpi_videos.completar import huecos

        self._guion("m", "matematica", "3° medio")
        self._guion("f", "fisica", "3 medio")
        faltan = huecos("media", nivel="3° medio")
        self.assertEqual([(h.nivel, h.materia) for h in faltan], [("3° medio", "ingenieria")])
        self.assertIsNone(faltan[0].carrera)  # en media no hay carrera
        self.assertEqual(len(huecos("media")), 4 * 3 - 2)
        self.assertEqual(len(huecos("universidad")), 4 * 3)

    def test_en_la_universidad_va_la_carrera_con_menos_guiones(self):
        from tpi_videos.completar import huecos

        self._guion("i1", "ingenieria", "3° año ingeniería", "carrera: industrial\n")
        self._guion("i2", "ingenieria", "3° año ingeniería", "carrera: electrica\n")
        from tpi_videos.panel import qc

        for ruta in (self.raiz / "guiones").glob("*.yaml"):
            qc.aprobar(ruta, "lote")  # aprobados: ya no cuentan como «por revisar», pero sí como usados
        h = next(x for x in huecos("universidad", nivel="3° año ingeniería") if x.materia == "ingenieria")
        self.assertEqual(h.carrera, "obras_civiles")
        from tpi_videos.malla import ramos

        self.assertIn(h.ramo, ramos(h.nivel, "ingenieria", "obras_civiles"))

    def test_un_fallo_no_corta_el_resto(self):
        from tpi_videos.completar import completar, huecos

        lista = huecos("universidad", nivel="1° año ingeniería")
        self.assertEqual(len(lista), 3)

        def escribir(h, _avisar):
            if h.materia == "fisica":
                raise ErrorMotor("la IA no respondió")
            return self.raiz / "guiones" / f"{h.materia}.yaml"

        escritos, fallidos = completar(lista, escribir=escribir)
        self.assertEqual([h.materia for h, _r in escritos], ["matematica", "ingenieria"])
        self.assertEqual([(h.materia, m) for h, m in fallidos], [("fisica", "la IA no respondió")])

    def test_simular_no_llama_a_la_ia(self):
        from tpi_videos import cli

        with mock.patch("tpi_videos.completar.completar") as completar:
            codigo = cli.main(["completar-niveles", "--publico", "universidad", "--simular"])
        self.assertEqual(codigo, 0)
        completar.assert_not_called()

    def test_de_punta_a_punta_con_la_ia_falsa(self):
        try:
            from google import genai  # noqa: F401
        except ImportError:
            self.skipTest("google-genai no está instalado")
        from pruebas.ia_falsa import ClienteFalso
        from tpi_videos import ia
        from tpi_videos.completar import completar, huecos
        from tpi_videos.guion import cargar_guion

        lista = [h for h in huecos("universidad", nivel="3° año ingeniería") if h.materia == "ingenieria"]
        with mock.patch.object(ia, "cliente", return_value=ClienteFalso()):
            escritos, fallidos = completar(lista)
        self.assertEqual(fallidos, [])
        g = cargar_guion(escritos[0][1])
        self.assertEqual(
            (g.materia, g.nivel, g.carrera), ("ingenieria", "3° año ingeniería", lista[0].carrera)
        )


if __name__ == "__main__":
    unittest.main()
