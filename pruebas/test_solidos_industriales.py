"""Piezas industriales en 3D (tolva, tubería, eje), calor en una placa y flujo entre placas."""

import math
import unittest

import numpy as np
import yaml

from tpi_videos.guion import Visual, a_yaml
from tpi_videos.simulacion import conducir_placa, perfil_couette, perfil_poiseuille
from tpi_videos.visuales import (
    TIPOS_3D,
    VISUALES,
    analizar_eje,
    analizar_flujo,
    analizar_tolva,
    analizar_tuberia,
)

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from tpi_videos.dibujos import ALTO_DIBUJO, dibujar_visual
    from tpi_videos.temas import ColoresTema

ANCHO_HOJA = 7.0
NUEVOS = ("tolva_3d", "tuberia_3d", "eje_3d", "gradiente_termico", "perfil_flujo")


def _visual(tipo, **extra):
    return Visual.model_validate({"tipo": tipo, **VISUALES[tipo].ejemplo, **extra})


class CuentasTest(unittest.TestCase):
    def test_la_tolva_suma_cilindro_y_cono_truncado(self):
        t = analizar_tolva("1,5 m", "2 m", "0,3 m", "1,2 m")
        esperado = math.pi * 1.5**2 * 2 + math.pi * 1.2 * (1.5**2 + 1.5 * 0.3 + 0.3**2) / 3
        self.assertAlmostEqual(t.volumen, esperado)
        self.assertAlmostEqual(t.generatriz, math.hypot(1.2, 1.2))
        self.assertEqual(t.unidad, "m")

    def test_las_unidades_se_pueden_mezclar(self):
        t = analizar_tolva("1,5 m", "2 m", "30 cm", "120 cm")
        self.assertAlmostEqual(t.radio_salida, 0.3)
        self.assertAlmostEqual(t.altura_cono, 1.2)

    def test_la_boca_tiene_que_ser_mas_angosta(self):
        with self.assertRaises(ValueError):
            analizar_tolva("1 m", "2 m", "1 m", "1 m")

    def test_la_tuberia_calcula_su_hueco_y_su_pared(self):
        t = analizar_tuberia("10 cm", "1 cm", "80 cm")
        self.assertAlmostEqual(t.radio_interior, 9.0)
        self.assertAlmostEqual(t.seccion, math.pi * 81)
        self.assertAlmostEqual(t.material, math.pi * (100 - 81) * 80)
        with self.assertRaises(ValueError):
            analizar_tuberia("1 cm", "1 cm", "10 cm")

    def test_el_eje_suma_sus_tramos(self):
        e = analizar_eje([20, 30], [60, 120], "mm")
        self.assertAlmostEqual(e.volumen, math.pi * (400 * 60 + 900 * 120))
        self.assertEqual(e.largo, 180)
        with self.assertRaises(ValueError):
            analizar_eje([20, 30], [60], "mm")
        with self.assertRaises(ValueError):
            analizar_eje([20], [60], "mm")

    def test_el_esfuerzo_en_la_pared(self):
        p = analizar_flujo("poiseuille", "2 m/s", "1 cm", "0,001 Pa·s")
        self.assertAlmostEqual(p.esfuerzo_pared, 0.8)
        self.assertAlmostEqual(p.media, 4 / 3)
        c = analizar_flujo("couette", "2 m/s", "1 cm", "0,001 Pa·s")
        self.assertAlmostEqual(c.esfuerzo_pared, 0.2)
        self.assertIsNone(analizar_flujo("couette", "2 m/s", "1 cm").esfuerzo_pared)
        self.assertAlmostEqual(analizar_flujo("couette", "36 km/h", "1 cm").velocidad, 10.0)


