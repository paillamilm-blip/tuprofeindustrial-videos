"""La IA conoce el motor vivo: el manual lo explica, los ejemplos validan y los campos llegan al YAML."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from tpi_videos.guion import Guion, Visual
from tpi_videos.redactor import EJEMPLOS_DINAMICOS, PasoIA, _sistema, _visual, a_guion

try:
    import manim  # noqa: F401
    from google import genai  # noqa: F401

    COMPLETO = True
except ImportError:  # el panel y las pruebas corren sin Manim
    COMPLETO = False


def _guion(clave: str) -> Guion:
    g = next(g for titulo, g in EJEMPLOS_DINAMICOS.items() if titulo.startswith(clave))
    return Guion.model_validate(a_guion(g))


def _paso(**campos):
    return PasoIA(nota="N", tex="x = 1", voz="Una voz.", **campos)


class ManualTest(unittest.TestCase):
    def test_el_manual_trae_los_dibujos_nuevos_y_los_campos_vivos(self):
        manual = _sistema()
        for texto in (
            'dibujo = "tolva"',
            'dibujo = "tuberia"',
            'dibujo = "eje"',
            'dibujo = "calor"',
            'dibujo = "flujo"',
            'movimiento = "tangente"',
            'movimiento = "area"',
            "despiece = true",
            "halo",
            "resaltar_cambio",
            "resultado_destello",
            "Qué dibujo elegir según el tema",
        ):
            self.assertIn(texto, manual)
        self.assertNotIn("{{", manual, "quedó un hueco de la plantilla sin llenar")

    def test_los_tres_ejemplos_entran_al_manual(self):
        manual = _sistema()
        for titulo in EJEMPLOS_DINAMICOS:
            self.assertIn(titulo, manual)
        self.assertIn('"despiece": true', manual)
        self.assertIn('"movimiento": "tangente"', manual)
        self.assertIn('"halo": [\n    "x^2"', manual)


class EjemplosTest(unittest.TestCase):
    def test_ingenieria_usa_la_tolva_despiezada(self):
        g = _guion("Ingeniería")
        visual = next(p.visual for p in g.pasos if p.visual)
        self.assertEqual(visual.tipo, "tolva_3d")
        self.assertTrue(visual.despiece)
        self.assertAlmostEqual(visual.tolva().volumen, 0.823, places=3)
        self.assertTrue(g.resultado.destello)

    def test_fisica_recorre_la_curva_de_0_a_5(self):
        g = _guion("Física")
        visual = next(p.visual for p in g.pasos if p.visual)
        self.assertEqual(visual.tipo, "grafico_funcion")
        self.assertEqual((visual.movimiento, visual.desde, visual.hasta), ("tangente", 0, 5))
        self.assertEqual(visual.anotar, ["pendiente"])
        f = visual.funcion_analizada()
        self.assertAlmostEqual(f.derivada(2.5), 0.0, places=4)  # se aplana en la altura máxima
        self.assertAlmostEqual(f.y(2.5), 30.625, places=3)

    def test_matematica_sigue_a_x_al_cuadrado_y_cierra_con_destello(self):
        g = _guion("Matemática")
        self.assertEqual(g.pasos[0].halo, ["x^2"])
        self.assertTrue(any(p.resaltar_cambio for p in g.pasos))
        self.assertTrue(g.resultado.destello)

    def test_los_ejemplos_pasan_la_revision_sin_advertencias(self):
        from tpi_videos.config import cargar_marca
        from tpi_videos.revision import revisar

        for titulo, g in EJEMPLOS_DINAMICOS.items():
            rev = revisar(Guion.model_validate(a_guion(g)), cargar_marca().cierre.voz)
            advertencias = [f"{a.donde}: {a.mensaje}" for a in rev.avisos if a.nivel == "advertencia"]
            self.assertEqual(advertencias, [], titulo)


class ConversionTest(unittest.TestCase):
    def test_cada_dibujo_nuevo_llega_al_motor(self):
        casos = {
            "tolva": dict(radio="1,5 m", altura="2 m", radio_salida="0,3 m", altura_cono="1,2 m", despiece=True),
            "tuberia": dict(radio="10 cm", espesor="1 cm", longitud="80 cm", bridas=False, anotar=["seccion"]),
            "eje": dict(radios=[20, 30], largos=[60, 120], unidad="mm", despiece=True),
            "calor": dict(temp_izquierda=100, temp_derecha=20, temp_arriba=20, temp_abajo=20, anotar=["centro"]),
            "flujo": dict(flujo="poiseuille", velocidad="2 m/s", separacion="1 cm", viscosidad="0,001 Pa·s",
                          anotar=["esfuerzo"]),
        }  # fmt: skip
        for dibujo, campos in casos.items():
            visual = Visual.model_validate(_visual(_paso(dibujo=dibujo, **campos)))
            self.assertIn(
                visual.tipo, ("tolva_3d", "tuberia_3d", "eje_3d", "gradiente_termico", "perfil_flujo")
            )
        self.assertFalse(Visual.model_validate(_visual(_paso(dibujo="tuberia", **casos["tuberia"]))).bridas)

    def test_movimiento_solo_viaja_con_el_grafico(self):
        proyectil = _visual(
            _paso(dibujo="proyectil", velocidad="20 m/s", angulo=30, movimiento="tangente", desde=0)
        )
        self.assertNotIn("movimiento", proyectil)
        self.assertNotIn("desde", proyectil)
        Visual.model_validate(proyectil)

    def test_halo_ajeno_a_la_formula_y_cambio_en_un_error_se_descartan(self):
        g = next(iter(EJEMPLOS_DINAMICOS.values())).model_copy(deep=True)
        g.pasos[0].halo = ["no está"]
        g.pasos[1].error = True
        g.pasos[1].resaltar_cambio = True
        datos = a_guion(g)
        self.assertNotIn("halo", datos["pasos"][0])
        self.assertNotIn("resaltar_cambio", datos["pasos"][1])


@unittest.skipUnless(COMPLETO, "manim o google-genai no están instalados")
class RedactarDePuntaAPuntaTest(unittest.TestCase):
    """``redactar`` completo contra el Gemini de mentira: LaTeX, revisión, corrección y YAML."""

    def test_los_tres_temas_dejan_un_yaml_con_los_campos_vivos(self):
        from pruebas.ia_falsa import ClienteFalso
        from tpi_videos import redactor

        temas = {
            "Un balance de masa en una tolva de inyección": ("tolva_3d", "despiece"),
            "Cálculo de altura máxima en tiro parabólico": ("grafico_funcion", "movimiento"),
            "Derivada de una función cuadrática paso a paso": ("grafico_funcion", "movimiento"),
        }
        with tempfile.TemporaryDirectory() as carpeta:
            with (
                mock.patch.object(redactor.ia, "cliente", return_value=ClienteFalso()),
                mock.patch.object(redactor, "raiz_proyecto", return_value=Path(carpeta)),
            ):
                for tema, (tipo, campo) in temas.items():
                    resultado = redactor.redactar(tema)
                    self.assertEqual(resultado.pendientes, [], tema)
                    datos = yaml.safe_load(resultado.ruta.read_text(encoding="utf-8"))
                    visual = next(p["visual"] for p in datos["pasos"] if "visual" in p)
                    self.assertEqual(visual["tipo"], tipo, tema)
                    self.assertIn(campo, visual, tema)
                    self.assertTrue(datos["resultado"].get("destello"), tema)
                    if tipo == "grafico_funcion":
                        self.assertIn("desde", visual)
                        self.assertIn("hasta", visual)
                    if "Derivada" in tema:
                        self.assertTrue(any(p.get("halo") for p in datos["pasos"]))
                        self.assertTrue(any(p.get("resaltar_cambio") for p in datos["pasos"]))


if __name__ == "__main__":
    unittest.main()
