"""Matemática viva: la pendiente y el área que se leen son las de la curva dibujada, y el guion valida."""

import unittest

import numpy as np

from tpi_videos.guion import Paso, Resultado, Visual, a_yaml
from tpi_videos.temas import ColoresTema
from tpi_videos.visuales import CAMPOS, MARCAS_FUNCION, VISUALES, analizar_funcion

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from tpi_videos.dibujos import ALTO_DIBUJO, dibujar_visual
    from tpi_videos.escena import recorrido_sin_fisica

ANCHO_HOJA = 7.0


def _grafico(**extra):
    return Visual.model_validate({"tipo": "grafico_funcion", "funcion": "x^2", "rango": [-3, 3], **extra})


class DerivadaYAreaTest(unittest.TestCase):
    def test_la_pendiente_de_x_al_cuadrado_en_3_es_6(self):
        f = analizar_funcion("x^2", None, [-5, 5], [])
        self.assertAlmostEqual(f.derivada(3.0), 6.0, places=4)

    def test_la_pendiente_del_seno_en_cero_es_uno(self):
        f = analizar_funcion("sin(x)", None, [-3, 3], [])
        self.assertAlmostEqual(f.derivada(0.0), 1.0, places=4)

    def test_en_una_asintota_no_hay_pendiente(self):
        f = analizar_funcion("1/x", None, [-2, 2], [])
        self.assertIsNone(f.derivada(0.0))

    def test_el_area_bajo_x_al_cuadrado_de_0_a_3_es_9(self):
        f = analizar_funcion("x^2", None, [-5, 5], [])
        self.assertAlmostEqual(f.area(0.0, 3.0), 9.0, places=3)

    def test_bajo_el_eje_el_area_resta(self):
        f = analizar_funcion("x", None, [-5, 5], [])
        self.assertAlmostEqual(f.area(-2.0, 0.0), -2.0, places=6)
        self.assertAlmostEqual(f.area(-2.0, 2.0), 0.0, places=6)

    def test_un_hueco_en_el_tramo_se_encuentra(self):
        f = analizar_funcion("1/x", None, [-2, 2], [])
        self.assertIsNotNone(f.tramo_sin_huecos(-1.0, 1.0))
        self.assertIsNone(f.tramo_sin_huecos(0.5, 2.0))


class ValidacionDelMovimientoTest(unittest.TestCase):
    def test_sin_movimiento_el_grafico_es_el_de_siempre(self):
        v = _grafico()
        self.assertEqual(v.movimiento, "")
        self.assertIsNone(v.desde)

    def test_la_tangente_y_el_area_validan(self):
        self.assertEqual(_grafico(movimiento="tangente", anotar=["pendiente"]).movimiento, "tangente")
        self.assertEqual(_grafico(movimiento="area", desde=0, hasta=2, anotar=["area"]).hasta, 2)

    def test_movimiento_en_otro_dibujo_se_rechaza(self):
        with self.assertRaises(ValueError):
            Visual.model_validate({"tipo": "circulo_trig", "angulo": 30, "movimiento": "tangente"})

    def test_desde_mayor_que_hasta_se_rechaza(self):
        with self.assertRaises(ValueError):
            _grafico(movimiento="area", desde=2, hasta=1)

    def test_un_recorrido_fuera_del_rango_se_rechaza(self):
        with self.assertRaises(ValueError):
            _grafico(movimiento="tangente", desde=-5)

    def test_una_asintota_dentro_del_recorrido_se_rechaza(self):
        with self.assertRaises(ValueError) as error:
            Visual.model_validate(
                {"tipo": "grafico_funcion", "funcion": "1/x", "rango": [-2, 2], "movimiento": "tangente"}
            )
        self.assertIn("no existe", str(error.exception))

    def test_la_marca_tiene_que_ir_con_su_movimiento(self):
        with self.assertRaises(ValueError):
            _grafico(movimiento="tangente", anotar=["area"])
        with self.assertRaises(ValueError):
            _grafico(anotar=["pendiente"])

    def test_el_catalogo_ofrece_los_campos_nuevos(self):
        campos = VISUALES["grafico_funcion"].campos
        for clave in ("movimiento", "desde", "hasta", "anotar"):
            self.assertIn(clave, campos)
            self.assertIn(clave, CAMPOS)
        self.assertEqual(VISUALES["grafico_funcion"].marcas, MARCAS_FUNCION)
        self.assertIn("despiece", VISUALES["solido_3d"].campos)

    def test_el_despiece_solo_va_en_un_solido_3d_que_tenga_piezas(self):
        base = {"tipo": "solido_3d", "figura": "cilindro", "radio": "3 cm", "altura": "5 cm"}
        self.assertTrue(Visual.model_validate({**base, "despiece": True}).despiece)
        with self.assertRaises(ValueError):
            Visual.model_validate({"tipo": "solido_3d", "figura": "esfera", "radio": "3 cm", "despiece": True})
        with self.assertRaises(ValueError):
            Visual.model_validate({"tipo": "solido", "figura": "cubo", "lado": "4 cm", "despiece": True})

    def test_halo_y_resaltar_cambio_son_opcionales(self):
        paso = Paso.model_validate({"voz": "Uno.", "tex": "x = 2"})
        self.assertEqual(paso.halo, [])
        self.assertFalse(paso.resaltar_cambio)
        self.assertEqual(Paso.model_validate({"voz": "Uno.", "tex": "x = 2", "halo": "x"}).halo, ["x"])
        self.assertFalse(Resultado.model_validate({"tex": "x = 2", "voz": "Listo."}).destello)

    def test_el_yaml_guarda_lo_nuevo_y_calla_lo_que_no_se_usa(self):
        guion = {
            "titulo": "T",
            "materia": "matematica",
            "gancho": {"texto": "¿Sí?"},
            "enunciado": {"texto": "E"},
            "pasos": [
                {
                    "voz": "V",
                    "tex": "x = 2",
                    "halo": ["x"],
                    "resaltar_cambio": True,
                    "visual": {
                        "tipo": "grafico_funcion",
                        "funcion": "x^2",
                        "movimiento": "area",
                        "desde": 0,
                        "hasta": 2,
                        "anotar": ["area"],
                    },
                },
                {"voz": "W", "tex": "y = 1"},
            ],
            "resultado": {"tex": "x = 2", "voz": "R", "destello": True},
        }
        texto = a_yaml(guion)
        for linea in ("movimiento: area", "desde: 0", "hasta: 2", "resaltar_cambio: true", "destello: true"):
            self.assertIn(linea, texto)
        self.assertEqual(texto.count("resaltar_cambio"), 1)