class FisicaTest(unittest.TestCase):
    def test_la_placa_cuadrada_con_un_borde_caliente_deja_un_cuarto_en_el_centro(self):
        # Superposición: los cuatro giros del problema suman la placa entera a 100 °C.
        placa = conducir_placa(100, 0, 0, 0, nx=21, ny=21)
        self.assertAlmostEqual(placa.centro(placa.fotos[0]), 0.0)
        self.assertAlmostEqual(placa.centro(), 25.0, delta=0.5)
        centros = [placa.centro(f) for f in placa.fotos]
        self.assertEqual(centros, sorted(centros), "el centro solo puede calentarse")

    def test_la_placa_respeta_sus_bordes(self):
        placa = conducir_placa(80, 20, 50, 10)
        t = placa.permanente
        self.assertTrue(np.allclose(t[1:-1, 0], 80))
        self.assertTrue(np.allclose(t[1:-1, -1], 20))
        self.assertTrue(np.allclose(t[-1, 1:-1], 50))
        self.assertTrue(np.allclose(t[0, 1:-1], 10))
        self.assertGreaterEqual(t.min(), 10 - 1e-9)
        self.assertLessEqual(t.max(), 80 + 1e-9)

    def test_couette_arranca_quieto_y_termina_recto(self):
        s = np.linspace(0.05, 0.95, 10)
        self.assertTrue(np.allclose(perfil_couette(s, 50.0), s, atol=1e-6))
        self.assertTrue(np.all(np.abs(perfil_couette(s[:-1], 1e-4)) < 1e-2))

    def test_poiseuille_arranca_quieto_y_termina_en_parabola(self):
        s = np.linspace(0.05, 0.95, 10)
        self.assertTrue(np.allclose(perfil_poiseuille(s, 50.0), 4 * s * (1 - s), atol=1e-6))
        self.assertLess(abs(float(perfil_poiseuille(0.5, 1e-4))), 1e-2)
        medio = [float(perfil_poiseuille(0.5, tau)) for tau in (0.01, 0.05, 0.1, 0.3)]
        self.assertEqual(medio, sorted(medio))


class GuionTest(unittest.TestCase):
    def test_los_ejemplos_del_catalogo_validan(self):
        for tipo in NUEVOS:
            self.assertEqual(_visual(tipo).tipo, tipo)

    def test_el_despiece_vale_en_las_piezas_3d(self):
        for tipo in ("tolva_3d", "tuberia_3d", "eje_3d"):
            self.assertIn(tipo, TIPOS_3D)
            self.assertTrue(_visual(tipo, despiece=True).despiece)
        with self.assertRaises(ValueError):
            _visual("gradiente_termico", despiece=True)

    def test_faltas_y_marcas_ajenas_se_explican(self):
        with self.assertRaises(ValueError):
            Visual.model_validate({"tipo": "tolva_3d", "radio": "1 m", "altura": "2 m"})
        with self.assertRaises(ValueError):
            _visual("tolva_3d", anotar=["seccion"])
        with self.assertRaises(ValueError):
            _visual("perfil_flujo", anotar=["esfuerzo"])  # sin viscosidad
        with self.assertRaises(ValueError):
            _visual("gradiente_termico", temp_izquierda=20)  # los cuatro bordes iguales
        with self.assertRaises(ValueError):
            Visual.model_validate({"tipo": "perfil_flujo", "velocidad": "2 m/s", "separacion": "1 cm"})

    def test_el_yaml_guarda_y_vuelve_igual(self):
        casos = [
            _visual("tolva_3d", despiece=True, vista="frente", anotar=["volumen", "chapa"]),
            _visual("tuberia_3d", bridas=False),
            _visual("eje_3d", despiece=True),
            _visual("gradiente_termico", base="40 cm", altura="20 cm", anotar=["centro", "isotermas"]),
            _visual("perfil_flujo", viscosidad="0,001 Pa·s", anotar=["esfuerzo"]),
        ]
        for visual in casos:
            texto = "\n".join(linea.strip() for linea in a_yaml_visual(visual))
            vuelta = Visual.model_validate(yaml.safe_load(texto))
            self.assertEqual(vuelta, visual, visual.tipo)


