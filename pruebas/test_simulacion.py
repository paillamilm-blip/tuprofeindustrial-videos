"""La simulación con SciPy: lo que el motor no puede resolver con una fórmula cerrada.

Estas pruebas no tocan Manim ni FFmpeg: es física numérica pura, y se corren en milisegundos.
"""

import math
import unittest

from tpi_videos.simulacion import GRAVEDAD, integrar_oscilador, integrar_pendulo_doble


class OsciladorTest(unittest.TestCase):
    def test_sin_amortiguamiento_sigue_a_cos_omega_t(self):
        """Con c = 0 la integral numérica tiene que dar la solución de libro, dígito arriba dígito abajo."""
        m, k, a = 2.0, 64.0, 0.35
        o = integrar_oscilador(masa=m, constante=k, amortiguamiento=0.0, amplitud=a, hasta=6.0)
        w0 = math.sqrt(k / m)
        error = max(abs(x - a * math.cos(w0 * t)) for t, x in zip(o.t, o.x))
        self.assertLess(error, 1e-6, f"se desvió {error:.2e} del coseno")
        self.assertEqual(o.regimen, "sin amortiguamiento")
        self.assertAlmostEqual(o.periodo, 2 * math.pi / w0, places=6)

    def test_amortiguamiento_suave_reproduce_la_solucion_exacta(self):
        """Subamortiguado y desde el reposo: x(t) = A e^(-αt) (cos ωd t + α/ωd sen ωd t), con α = c/2m."""
        m, k, c, a = 1.0, 100.0, 2.0, 0.4
        o = integrar_oscilador(masa=m, constante=k, amortiguamiento=c, amplitud=a, hasta=5.0)
        alfa = c / (2 * m)
        w0 = math.sqrt(k / m)
        wd = math.sqrt(w0**2 - alfa**2)
        exacta = [
            a * math.exp(-alfa * t) * (math.cos(wd * t) + (alfa / wd) * math.sin(wd * t)) for t in o.t
        ]
        error = max(abs(x - y) for x, y in zip(o.x, exacta))
        self.assertLess(error, 1e-5, f"se desvió {error:.2e} de la solución exacta")
        self.assertEqual(o.regimen, "subamortiguado")
        self.assertAlmostEqual(o.periodo, 2 * math.pi / wd, places=4)
        self.assertGreater(o.periodo, 2 * math.pi / w0)  # amortiguado tarda un poco más
        self.assertAlmostEqual(o.decaimiento, 2 * m / c, places=6)

    def test_el_regimen_lo_dice_el_factor_de_amortiguamiento(self):
        critico = 2 * math.sqrt(1.0 * 100.0)
        sub = integrar_oscilador(1.0, 100.0, critico * 0.3, 0.4, 4.0)
        igual = integrar_oscilador(1.0, 100.0, critico, 0.4, 4.0)
        sobre = integrar_oscilador(1.0, 100.0, critico * 3.0, 0.4, 4.0)
        self.assertAlmostEqual(sub.zeta, 0.3, places=6)
        self.assertEqual(sub.regimen, "subamortiguado")
        self.assertEqual(igual.regimen, "criticamente amortiguado")
        self.assertIsNone(igual.periodo)  # sin oscilar no hay período que anotar
        self.assertEqual(sobre.regimen, "sobreamortiguado")
        self.assertIsNone(sobre.periodo)

    def test_sobreamortiguado_baja_sin_pasar_jamas_de_cero(self):
        """Soltado desde el reposo con ζ > 1 no cruza el equilibrio: si lo hace, la integral está mal."""
        o = integrar_oscilador(masa=1.0, constante=100.0, amortiguamiento=40.0, amplitud=0.4, hasta=3.0)
        self.assertGreater(min(o.x), 0.0)
        for antes, despues in zip(o.x, o.x[1:]):
            self.assertLessEqual(despues, antes + 1e-9)

    def test_la_curva_sale_muestreada_de_corrido_hasta_el_final(self):
        o = integrar_oscilador(masa=1.0, constante=50.0, amortiguamiento=1.0, amplitud=0.2, hasta=4.0)
        self.assertEqual(len(o.t), len(o.x))
        self.assertGreaterEqual(len(o.t), 200)
        self.assertEqual(o.t[0], 0.0)
        self.assertAlmostEqual(o.t[-1], 4.0)
        self.assertTrue(all(b > a for a, b in zip(o.t, o.t[1:])), "el tiempo no avanza de corrido")
        self.assertAlmostEqual(o.x[0], 0.2)

    def test_un_numero_fuera_de_lugar_nombre_al_culpable_en_espanol(self):
        casos = (
            ({"masa": 0.0}, "masa"),
            ({"constante": -10.0}, "constante"),
            ({"amortiguamiento": -1.0}, "amortiguamiento"),
            ({"amplitud": 0.0}, "amplitud"),
            ({"hasta": 0.0}, "hasta"),
        )
        for cambio, culpable in casos:
            datos = {"masa": 1.0, "constante": 10.0, "amortiguamiento": 1.0, "amplitud": 0.2, "hasta": 4.0}
            datos.update(cambio)
            with self.subTest(**cambio):
                with self.assertRaises(ValueError) as ctx:
                    integrar_oscilador(**datos)
                self.assertIn(culpable, str(ctx.exception))


