"""La lógica del muro de familias: qué tarjeta está activa y quién la puso (sin widgets)."""

import unittest

from tpi_videos.panel.formatos_ui import elegir, sugerido, texto_del_pie


class SugerenciaTest(unittest.TestCase):
    def test_una_idea_nueva_sugiere_su_familia_sin_bloquear_nada(self):
        self.assertEqual(sugerido("32 por 11 sin lápiz: un atajo de dos segundos"), "hacks")
        self.assertIsNone(sugerido("hola"))

    def test_lo_que_el_autor_toca_gana_a_lo_que_sugiere_la_maquina(self):
        e = elegir(autor="hacks", sugerida="trampas")
        self.assertEqual(e.activo, "hacks")
        self.assertTrue(e.la_puso_el_autor)

    def test_sin_toque_propio_el_activo_es_la_sugerencia(self):
        e = elegir(autor=None, sugerida="datos")
        self.assertEqual(e.activo, "datos")
        self.assertFalse(e.la_puso_el_autor)

    def test_una_clave_que_no_existe_no_rompe_la_tarjeta(self):
        self.assertEqual(elegir(autor="familia_inventada", sugerida=None).activo, "datos")


class PieTest(unittest.TestCase):
    def test_el_cta_se_muestra_como_pie_nunca_como_voz(self):
        self.assertIn("va en el pie", texto_del_pie("hacks"))

    def test_cada_familia_muestra_su_valor_y_un_cambiar(self):
        """Su regla: todo lo que decide la máquina se ve con su valor, y nada bloquea el paso."""
        from tpi_videos.formatos import cargar_formatos
        from tpi_videos.panel.formatos_ui import piezas

        for clave in cargar_formatos():
            nombres = [p[0] for p in piezas(clave)]
            self.assertEqual(nombres, ["Molde", "Estilo", "Dibujos"], clave)
            for nombre, valor, opciones in piezas(clave):
                self.assertTrue(valor, f"{clave} · {nombre} llegó vacío")
                self.assertTrue(opciones, f"{clave} · {nombre} no tiene con qué cambiarse")


class PortadaTest(unittest.TestCase):
    def test_la_portada_de_cada_familia_se_dibuja_de_verdad(self):
        """Sin los datos de ejemplo el motor contesta «aún no está completo» y la tarjeta sale vacía."""
        from tpi_videos.formatos import cargar_formatos, formato
        from tpi_videos.panel.formatos_ui import visual_de_portada
        from tpi_videos.panel.miniaturas import dibujar_miniatura

        for clave in cargar_formatos():
            png = dibujar_miniatura(visual_de_portada(clave), tema=formato(clave).tema)
            self.assertTrue(png.exists(), clave)

    def test_el_nombre_de_un_estilo_no_es_su_definicion_completa(self):
        """`listar_temas()` entrega el tema entero: en la tarjeta se muestra su nombre, no su repr."""
        from tpi_videos.panel.formatos_ui import opciones_de

        for ident, nombre in opciones_de("Estilo").items():
            self.assertLess(len(nombre), 40, ident)
            self.assertNotIn("=", nombre, ident)


class CaminoTest(unittest.TestCase):
    def test_se_puede_llegar_al_video_sin_tocar_ninguna_sugerencia(self):
        from tpi_videos.panel.paginas.crear import puede_continuar

        self.assertEqual(puede_continuar({"idea": "una idea"}), (True, ""))

    def test_sin_idea_no_hay_paso_siguiente_y_lo_dice(self):
        from tpi_videos.panel.paginas.crear import puede_continuar

        continuable, motivo = puede_continuar({"idea": "   "})
        self.assertFalse(continuable)
        self.assertIn("idea", motivo.lower())

    def test_cada_pantalla_del_camino_tiene_su_nombre_en_la_barra(self):
        """La barra se pinta con los nombres del paso: un paso sin nombre sería una pantalla invisible."""
        from tpi_videos.panel.paginas import crear

        self.assertEqual(crear.PASOS, ("idea", "formato", "hoja", "video"))
        self.assertEqual(sorted(crear._NOMBRES), sorted(crear.PASOS))
        self.assertTrue(all(str(v).strip() for v in crear._NOMBRES.values()))


if __name__ == "__main__":
    unittest.main()
