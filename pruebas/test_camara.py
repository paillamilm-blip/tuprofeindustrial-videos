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
        escala, _, centro = escena.encuadre(
            -3.5, 0.9, escena.Paisaje(5.8, 0.1, 7.0), self.ALTO, self.ANCHO, 0.86
        )
        self.assertAlmostEqual(escala, 0.9)
        self.assertAlmostEqual(centro, 0.1)

    def test_en_pizarra_sigue_al_dibujo_hasta_el_borde(self):
        escala, _, centro = escena.encuadre(
            -3.5, 0.97, escena.Paisaje(7.9, 0.0, 7.6), self.ALTO, self.ANCHO, 0.78
        )
        self.assertAlmostEqual(escala, 0.97)
        self.assertAlmostEqual(centro, -(7.9 - self.ALTO * 0.97 / 2))

    def test_no_recorta_lo_dibujado_por_los_lados(self):
        """Acercarse más de la cuenta cortaba la tarjeta de la pizarra por los dos bordes."""
        escala, _, _ = escena.encuadre(
            0.0, 0.80, escena.Paisaje(7.9, 0.0, 7.6), self.ALTO, self.ANCHO, 0.78
        )
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

    def test_el_golpe_entra_rapido_se_pasa_y_vuelve(self):
        """Sin sobrepaso el movimiento es tan suave que en el video no se nota."""
        ritmo = escena.ritmo_de_golpe(2.0)
        self.assertAlmostEqual(ritmo(0.0), 0.0, places=6)
        self.assertAlmostEqual(ritmo(1.0), 1.0, places=6)
        maximo = max(ritmo(k / 200) for k in range(201))
        self.assertGreater(maximo, 1.9)
        self.assertLessEqual(maximo, 2.0 + 1e-9)

    def test_el_pico_del_golpe_pasa_poco_del_borde_seguro(self):
        """El golpe dura un instante, pero no tanto como para cortar una tarjeta de lado a lado."""
        hoja = escena.Paisaje(5.8, 0.1, 7.0)
        seguro = escena.encuadre(0.0, 0.4, hoja, self.ALTO, self.ANCHO, 0.0)[0]
        pico = escena.pico_del_golpe(hoja, self.ANCHO, "suave")
        self.assertLess(pico, seguro)
        self.assertGreaterEqual(pico, seguro - escena.GOLPE["suave"] - 1e-9)
        self.assertLess(escena.pico_del_golpe(hoja, self.ANCHO, "fuerte"), pico)

    def test_el_paisaje_sale_del_marco_del_tema(self):
        from tpi_videos.config import Marca
        from tpi_videos.temas import cargar_tema

        hoja = escena.paisaje_del_tema(cargar_tema("hoja_de_desarrollo", Marca()))
        pizarra = escena.paisaje_del_tema(cargar_tema("plano_azul", Marca()))
        self.assertAlmostEqual(hoja.centro_y, 0.1)
        self.assertGreater(pizarra.medio_alto, hoja.medio_alto)
        self.assertAlmostEqual(hoja.ancho_util, 7.0)
        self.assertAlmostEqual(pizarra.ancho_util, 7.6)
        # El paneo horizontal se detiene en el borde del fondo: la hoja es más angosta que la pizarra.
        self.assertAlmostEqual(hoja.medio_ancho, 3.95)
        self.assertGreater(pizarra.medio_ancho, hoja.medio_ancho)


