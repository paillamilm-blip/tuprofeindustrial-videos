"""La cámara: cuánto se acerca en cada paso y hasta dónde puede mirar sin salirse de lo dibujado."""

import unittest

from tpi_videos.guion import Guion

try:
    from tpi_videos import escena
except ModuleNotFoundError:  # pragma: no cover - sin manim instalado
    escena = None


def base(**extra):
    datos = {
        "titulo": "Ocho veces más pesado",
        "materia": "matematica",
        "gancho": {"texto": "¿El doble de lado pesa el doble?", "voz": "¿El doble de lado pesa el doble?"},
        "enunciado": {
            "texto": "Un cubo de 4 cm pesa 64 g.",
            "voz": "Un cubo de cuatro centímetros pesa sesenta y cuatro gramos.",
        },
        "pasos": [{"voz": "El volumen es lado al cubo.", "tex": "V = 4^3 = 64", "nota": "Volumen"}],
        "resultado": {"tex": "m_2 = 512", "voz": "Pesa quinientos doce gramos."},
    }
    datos.update(extra)
    return datos


class CamaraDelGuionTest(unittest.TestCase):
    def test_por_defecto_la_camara_se_mueve_suave(self):
        self.assertEqual(Guion.model_validate(base()).camara, "suave")

    def test_quieta_y_fuerte_se_pueden_elegir(self):
        for modo in ("quieta", "fuerte"):
            self.assertEqual(Guion.model_validate(base(camara=modo)).camara, modo)

    def test_un_modo_inventado_no_pasa(self):
        with self.assertRaises(Exception) as sube:
            Guion.model_validate(base(camara="epica"))
        self.assertIn("camara", str(sube.exception))


@unittest.skipUnless(escena is not None, "manim no está instalado")
class EncuadreTest(unittest.TestCase):
    ALTO = 14.222  # el cuadro vertical del video final
    ANCHO = 8.0

    def test_en_hoja_no_panea_porque_el_papel_es_justo(self):
        """El papel mide 11,6: al acercarse no queda margen para bajar la mirada sin ver el escritorio."""
        escala, centro = escena.encuadre(
            -3.5, 0.9, escena.Paisaje(5.8, 0.1, 7.0), self.ALTO, self.ANCHO, 0.86
        )
        self.assertAlmostEqual(escala, 0.9)
        self.assertAlmostEqual(centro, 0.1)

    def test_en_pizarra_sigue_al_dibujo_hasta_el_borde(self):
        escala, centro = escena.encuadre(
            -3.5, 0.97, escena.Paisaje(7.9, 0.0, 7.6), self.ALTO, self.ANCHO, 0.78
        )
        self.assertAlmostEqual(escala, 0.97)
        self.assertAlmostEqual(centro, -(7.9 - self.ALTO * 0.97 / 2))

    def test_no_recorta_lo_dibujado_por_los_lados(self):
        """Acercarse más de la cuenta cortaba la tarjeta de la pizarra por los dos bordes."""
        escala, _ = escena.encuadre(0.0, 0.80, escena.Paisaje(7.9, 0.0, 7.6), self.ALTO, self.ANCHO, 0.78)
        self.assertGreaterEqual(self.ANCHO * escala, 7.6 + escena.HOLGURA_ANCHO - 1e-9)

    def test_nunca_se_aleja_mas_alla_del_cuadro_completo(self):
        paisaje = escena.Paisaje(7.9, 0.0, 7.6)
        self.assertEqual(escena.encuadre(0.0, 1.4, paisaje, self.ALTO, self.ANCHO, 0.86)[0], 1.0)

    def test_respeta_el_acercamiento_minimo(self):
        paisaje = escena.Paisaje(7.9, 0.0, 6.0)  # cabe más cerca sin cortar: manda el mínimo
        self.assertEqual(escena.encuadre(0.0, 0.4, paisaje, self.ALTO, self.ANCHO, 0.86)[0], 0.86)

    def test_el_paso_acumula_pero_no_se_pasa_del_minimo(self):
        escala = 1.0
        for _ in range(8):
            escala = escena.escala_del_paso(escala, "suave")
        self.assertGreaterEqual(escala, escena.ESCALAS["suave"]["minima"] - 1e-9)
        self.assertLess(escala, 0.9)

    def test_el_modo_fuerte_acerca_mas_que_el_suave(self):
        self.assertLess(escena.escala_del_paso(1.0, "fuerte"), escena.escala_del_paso(1.0, "suave"))

    def test_un_modo_desconocido_se_comporta_como_suave(self):
        self.assertEqual(escena.escala_del_paso(1.0, "loca"), escena.escala_del_paso(1.0, "suave"))

    def test_el_paisaje_sale_del_marco_del_tema(self):
        from tpi_videos.config import Marca
        from tpi_videos.temas import cargar_tema

        hoja = escena.paisaje_del_tema(cargar_tema("hoja_de_desarrollo", Marca()))
        pizarra = escena.paisaje_del_tema(cargar_tema("plano_azul", Marca()))
        self.assertAlmostEqual(hoja.centro_y, 0.1)
        self.assertGreater(pizarra.medio_alto, hoja.medio_alto)
        self.assertAlmostEqual(hoja.ancho_util, 7.0)
        self.assertAlmostEqual(pizarra.ancho_util, 7.6)
