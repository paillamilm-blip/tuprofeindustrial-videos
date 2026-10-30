"""La tarjeta «Cómo se graba cada molde» de Ajustes: qué filas muestra y qué resumen escribe.

Como en el resto del panel, la lógica va fuera de los widgets para poder probarla sin navegador.
"""

import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import mkdtemp

import tpi_videos.rodaje as rodaje
from tpi_videos.panel.paginas.ajustes import filas_de_rodaje, resumen_de_receta
from tpi_videos.rodaje import campos_de_receta, guardar_receta

FILA = tuple  # mando, nombre, frase de hoy, opciones, valor activo


@contextmanager
def _recetas_del_autor(texto: str):
    ruta = Path(mkdtemp()) / "rodaje.yaml"
    ruta.write_text(texto, encoding="utf-8")
    original = rodaje._ruta_usuario
    rodaje._ruta_usuario = lambda: ruta
    try:
        yield ruta
    finally:
        rodaje._ruta_usuario = original


def _fila(filas: list[FILA], mando: str) -> FILA:
    return next(f for f in filas if f[0] == mando)


class FilasTest(unittest.TestCase):
    def test_una_fila_por_mando_con_dos_opciones_y_su_valor_marcado(self):
        """La regla del autor: cada decisión se ve con su valor y con una forma de cambiarla."""
        filas = filas_de_rodaje(campos_de_receta("mito_realidad"))
        self.assertEqual([mando for mando, *_ in filas], list(rodaje.NOMBRE_MANDO))
        for mando, nombre, frase, opciones, actual in filas:
            self.assertTrue(nombre.strip() and frase.strip(), mando)
            self.assertEqual(len(opciones), 2, mando)
            self.assertIn(actual, [valor for valor, _ in opciones], mando)

    def test_muestra_lo_que_me_guardo_no_lo_que_trae_el_motor(self):
        """El motor tapa el resultado del reto; si el autor lo destapó, eso es lo que se lee."""
        valores = {**campos_de_receta("reto"), "tapar_resultado": "visible"}
        self.assertEqual(campos_de_receta("reto")["tapar_resultado"], "tapada")
        with _recetas_del_autor(""):
            guardar_receta("reto", valores)
            filas = filas_de_rodaje(campos_de_receta("reto"))
        fila = _fila(filas, "tapar_resultado")
        self.assertEqual(fila[2], rodaje.QUE_HACE["tapar_resultado"]["visible"])
        self.assertEqual(fila[4], "visible")

    def test_cada_fila_ofrece_las_dos_opciones_con_su_frase(self):
        filas = filas_de_rodaje(campos_de_receta("pov"))
        for mando, _, _, opciones, _ in filas:
            self.assertEqual([v for v, _ in opciones], list(rodaje.QUE_HACE[mando]))


class ResumenTest(unittest.TestCase):
    def test_el_resumen_nombre_el_molde_y_lista_los_ocho_mandos(self):
        valores = campos_de_receta("mito_realidad")
        texto = resumen_de_receta("mito_realidad", valores)
        self.assertIn("mito_realidad", texto)
        for _, _, frase, _, _ in filas_de_rodaje(valores):
            self.assertIn(frase, texto)

    def test_el_resumen_se_reescribe_al_cambiar_un_mando(self):
        valores = campos_de_receta("pov")
        self.assertNotEqual(resumen_de_receta("pov", valores),
                            resumen_de_receta("pov", {**valores, "deriva": "fija"}))


if __name__ == "__main__":
    unittest.main()