class PenduloDobleTest(unittest.TestCase):
    suelto = dict(masa_1=1.0, masa_2=1.0, longitud_1=1.0, longitud_2=1.0, angulo_1=40.0, angulo_2=20.0)

    def test_la_energia_se_conserva(self):
        """Sin rozamiento la energía no se crea ni se destruye: es la prueba de que integró bien."""
        for nombre, datos in (("suave", self.suelto), ("violento", self.violento)):
            with self.subTest(regimen=nombre):
                p = integrar_pendulo_doble(hasta=10.0, **datos)
                deriva = max(abs(e - p.energia_inicial) for e in p.energia)
                self.assertLess(deriva / abs(p.energia_inicial), 1e-7, f"la energía se movió {deriva:.3e} J")

    def test_los_angulos_vienen_en_grados_y_empiezan_en_la_suelta(self):
        p = integrar_pendulo_doble(hasta=6.0, **self.suelto)
        self.assertAlmostEqual(p.angulo_1[0], 40.0, places=6)
        self.assertAlmostEqual(p.angulo_2[0], 20.0, places=6)

    def test_con_la_segunda_masa_casi_sin_peso_vuelve_pendulo_simple(self):
        """Chequeo contra una fórmula de libro: si la masa de abajo no pesa, el brazo de arriba
        oscillando a 5 grados tiene que dar el período 2π√(L/g) del péndulo simple."""
        p = integrar_pendulo_doble(
            masa_1=1.0, masa_2=0.0001, longitud_1=1.0, longitud_2=1.0,
            angulo_1=5.0, angulo_2=5.0, hasta=6.0, puntos=6001,
        )
        cruces = [
            p.t[i] for i in range(1, len(p.t)) if (p.angulo_1[i - 1] < 0) != (p.angulo_1[i] < 0)
        ]
        self.assertGreaterEqual(len(cruces), 4, "ni siquiera cruzó por cero cuatro veces")
        medido = cruces[3] - cruces[1]
        teorico = 2 * math.pi / math.sqrt(GRAVEDAD / 1.0)
        # A 5 grados el período real es un 0,05 % más largo: la fórmula de libro supone ángulo ínfimo.
        self.assertLess(abs(medido - teorico) / teorico, 0.001, f"{medido:.4f} s vs {teorico:.4f} s")

    def test_en_el_regimen_lineal_no_se_desmadra(self):
        """A 2 grados sigue siendo un péndulo: si se disparara, la dinámica estaría mal armada."""
        p = integrar_pendulo_doble(
            masa_1=1.0, masa_2=1.0, longitud_1=1.0, longitud_2=1.0,
            angulo_1=2.0, angulo_2=2.0, hasta=8.0,
        )
        self.assertLess(max(abs(a) for a in p.angulo_1), 5.0)
        self.assertLess(max(abs(a) for a in p.angulo_2), 5.0)

    violento = dict(
        masa_1=1.0, masa_2=1.0, longitud_1=1.0, longitud_2=1.0, angulo_1=170.0, angulo_2=170.0
    )

    def test_con_los_brazos_arriba_una_diferencia_microscopica_cambia_la_trayectoria(self):
        """El péndulo doble es caótico cuando la masa de abajo pasa por encima: dos sueltas
        casi idénticas terminan en otra parte, y eso es lo que el video quiere mostrar."""
        a = integrar_pendulo_doble(hasta=10.0, **self.violento)
        b = integrar_pendulo_doble(hasta=10.0, **{**self.violento, "angulo_1": 170.0 + 1e-6})
        separacion = max(math.dist(pa, pb) for pa, pb in zip(a.traza, b.traza))
        self.assertGreater(separacion, 0.05, "no se separó: no hay caos, hay un error")

    def test_a_60_grados_dos_sueltas_casi_iguales_se_pegan_una_a_otra(self):
        """El contraste: con energía moderada el sistema no es caótico y late en modo estable."""
        moderado = dict(
            masa_1=1.0, masa_2=1.0, longitud_1=1.0, longitud_2=1.0, angulo_1=60.0, angulo_2=60.0
        )
        a = integrar_pendulo_doble(hasta=10.0, **moderado)
        b = integrar_pendulo_doble(hasta=10.0, **{**moderado, "angulo_1": 60.0 + 1e-6})
        self.assertLess(max(math.dist(pa, pb) for pa, pb in zip(a.traza, b.traza)), 1e-4)

    def test_la_traza_cabe_en_el_radio_de_los_dos_brazos(self):
        p = integrar_pendulo_doble(hasta=8.0, **self.suelto)
        for x, y in p.traza:
            self.assertLessEqual(math.hypot(x, y), 2.0 + 1e-9)

    def test_la_traza_empieza_de_donde_se_suelta(self):
        """La masa de abajo cuelga de los dos brazos: el primer punto sale de la geometría, no de la integral."""
        suelto = dict(self.suelto, longitud_1=0.8, longitud_2=1.4, angulo_1=35.0, angulo_2=-15.0)
        p = integrar_pendulo_doble(hasta=5.0, **suelto)
        a1, a2 = math.radians(35.0), math.radians(-15.0)
        esperado = (
            0.8 * math.sin(a1) + 1.4 * math.sin(a2),
            -(0.8 * math.cos(a1) + 1.4 * math.cos(a2)),
        )
        x, y = p.traza[0]
        self.assertAlmostEqual(x, esperado[0], places=9)
        self.assertAlmostEqual(y, esperado[1], places=9)

    def test_una_longitud_o_una_masa_cero_nombre_al_culpable_en_espanol(self):
        for clave, valor in (("masa_1", 0.0), ("masa_2", -1.0), ("longitud_1", 0.0), ("longitud_2", -0.5)):
            with self.subTest(clave=clave):
                with self.assertRaises(ValueError) as ctx:
                    integrar_pendulo_doble(hasta=5.0, **{**self.suelto, clave: valor})
                culpable = "masa" if "masa" in clave else "longitud"
                self.assertIn(culpable, str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            integrar_pendulo_doble(hasta=5.0, **{**self.suelto, "angulo_1": 180.0})
        self.assertIn("angulo", str(ctx.exception).lower())
        with self.assertRaises(ValueError) as ctx:
            integrar_pendulo_doble(hasta=0.0, **self.suelto)
        self.assertIn("hasta", str(ctx.exception))

    def test_devuelve_las_series_del_mismo_largo(self):
        p = integrar_pendulo_doble(hasta=6.0, **self.suelto)
        n = len(p.t)
        self.assertGreaterEqual(n, 300)
        self.assertEqual(
            (len(p.angulo_1), len(p.angulo_2), len(p.traza), len(p.energia)), (n, n, n, n)
        )


if __name__ == "__main__":
    unittest.main()