def a_yaml_visual(visual):
    """Las líneas del bloque visual tal como las escribe el guardado del guion."""
    guion = {
        "titulo": "T",
        "materia": "fisica",
        "gancho": {"texto": "G"},
        "enunciado": {"texto": "E"},
        "pasos": [{"voz": "V", "visual": visual.model_dump(exclude_none=True)}],
        "resultado": {"tex": "x", "voz": "R"},
    }
    lineas = a_yaml(guion).splitlines()
    inicio = lineas.index("    visual:") + 1
    fin = next(i for i in range(inicio, len(lineas)) if not lineas[i].startswith("      "))
    return lineas[inicio:fin]


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujosTest(unittest.TestCase):
    def _dibujo(self, tipo, **extra):
        return dibujar_visual(_visual(tipo, **extra), ColoresTema(), ANCHO_HOJA, ALTO_DIBUJO)

    def test_todos_se_mueven_sin_reloj_fisico_y_no_se_salen(self):
        for tipo in NUEVOS:
            dib = self._dibujo(tipo, **({"despiece": True} if tipo in TIPOS_3D else {}))
            self.assertIsNotNone(dib.vivo, tipo)
            self.assertFalse(dib.fisico, tipo)
            for t in (0.0, 0.3, 0.7, 1.0):
                dib.vivo(t)
                pts = np.vstack([m.points for m in dib.mobs.get_family() if len(m.points)])
                self.assertTrue(np.all(np.isfinite(pts)), f"{tipo} t={t}")
                self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 0.05, f"{tipo} t={t}")
                self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 0.05, f"{tipo} t={t}")

    def test_con_despiece_las_piezas_de_la_tolva_se_separan(self):
        from tpi_videos.dibujos_3d import _piezas_tolva

        t = _visual("tolva_3d").tolva()
        juntas, separadas = _piezas_tolva(t, False), _piezas_tolva(t, True)
        self.assertTrue(all(np.allclose(p.salida, 0) for p in juntas))
        self.assertGreater(separadas[0].salida[2], 0)  # el cilindro sube
        self.assertLess(separadas[1].salida[2], 0)  # el cono baja

    def test_la_tuberia_es_hueca_y_tiene_bridas(self):
        from tpi_videos.dibujos_3d import _piezas_tuberia

        t = _visual("tuberia_3d").tuberia()
        piezas = _piezas_tuberia(t, True, False)
        self.assertEqual(len(piezas), 3)
        clases = {c.clase for p in piezas for c in p.caras}
        self.assertTrue({"cuerpo", "interior", "anillo"} <= clases)
        self.assertEqual(len(_piezas_tuberia(t, False, False)), 1)

    def test_el_eje_tiene_un_tramo_por_radio(self):
        from tpi_videos.dibujos_3d import _piezas_eje

        piezas, centros = _piezas_eje(_visual("eje_3d").eje(), True)
        self.assertEqual(len(piezas), 3)
        self.assertEqual(centros, sorted(centros))
        # Acostado a lo largo de x y, con despiece, cada tramo se corre por su eje.
        self.assertLess(piezas[0].salida[0], 0)
        self.assertGreater(piezas[-1].salida[0], 0)

    def test_la_placa_pinta_caliente_el_borde_caliente(self):
        from manim import ManimColor

        from tpi_videos.dibujos import color_termico

        dib = self._dibujo("gradiente_termico")
        dib.vivo(1.0)
        celdas = dib.aparece[0]
        nx = _visual("gradiente_termico").placa().permanente.shape[1]
        izquierda = ManimColor(celdas[nx * 4 + 1].get_fill_color()).to_rgb()
        derecha = ManimColor(celdas[nx * 4 + nx - 2].get_fill_color()).to_rgb()
        self.assertGreater(izquierda[0] - izquierda[2], derecha[0] - derecha[2])
        self.assertEqual(color_termico(0.0).to_hex().upper(), "#2F5BEA")
        self.assertEqual(color_termico(1.0).to_hex().upper(), "#D7263D")

    def test_el_perfil_de_poiseuille_es_mas_rapido_al_centro(self):
        from manim import Arrow

        dib = self._dibujo("perfil_flujo")
        dib.vivo(1.0)
        flechas = [m for m in dib.aparece if isinstance(m, Arrow)]
        largos = [float(np.linalg.norm(f.get_end() - f.get_start())) for f in flechas]
        centro = len(largos) // 2
        self.assertEqual(max(largos), largos[centro])
        self.assertLess(largos[0], largos[centro] * 0.5)
        dib.vivo(0.0)
        quietos = [float(np.linalg.norm(f.get_end() - f.get_start())) for f in flechas]
        self.assertLess(max(quietos), 0.1, "arranca en reposo")


if __name__ == "__main__":
    unittest.main()