@unittest.skipUnless(MANIM, "manim no está instalado")
class GraficoVivoTest(unittest.TestCase):
    def _dibujo(self, **extra):
        return dibujar_visual(_grafico(**extra), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)

    def test_sin_movimiento_queda_quieto_y_con_la_misma_geometria(self):
        quieto = self._dibujo()
        self.assertIsNone(quieto.vivo)
        self.assertTrue(quieto.fisico)

    def test_la_tangente_y_el_area_se_mueven_sin_reloj_fisico(self):
        for movimiento in ("tangente", "area"):
            dib = self._dibujo(movimiento=movimiento)
            self.assertIsNotNone(dib.vivo, movimiento)
            self.assertFalse(dib.fisico, movimiento)
            self.assertGreater(dib.duracion, 0, movimiento)

    def test_la_tangente_recorre_la_curva_y_gira(self):
        from manim import Dot, Line

        dib = self._dibujo(movimiento="tangente", anotar=["pendiente"])
        punto = next(m for m in dib.mobs.get_family() if isinstance(m, Dot) and m.radius > 0.08)
        recta = next(m for m in dib.mobs.get_family() if isinstance(m, Line) and m.stroke_width >= 6)
        poses = []
        for t in (0.0, 0.5, 1.0):
            dib.vivo(t)
            inicio, fin = recta.get_start(), recta.get_end()
            poses.append((punto.get_center().copy(), (fin - inicio)[1] / max(abs((fin - inicio)[0]), 1e-9)))
            self.assertTrue(np.all(np.isfinite(punto.get_center())))
        xs = [p[0][0] for p in poses]
        self.assertLess(xs[0], xs[1])
        self.assertLess(xs[1], xs[2])
        # x² en [-3, 3]: baja al principio, plana en el medio y sube al final.
        self.assertLess(poses[0][1], 0)
        self.assertAlmostEqual(poses[1][1], 0, places=2)
        self.assertGreater(poses[2][1], 0)

    def test_el_valor_escrito_es_el_de_la_curva(self):
        dib = self._dibujo(movimiento="area", desde=0, hasta=3, anotar=["area"])
        dib.vivo(1.0)
        textos = [m.text for m in dib.mobs.get_family() if hasattr(m, "text")]
        self.assertTrue(any("9" in t and "A" in t for t in textos), textos)

    def test_la_pose_no_se_sale_de_la_franja(self):
        dib = self._dibujo(movimiento="tangente")
        for t in np.linspace(0, 1, 9):
            dib.vivo(float(t))
            self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
            self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)


@unittest.skipUnless(MANIM, "manim no está instalado")
class HaloDelCambioTest(unittest.TestCase):
    def test_lo_que_llega_nuevo_es_solo_el_termino_que_cambio(self):
        from tpi_videos import componentes as c

        antes, despues = c.ecuacion("5x + 5x = 20"), c.ecuacion("10x = 20")
        self.assertEqual([p.tex_string for p in c.terminos_nuevos(antes, despues)], ["10x"])
        self.assertEqual([p.tex_string for p in c.terminos_nuevos(despues, antes)], ["5x", "5x"])
        self.assertEqual(c.terminos_nuevos(None, despues), [])

    def test_el_halo_son_tres_capas_que_se_apagan_hacia_afuera(self):
        from tpi_videos import componentes as c

        parte = c.ecuacion("10x = 20")[0]
        halo = c.halo_de(parte, "#FFCC00")
        self.assertEqual(len(halo), 3)
        anchos = [capa.width for capa in halo]
        opacidades = [capa.get_fill_opacity() for capa in halo]
        self.assertEqual(anchos, sorted(anchos, reverse=True))
        self.assertEqual(opacidades, sorted(opacidades))
        self.assertGreater(halo[-1].width, parte.width)


@unittest.skipUnless(MANIM, "manim no está instalado")
class RecorridoSinFisicaTest(unittest.TestCase):
    def test_llena_la_ventana_y_siempre_llega_al_final(self):
        self.assertEqual(recorrido_sin_fisica(3.2), (3.2, 1.0))
        self.assertEqual(recorrido_sin_fisica(0.0), (0.35, 1.0))


if __name__ == "__main__":
    unittest.main()
