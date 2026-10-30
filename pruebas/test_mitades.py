"""Las dos mitades del tablero partido (``partida: mitades``): dónde cae cada una y si la cámara
alcanza a mirarlas por separado.

Todo es geometría pura, medida con el cuadro vertical del motor y el paisaje de la hoja cuadriculada
(el marco de los moldes que vienen partido)."""

import unittest

from tpi_videos.dibujos import ALTO_DIBUJO
from tpi_videos.escena import (
    AIRE_CASILLERO,
    ANCHO_CASILLERO,
    BANDA_SUBTITULO,
    HOLGURA_ANCHO,
    Paisaje,
    casilleros_de_mitades,
    encuadre_de_casillero,
)

ALTO_CUADRO, ANCHO_CUADRO = 14.222, 8.0
HOJA = Paisaje(5.8, 0.1, 7.0, 3.95)  # el papel: 11,6 de alto centrado en 0,1
TOPE, FONDO = 4.55, -3.55  # la banda de pasos entera (sin dibujo)


def _toma(y_linea: float, alto: float = 1.4):
    return encuadre_de_casillero(ANCHO_CASILLERO, alto, y_linea, HOJA, ALTO_CUADRO, ANCHO_CUADRO)


class CasillerosTest(unittest.TestCase):
    def test_cada_mitad_ocupa_la_suya_sin_pisarse(self):
        """La línea de arriba termina justo en la raya y la de abajo empieza debajo de ella."""
        arriba, abajo = casilleros_de_mitades(TOPE, FONDO).values()
        _, y_linea, alto_max = arriba
        self.assertAlmostEqual(y_linea - alto_max / 2, (TOPE + FONDO) / 2, places=6)
        _, y_b, alto_b = abajo
        self.assertLessEqual(y_b + alto_b / 2, (TOPE + FONDO) / 2 + 1e-6)
        self.assertAlmostEqual(y_b - alto_b / 2, FONDO, places=6)

    def test_los_rotulos_quedan_arriba_de_su_linea_y_dentro_de_la_hoja(self):
        cas = casilleros_de_mitades(TOPE, FONDO)
        self.assertGreater(cas["arriba"][0], cas["arriba"][1])
        self.assertGreater(cas["abajo"][0], cas["abajo"][1])
        self.assertLessEqual(cas["arriba"][0] + 0.3, TOPE + 0.35)  # la etiqueta no se sale del techo

    def test_con_dibujo_el_casillero_de_abajo_se_corre_por_encima_de_la_franja(self):
        """La franja del dibujo se reserva desde el primer paso: si no, el casillero saltaría al entrar."""
        fondo = FONDO + 3.3 + 0.28  # ALTO_DIBUJO + el aire que le da la escena
        _, y_linea, alto_max = casilleros_de_mitades(TOPE, fondo)["abajo"]
        self.assertGreaterEqual(y_linea - alto_max / 2, fondo - 1e-6)


