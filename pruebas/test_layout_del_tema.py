"""La diagramación vive en el tema y no en el código.

Dos cosas que no se pueden perder: los estilos que ya existen tienen que verse exactamente igual
(un tema sin `layout` conserva las zonas de su marco), y el estilo activo no puede pasar de un
render a otro cuando dos corren en el mismo proceso.
"""

import threading
import unittest
from contextlib import contextmanager
from typing import Any

import yaml

from tpi_videos import componentes, temas
from tpi_videos.escena import Paisaje, franja_del_dibujo

TEMAS = temas.TEMAS_DIR
ZONAS_DE_HOY = {  # (cabecera, techo de la zona, piso de la zona) que usa cada marco desde siempre
    "pizarra": (6.55, 4.75, -2.4),
    "hoja": (6.5, 4.15, -3.55),
}


@contextmanager
def estilo(tema: temas.Tema):
    token = componentes.usar_estilo(tema)
    try:
        yield
    finally:
        componentes.restablecer_estilo(token)


def tema_con(layout: dict[str, Any] | None = None, **datos: Any) -> temas.Tema:
    datos.setdefault("nombre", "prueba")
    if layout is not None:
        datos["layout"] = layout
    return temas.Tema.model_validate(datos)


class LayoutDelTemaTest(unittest.TestCase):
    def test_un_tema_sin_layout_conserva_las_zonas_del_marco(self) -> None:
        """Ninguno de los 19 temas de fábrica declara layout: tienen que seguir igual."""
        for ruta in sorted(TEMAS.glob("*.yaml")):
            crudo = yaml.safe_load(ruta.read_text(encoding="utf-8"))
            self.assertNotIn("layout", crudo, ruta.name)
            tema = temas.Tema.model_validate(crudo)
            with estilo(tema):
                vistos = (
                    componentes.Y_CABECERA,
                    componentes.Y_ZONA_SUPERIOR,
                    componentes.Y_ZONA_INFERIOR,
                )
            self.assertEqual(vistos, ZONAS_DE_HOY[tema.marco], ruta.name)

    def test_sin_tema_las_funciones_sueltas_usan_las_constantes_de_siempre(self) -> None:
        self.assertEqual(componentes.Y_CABECERA, 6.55)
        self.assertEqual(componentes.Y_ZONA_SUPERIOR, 4.75)
        self.assertEqual(componentes.BANDA_SUBTITULO, 0.28)
        self.assertEqual(componentes.AIRE_DIBUJO, 0.28)

    def test_el_yaml_del_tema_manda_sobre_la_diagramacion(self) -> None:
        tema = tema_con(
            {"y_cabecera": 6.2, "y_zona_enunciado": 4.4, "y_zona_pasos": -2.0,
             "banda_subtitulo": 0.34, "aire_dibujo": 0.12}
        )  # fmt: skip
        with estilo(tema):
            self.assertEqual(componentes.Y_CABECERA, 6.2)
            self.assertEqual(componentes.Y_ZONA_SUPERIOR, 4.4)
            self.assertEqual(componentes.Y_ZONA_INFERIOR, -2.0)
            self.assertAlmostEqual(componentes.CENTRO_ZONA, 1.2)
            self.assertAlmostEqual(componentes.ALTO_ZONA, 6.4)
            self.assertEqual(componentes.BANDA_SUBTITULO, 0.34)
            self.assertEqual(componentes.AIRE_DIBUJO, 0.12)

    def test_la_banda_del_subtitulo_mueve_el_piso_del_dibujo(self) -> None:
        paisaje = Paisaje(medio_alto=5.8, centro_y=5.0, ancho_util=7.0)
        fondo, centro, alto = franja_del_dibujo(paisaje, 16.0, 1.0, 0.0, 4.0)
        with estilo(tema_con({"banda_subtitulo": 0.34})):
            desplazado = franja_del_dibujo(paisaje, 16.0, 1.0, 0.0, 4.0)
        self.assertEqual(desplazado[0], fondo)  # el aire no cambió: el filo del dibujo queda igual
        self.assertGreater(desplazado[1], centro)  # más banda: los pasos se detienen más arriba
        self.assertLess(desplazado[2], alto)  # y la franja del dibujo cede ese tramo

    def test_el_aire_del_dibujo_sale_del_tema(self) -> None:
        paisaje = Paisaje(medio_alto=5.8, centro_y=5.0, ancho_util=7.0)
        con_lo_de_siempre = franja_del_dibujo(paisaje, 16.0, 1.0, 0.0, 4.0)
        with estilo(tema_con({"aire_dibujo": 0.12})):
            movido = franja_del_dibujo(paisaje, 16.0, 1.0, 0.0, 4.0)
        self.assertAlmostEqual(movido[0], con_lo_de_siempre[0] - 0.16)

    def test_dos_hilos_con_estilos_distintos_no_se_pisan(self) -> None:
        listos = threading.Barrier(2)
        vistos: dict[str, float] = {}

        def correr(nombre: str, tema: temas.Tema) -> None:
            token = componentes.usar_estilo(tema)
            try:
                listos.wait(timeout=5)
                vistos[nombre] = componentes.Y_CABECERA
            finally:
                componentes.restablecer_estilo(token)

        hilos = [
            threading.Thread(target=correr, args=("primero", tema_con({"y_cabecera": 6.2}))),
            threading.Thread(target=correr, args=("segundo", tema_con({"y_cabecera": 6.4}))),
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=5)
            self.assertFalse(hilo.is_alive())
        self.assertEqual(vistos, {"primero": 6.2, "segundo": 6.4})
        self.assertEqual(componentes.Y_CABECERA, 6.55)  # el hilo principal no quedó tocado

    def test_restablecer_vuelve_al_estilo_anterior(self) -> None:
        token_hoja = componentes.usar_estilo(tema_con(marco="hoja"))
        token_pizarra = componentes.usar_estilo(tema_con(marco="pizarra"))
        try:
            self.assertEqual(componentes.Y_CABECERA, 6.55)
            componentes.restablecer_estilo(token_pizarra)
            self.assertEqual(componentes.Y_CABECERA, 6.5)
        finally:
            componentes.restablecer_estilo(token_hoja)
        self.assertEqual(componentes.Y_CABECERA, 6.55)