@unittest.skipUnless(escena is not None, "manim no está instalado")
class PrimerPlanoTest(unittest.TestCase):
    """La toma cerrada de un término: el encuadre lo manda el bulto, no lo ancho de la hoja."""

    ALTO = 16.0
    ANCHO = 9.0
    PIZARRA = escena.Paisaje(7.9, 0.0, 7.6)

    def encuadra(self, x=0.0, y=0.0, ancho=1.0, alto=0.6, paisaje=None):
        return escena.encuadre_primer_plano(
            x, y, ancho, alto, paisaje or self.PIZARRA, self.ALTO, self.ANCHO
        )

    def test_entra_mucho_mas_de_lo_que_permite_el_plano_general(self):
        """El plano general no puede pasar de 0,86; si el primer plano tampoco, no hay dinamismo."""
        escala, _, _ = self.encuadra(ancho=1.2)
        self.assertLess(escala, (self.PIZARRA.ancho_util + escena.HOLGURA_ANCHO) / self.ANCHO)

    def test_un_termilio_no_se_vuelve_un_macro_inlegible(self):
        """Un «16» aislado podría llenar el cuadro; el freno es la legibilidad, no el fondo."""
        for ancho, alto in ((0.2, 0.2), (0.5, 0.4), (0.7, 0.3)):
            self.assertAlmostEqual(self.encuadra(ancho=ancho, alto=alto)[0], escena.MINIMA_PRIMER_PLANO)
        self.assertEqual(self.encuadra(ancho=0.01)[0], escena.MINIMA_PRIMER_PLANO)

    def test_se_abre_hasta_no_cortar_lo_destacado(self):
        """Un renglón entero destacado no cabe en un primer plano cerrado: la toma se abre."""
        escala, _, _ = self.encuadra(ancho=4.0, alto=0.9)
        self.assertGreaterEqual(self.ANCHO * escala, 4.0 + escena.AIRE_PRIMER_PLANO - 1e-9)
        self.assertLess(escala, 1.0)

    def test_si_lo_destacado_llena_el_cuadro_no_hay_toma_que_hacer(self):
        """Ya no se puede abrir más: en vez de cortar, se queda en el plano general."""
        self.assertAlmostEqual(self.encuadra(ancho=6.0, alto=0.9)[0], 1.0)

    def test_un_bulto_alto_y_angosto_se_mide_por_su_alto(self):
        angosto = self.encuadra(ancho=0.5, alto=4.0)[0]
        cuadro = self.encuadra(ancho=0.5, alto=0.5)[0]
        self.assertGreater(angosto, cuadro)

    def test_se_corre_hacia_lo_destacado(self):
        """La cámara ya no se queda fija en x=0: persigue el término por toda la hoja."""
        escala, x, y = self.encuadra(x=1.8, y=1.1)
        self.assertAlmostEqual(x, 1.8)
        self.assertAlmostEqual(y, 1.1)
        # El cuadro entero cabe dentro del fondo dibujado: ahí termina el paneo.
        self.assertLessEqual(abs(x) + self.ANCHO * escala / 2, self.PIZARRA.medio_ancho + 1e-9)

    def test_el_borde_del_fondo_frena_el_paneo(self):
        """En la hoja el papel es angosto: un término en la orilla no puede quedar al centro."""
        hoja = escena.Paisaje(5.8, 0.1, 7.0, 3.95)
        escala, x, _ = escena.encuadre_primer_plano(6.0, 0.0, 1.0, 0.6, hoja, self.ALTO, self.ANCHO)
        self.assertLess(x, 6.0)
        self.assertAlmostEqual(x, hoja.medio_ancho - self.ANCHO * escala / 2)

    def test_el_centro_vertical_tampoco_se_sale_del_fondo(self):
        _, _, y = self.encuadra(y=9.0)
        escala = self.encuadra(y=9.0)[0]
        self.assertAlmostEqual(abs(y), self.PIZARRA.medio_alto - self.ALTO * escala / 2)

    def test_nunca_se_aleja_del_cuadro_completo(self):
        self.assertEqual(self.encuadra(ancho=9.0, alto=8.0)[0], 1.0)


@unittest.skipUnless(escena is not None, "manim no está instalado")
class DerivaTest(unittest.TestCase):
    """La cámara en mano: el cuadro se desliza en las pausas, sin salirse de lo dibujado."""

    ALTO = 16.0
    ANCHO = 9.0

    def test_arranca_en_el_reposo(self):
        """Si el primer deslizamiento ya hubiera avanzado, la pausa se vería como un salto."""
        self.assertEqual(escena.deriva_desplazamiento(0.0), (0.0, 0.0, 0.0))

    def test_el_deslizamiento_se_nota_sin_ser_mareante(self):
        recorrido = [escena.deriva_desplazamiento(t / 10) for t in range(0, 600)]
        apartada = max(abs(x) for x, _, _ in recorrido)
        self.assertGreater(apartada, 0.2)
        self.assertLessEqual(apartada, escena.ALCANCE_DERIVA + 1e-9)

    def test_sub_y_baja_menos_de_lo_que_lado_a_lado(self):
        """El papel casi no deja mover la cámara en alto; el vaivén vertical es la mitad de corto."""
        recorrido = [escena.deriva_desplazamiento(t / 10) for t in range(0, 600)]
        self.assertLess(max(abs(y) for _, y, _ in recorrido), 0.75 * escena.ALCANCE_DERIVA)

    def test_respira_hacia_adentro_y_nunca_mas_alla_de_lo_pedido(self):
        """En la hoja el paneo no tiene adónde ir: el acercamiento es lo único que siempre se ve."""
        respiración = [dz for _, _, dz in (escena.deriva_desplazamiento(t / 10) for t in range(0, 600))]
        self.assertGreater(max(respiración), 0.04)
        self.assertLessEqual(min(respiración), 1e-9)
        self.assertGreaterEqual(min(respiración), 0.0)

    def test_no_repite_el_mismo_recorrido_dentro_de_un_video(self):
        vistos = {tuple(round(v, 2) for v in escena.deriva_desplazamiento(t)) for t in range(0, 45)}
        self.assertGreater(len(vistos), 40)

    def test_el_cuadro_jamas_salir_de_lo_dibujado(self):
        """Pase lo que pase con la toma, el deslizamiento se frena en el borde del fondo."""
        paisajes = (escena.Paisaje(7.9, 0.0, 7.6), escena.Paisaje(5.8, 0.1, 7.0, 3.95))
        for paisaje in paisajes:
            for escala in (1.0, 0.86, 0.6, 0.46):
                for t in range(1, 80):
                    dx, dy, _dz = escena.deriva_desplazamiento(t * 0.7)
                    x = escena._centro_x(0.4 + dx, escala, self.ANCHO, paisaje)
                    y = escena._centro_y(2.0 + dy, escala, self.ALTO, paisaje)
                    libre_x = max(0.0, paisaje.medio_ancho - self.ANCHO * escala / 2)
                    libre_y = max(0.0, paisaje.medio_alto - self.ALTO * escala / 2)
                    self.assertLessEqual(abs(x), libre_x + 1e-9)
                    self.assertLessEqual(abs(y - paisaje.centro_y), libre_y + 1e-9)