class TomaDeMitadTest(unittest.TestCase):
    def test_la_camara_entra_hasta_el_casillero(self):
        escala, _, _ = _toma(casilleros_de_mitades(TOPE, FONDO)["arriba"][1])
        self.assertLess(escala, 0.75, "más abierta que esto no hay casillero que se aísle")

    def test_bajar_del_mito_a_la_realidad_es_un_tramo_de_verdad(self):
        """Lo que se cobra la tanda: los dos destinos no pueden ser el mismo cuadro."""
        cas = casilleros_de_mitades(TOPE, FONDO)
        _, _, arriba_y = _toma(cas["arriba"][1])
        _, _, abajo_y = _toma(cas["abajo"][1])
        self.assertGreater(
            arriba_y - abajo_y,
            3.0,
            f"la cámara solo se inclina {arriba_y - abajo_y:.2f}: no se lee que son dos mitades",
        )

    def test_ninguna_toma_descubre_el_escritorio(self):
        cas = casilleros_de_mitades(TOPE, FONDO)
        for clave in ("arriba", "abajo"):
            escala, _, centro = _toma(cas[clave][1])
            borde = HOJA.medio_alto - ALTO_CUADRO * escala / 2
            self.assertLessEqual(abs(centro - HOJA.centro_y), borde + 1e-6, clave)

    def test_el_casillero_cabe_entero_en_su_toma(self):
        """Si la toma recortara el casillero por los lados, la mitad partida se leería a medias."""
        cas = casilleros_de_mitades(TOPE, FONDO)
        for clave in ("arriba", "abajo"):
            escala, centro_x, centro_y = _toma(cas[clave][1])
            visible_ancho, visible_alto = ANCHO_CUADRO * escala, ALTO_CUADRO * escala
            self.assertGreaterEqual(visible_ancho, ANCHO_CASILLERO + 0.4, clave)
            self.assertLess(abs(cas[clave][1] - centro_y) - visible_alto / 2, 0.0, clave)

    def test_la_toma_mas_abierta_que_pide_el_ancho_sigue_siendo_el_techo(self):
        """Un casillero angosto deja entrar; uno ancho (la hoja entera) no: la toma no se inventa sitio."""
        ancha = encuadre_de_casillero(
            7.0, 1.4, casilleros_de_mitades(TOPE, FONDO)["arriba"][1], HOJA, ALTO_CUADRO, ANCHO_CUADRO
        )
        angosta = _toma(casilleros_de_mitades(TOPE, FONDO)["arriba"][1])
        self.assertLess(angosta[0], ancha[0])


class DibujoEnCasilleroTest(unittest.TestCase):
    """El casillero que lleva el dibujo encima: la toma lo encuadra, pero no lo mete al subtítulo."""

    ANCHO = ANCHO_CASILLERO - 0.3  # lo que la escena le deja al visual cuando el tablero está partido
    CENTRO = -1.76  # el hexágono del video de la apotema: franja reservada hasta el fondo de la hoja

    def en_pantalla(self, y: float, centro: float, escala: float) -> float:
        """Dónde cae esa altura de la pizarra en el cuadro: 0 arriba, 1 abajo."""
        return 0.5 + (centro - y) / (ALTO_CUADRO * escala)

    def toma(self):
        return encuadre_de_casillero(self.ANCHO, ALTO_DIBUJO, self.CENTRO, HOJA, ALTO_CUADRO, ANCHO_CUADRO)

    def test_el_borde_del_dibujo_no_le_baja_al_subtitulo(self):
        """A 24,0 s el filo de abajo de la tarjeta cruzaba la palabra amarilla: la toma se mete más."""
        escala, _, centro = self.toma()
        fondo = self.CENTRO - ALTO_DIBUJO / 2
        self.assertLessEqual(self.en_pantalla(fondo, centro, escala), 1.0 - BANDA_SUBTITULO + 1e-6)

    def test_y_aun_asi_el_dibujo_se_ve_entero(self):
        """Cerrar la toma no vale nada si corta el hexágono por arriba."""
        escala, _, centro = self.toma()
        tope = self.CENTRO + ALTO_DIBUJO / 2
        self.assertGreaterEqual(self.en_pantalla(tope, centro, escala), 0.05)

    def test_una_linea_fina_no_se_mueve_por_esta_regla(self):
        """El casillero de una sola fórmula ya estaba lejos de la banda: no hay por qué achicarlo."""
        escala, _, centro = encuadre_de_casillero(ANCHO_CASILLERO, 1.4, -1.5, HOJA, ALTO_CUADRO, ANCHO_CUADRO)
        self.assertAlmostEqual(escala, (ANCHO_CASILLERO + AIRE_CASILLERO + HOLGURA_ANCHO) / ANCHO_CUADRO, places=6)
        self.assertAlmostEqual(centro, -1.5, places=6)


if __name__ == "__main__":
    unittest.main()
