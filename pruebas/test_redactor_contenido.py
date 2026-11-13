"""La IA redacta contenido educativo (dato, mito, error, ejercicio), no solo ejercicios.

La red y LaTeX se simulan; el esquema, a_guion, la validación del Guion, el formato y el YAML son reales.
"""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tpi_videos import redactor
from tpi_videos.errores import ErrorMotor
from tpi_videos.guion import Contenido, cargar_guion


def _dato(**cambios):
    d = redactor.EJEMPLO.model_dump()
    d["es_contenido_educativo"] = True
    d["contenido"] = {"intenciones": ["dato"], "objetivo": "Explicar la gravedad sin pedir un cálculo."}
    d["resultado_tex"] = ""
    d["resultado_texto"] = "La gravedad acelera la caída."
    d.update(cambios)
    return redactor.GuionIA.model_validate(d)


APRUEBA = redactor.RevisionIA(aprobado=True, problemas=[])


def _redactar(respuestas, **kw):
    pedidos = []

    def pedir(cliente, modelo, sistema, contenido, esquema, *a, **k):
        pedidos.append(list(contenido))
        return respuestas.pop(0)

    with TemporaryDirectory() as carpeta, patch.dict(os.environ, {"TPI_RAIZ": carpeta}):
        (Path(carpeta) / "guiones").mkdir()
        with (
            patch("tpi_videos.ia.cliente", return_value=object()),
            patch.object(redactor, "pedir_json", side_effect=pedir),
            patch.object(redactor, "errores_latex", return_value=[]),
        ):
            resultado = redactor.redactar("Explica qué hace la gravedad durante una caída.", **kw)
        g = cargar_guion(resultado.ruta)
        texto = resultado.ruta.read_text(encoding="utf-8")
    return resultado, g, texto, pedidos


class RedactorContenidoTest(unittest.TestCase):
    def test_dato_educativo_se_escribe_y_se_relee(self):
        _, g, texto, _ = _redactar([_dato(), APRUEBA])
        self.assertEqual(g.contenido.intenciones, ["dato"])
        self.assertEqual(g.resultado.texto, "La gravedad acelera la caída.")
        self.assertEqual(g.resultado.tex, "")
        self.assertNotIn("  tex: ''", texto)

    def test_paso_sin_formula_no_escribe_tex_vacio(self):
        d = _dato()
        d.pasos[0].tex = ""
        d.pasos[0].mapa = []
        d.pasos[0].destacar = []
        d.pasos[0].halo = []
        d.pasos[0].resaltar_cambio = False
        _, g, texto, _ = _redactar([d, APRUEBA])
        self.assertIsNone(g.pasos[0].tex)
        self.assertNotIn("tex: ''", texto)

    def test_fuera_de_stem_se_rechaza(self):
        no = _dato(es_contenido_educativo=False, motivo="Es una receta de cocina.")
        with self.assertRaisesRegex(ErrorMotor, "No hay contenido educativo suficiente"):
            _redactar([no])

    def test_contenido_manual_manda_sobre_el_inferido_en_cada_ronda(self):
        manual = Contenido(intenciones=["mito"], objetivo="Desarmar que lo pesado cae antes.")
        rechazo = redactor.RevisionIA(aprobado=False, problemas=["paso 1: falta el porqué"])
        _, g, _, pedidos = _redactar([_dato(), rechazo, _dato(), APRUEBA], contenido=manual)
        self.assertEqual(g.contenido, manual)
        self.assertTrue(any("CONTENIDO ELEGIDO" in str(p) for p in pedidos[0]))
        self.assertEqual(len(pedidos), 4)  # la corrección vuelve a pasar por el revisor

    def test_manual_no_salta_la_clasificacion(self):
        manual = Contenido(intenciones=["dato"], objetivo="Algo.")
        with self.assertRaises(ErrorMotor):
            _redactar([_dato(es_contenido_educativo=False, motivo="No es STEM.")], contenido=manual)

    def test_ejercicio_sin_resultado_vuelve_a_corregirse(self):
        sin = _dato(contenido={"intenciones": ["ejercicio"], "objetivo": "Calcular t."}, resultado_texto="")
        con = _dato(contenido={"intenciones": ["ejercicio"], "objetivo": "Calcular t."},
                    resultado_tex="t \\approx 2{,}02\\ \\text{s}", resultado_texto="")  # fmt: skip
        r, g, _, _ = _redactar([sin, con, APRUEBA])
        self.assertEqual(r.rondas, 1)
        self.assertTrue(any("fórmula final" in h for h in r.historial))
        self.assertTrue(g.resultado.tex)

    def test_mapa_inventado_se_descarta(self):
        d = _dato()
        d.pasos[0].mapa = [redactor.MapaIA(termino="zeta_{99}", concepto="inventado")]
        _, g, _, _ = _redactar([d, APRUEBA])
        self.assertEqual(g.pasos[0].mapa, [])

    def test_ejercicio_heredado_sin_contenido_sigue_igual(self):
        e = redactor.EJEMPLO.model_copy(update={"es_contenido_educativo": True})
        _, g, texto, _ = _redactar([e, APRUEBA])
        self.assertIsNone(g.contenido)
        self.assertNotIn("contenido:", texto)
        self.assertTrue(g.resultado.tex)


if __name__ == "__main__":
    unittest.main()