@unittest.skipUnless(escena is not None, "manim no está instalado")
class DerivaEnLaEscenaTest(unittest.TestCase):
    """Qué hace la escena con la cámara en mano, probado sin renderizar el video."""

    class _Frame:
        """El cuadro de la cámara: anota a dónde lo mandan en vez de animarse."""

        def __init__(self):
            self.ancho = None
            self.destino = None

        @property
        def animate(self):
            return lambda **_kwargs: self

        def set(self, width=None):
            self.ancho = width
            return self

        def move_to(self, punto):
            self.destino = punto
            return self

    class _Trampa(escena.VideoEjercicio):
        """Lo mínimo que necesitan ``wait`` y ``_mover_camara`` para ejercitarse de verdad.

        Hereda de la escena para que el ``super().wait`` de la receta quieta llegue al ``Wait``
        de siempre; no pasa por ``__init__`` porque aquí solo interesa la aritmética de la cámara.
        """

        def __init__(self, deriva="en_mano", modo="suave"):
            from tpi_videos.rodaje import Receta

            self.receta = Receta("ancla", "sale", "ninguno", "destacar", "lleno", deriva, "seguida", "visible")
            self.modo_camara = modo
            self.paisaje = escena.Paisaje(7.9, 0.0, 7.6)
            self.alto_cuadro, self.ancho_cuadro = 16.0, 9.0
            self._camara_escala = self._camara_ancho = 0.86
            self._camara_centro, self._camara_centro_x = 1.0, 0.0
            self._deriva_base_x, self._deriva_base_y, self._deriva_t = 0.0, 1.0, 0.0
            self._cabecera_fija, self._cabecera_visible, self._camara_cerca = None, True, 1.0
            self._cuadro = DerivaEnLaEscenaTest._Frame()
            self.jugadas = []

        @property
        def camera(self):
            return type("Cam", (), {"frame": self._cuadro})()

        def validate_run_time(self, run_time, method, parameter_name):
            return run_time

        def play(self, *animaciones, run_time=None):
            self.jugadas.append((animaciones, run_time))

    def test_la_pausa_se_desliza_y_no_se_congela(self):
        trampa = self._Trampa()
        trampa.wait(1.2)
        (animaciones, run_time), = trampa.jugadas
        self.assertEqual(len(animaciones), 1)
        self.assertEqual(run_time, 1.2)  # la pausa no cuesta ni un décimo más
        self.assertAlmostEqual(trampa._deriva_t, 1.2)

    def test_sin_deriva_la_pausa_sigue_siendo_una_espera(self):
        from manim import Wait

        trampa = self._Trampa(deriva="fija")
        trampa.wait(1.2)
        (animaciones, _), = trampa.jugadas
        self.assertIsInstance(animaciones[0], Wait)
        self.assertEqual(trampa._deriva_t, 0.0)

    def test_con_la_camara_quieta_tampoco_se_mueve(self):
        from manim import Wait

        trampa = self._Trampa(modo="quieta")
        trampa.wait(1.2)
        self.assertIsInstance(trampa.jugadas[0][0][0], Wait)

    def test_una_pausa_cortisima_no_alcanza_a_verse(self):
        from manim import Wait

        trampa = self._Trampa()
        trampa.wait(escena.PAUSA_MINIMA_DERIVA - 0.01)
        self.assertIsInstance(trampa.jugadas[0][0][0], Wait)
        self.assertEqual(trampa._deriva_t, 0.0)

    def test_el_reposo_de_la_toma_no_se_arrastra(self):
        """El golpe manda el encuadre; el vaivén se mide desde ahí y no se acumula de pausa en pausa."""
        trampa = self._Trampa()
        for _ in range(40):
            trampa.wait(1.0)
            apartada = abs(trampa._cuadro.destino[0] - trampa._deriva_base_x)
            self.assertLessEqual(apartada, escena.ALCANCE_DERIVA + 1e-9)
        self.assertEqual((trampa._deriva_base_x, trampa._deriva_base_y), (0.0, 1.0))

    def test_la_toma_respira_aun_cuando_el_paneo_no_tiene_adonde_ir(self):
        """En la hoja el papel es casi del ancho del cuadro: el acercamiento es lo que se ve.

        La onda se frena en sus punteras, como una mano de verdad, así que no cada pausa mueve algo;
        lo que no puede pasar es que el cuadro se quede quieto media minuto.
        """
        hoja = escena.Paisaje(5.8, 0.1, 7.0, 3.95)
        trampa = self._Trampa()
        trampa.paisaje = hoja
        trampa._camara_escala = trampa._camara_ancho = 0.97
        anchos = []
        for k in range(1, 25):
            if trampa._mover_camara(0.97, 0.0, 0.0, 1.0):
                anchos.append(trampa._camara_ancho)
        self.assertGreaterEqual(len(anchos), 15)
        self.assertLess(min(anchos), 0.94)  # se mete de verdad en el cuadro
        self.assertLessEqual(max(anchos), 0.97 + 1e-9)  # y nunca se abre más de lo pedido

    def test_el_golpe_sigue_llegando_a_su_encuadre(self):
        """Con la receta en_mano el destino declarado de la toma queda anotado como reposo."""
        trampa = self._Trampa()
        trampa._mover_camara(0.8, 1.2, 2.5, 0.5)
        self.assertEqual((trampa._deriva_base_x, trampa._deriva_base_y), (1.2, 2.5))
        self.assertEqual(trampa._camara_escala, 0.8)  # el reposo sigue siendo el encuadre del golpe
        x, y, _ = trampa._cuadro.destino
        self.assertNotEqual((round(x, 3), round(y, 3)), (1.2, 2.5))  # llega corrida por el vaivén
        self.assertLessEqual(abs(x - 1.2), escena.ALCANCE_DERIVA + 1e-9)

    def test_la_deriva_nunca_saca_el_cuadro_del_fondo(self):
        """Pase lo que pase con la toma, el deslizamiento se frena en el borde de lo dibujado."""
        for paisaje in (escena.Paisaje(7.9, 0.0, 7.6), escena.Paisaje(5.8, 0.1, 7.0, 3.95)):
            for escala in (1.0, 0.86, 0.6, 0.46):
                for t in range(1, 80):
                    e, x, y = escena.encuadre_con_deriva(0.4, 2.0, escala, t * 0.7, paisaje, 16.0, 9.0)
                    self.assertLessEqual(e, escala + 1e-9)  # respira hacia adentro, nunca se abre
                    libre_x = max(0.0, paisaje.medio_ancho - 9.0 * e / 2)
                    libre_y = max(0.0, paisaje.medio_alto - 16.0 * e / 2)
                    self.assertLessEqual(abs(x), libre_x + 1e-9)
                    self.assertLessEqual(abs(y - paisaje.centro_y), libre_y + 1e-9)


@unittest.skipUnless(escena is not None, "manim no está instalado")
class GanchoLlenoTest(unittest.TestCase):
    """El gancho que ocupa todo el cuadro: ni baja a la banda de los subtítulos ni tapa la cabecera."""

    def test_deja_libre_la_banda_de_los_subtitulos(self):
        self.assertGreater(
            escena.Y_GANCHO_LLENO - escena.ALTO_GANCHO_LLENO / 2, escena.Y_SOBRE_SUBTITULOS
        )

    def test_deja_arriba_el_sitio_de_la_marca(self):
        """En los dos marcos la cabecera vive en 6,5 o más: ahí el bloque lleno no llega."""
        self.assertLess(escena.Y_GANCHO_LLENO + escena.ALTO_GANCHO_LLENO / 2, 6.5)

    def test_la_pregunta_se_ve_un_tercio_mas_grande(self):
        self.assertGreaterEqual(escena.ESCALA_GANCHO_LLENO, 1.3)
