"""El ritmo de lectura: cuánto necesita durar un guion para que sus fórmulas se puedan leer.

La voz manda en el render (manim-voiceover espera el audio), así que una fórmula dicha rápido vive
menos de dos segundos quieta. Estas pruebas fijan el modelo que estima ese tiempo y el piso que lo
garantiza, porque el panel lo muestra como valor elegible con su «cambiar».
"""

import unittest

from tpi_videos.guion import Guion
from tpi_videos.revision import necesita_segundos, revisar, segundos_a_esperar


def _guion(pasos, resultado_voz="Las dos soluciones son cero y cinco.", gancho_tex=None):
    datos = {
        "titulo": "El error al despejar",
        "materia": "matematica",
        "gancho": {"texto": "¿Por qué tachar la equis está mal?", "voz": "Por qué tachar la equis está mal"},
        "enunciado": {"texto": "Resuelve x² = 5x.", "voz": "Resolvamos la ecuación equis al cuadrado"},
        "pasos": pasos,
        "resultado": {"tex": "x_1 = 0, x_2 = 5", "voz": resultado_voz},
    }
    if gancho_tex:
        datos["gancho"]["tex"] = gancho_tex
    return Guion.model_validate(datos)


VOZ_LARGA = (
    "Aquí lo que hacemos es restar cinco equis a los dos lados para dejar el cero solo "
    "y poder factorizar sin perder ninguna solución del ejercicio completo."
)


class RitmoDeLecturaTest(unittest.TestCase):
    def test_una_formula_dicha_rapido_necesita_mas_pantalla(self):
        ritmo = necesita_segundos(_guion([{"voz": "Factorizo la equis.", "tex": "x (x - 5) = 0"}]), "Sígueme.")
        secciones = [s for s, _ in ritmo.estirados]
        self.assertIn("paso 1", secciones, "la fórmula se dice en ~1,4 s y no da tiempo a leerla")
        self.assertGreater(ritmo.segundos, ritmo.base)

    def test_un_bloque_sin_formula_no_pide_tiempo_de_lectura(self):
        ritmo = necesita_segundos(_guion([{"voz": "Factorizo la equis."}]), "Sígueme.")
        self.assertNotIn("paso 1", [s for s, _ in ritmo.estirados])

    def test_la_voz_larga_ya_deja_la_formula_quieta_sobra_tiempo(self):
        ritmo = necesita_segundos(_guion([{"voz": VOZ_LARGA, "tex": "x^2 - 5x = 0"}]), "Sígueme.")
        self.assertEqual(
            [s for s, _ in ritmo.estirados],
            ["resultado"],
            "un paso dicho en voz larga ya tiene su fórmula visible el tiempo suficiente",
        )
        self.assertEqual(ritmo.segundos, ritmo.base + sum(f for _, f in ritmo.estirados))

    def test_el_piso_es_un_valor_elegible(self):
        guion = _guion([{"voz": "Factorizo la equis.", "tex": "x (x - 5) = 0"}])
        sin_piso = necesita_segundos(guion, "Sígueme.", piso=0.0)
        self.assertEqual(sin_piso.estirados, [], "piso 0 es el video tal como sale hoy")
        self.assertEqual(sin_piso.segundos, sin_piso.base)
        corto = necesita_segundos(guion, "Sígueme.", piso=2.5)
        largo = necesita_segundos(guion, "Sígueme.", piso=3.5)
        self.assertGreater(largo.segundos, corto.segundos)

    def test_el_motivo_dice_cuantos_bloques_y_con_que_piso(self):
        ritmo = necesita_segundos(_guion([{"voz": "Factorizo la equis.", "tex": "x (x - 5) = 0"}]), "Sígueme.")
        self.assertIn("2 bloques", ritmo.motivo)
        self.assertIn("2,5 s", ritmo.motivo)


class CuantoEsperarTest(unittest.TestCase):
    """El render mide cuánto lleva la fórmula quieta y espera lo que falte; acá está esa resta."""

    def test_devuelve_lo_que_falta_hasta_el_piso(self):
        self.assertEqual(segundos_a_esperar(2.5, 1.0), 1.5)

    def test_si_ya_paso_el_piso_no_espera_nada(self):
        self.assertEqual(segundos_a_esperar(2.5, 3.0), 0.0)

    def test_piso_cero_es_el_video_de_hoy(self):
        self.assertEqual(segundos_a_esperar(0.0, 0.86), 0.0)


class RevisionConLecturaTest(unittest.TestCase):
    """La revisión del guion avisa las fórmulas que van a quedar cortas de lectura.

    Sale por el mismo camino del `tpi revisar` y de «La hoja» del panel, así el número no es un
    secreto del render: se ve antes de crear el video.
    """

    def test_la_revision_dice_cuantos_bloques_hay_que_estirar(self):
        guion = _guion([{"voz": "Factorizo la equis.", "tex": "x (x - 5) = 0"}])
        rev = revisar(guion, "Sígueme.")
        self.assertEqual([s for s, _ in rev.estirados], ["paso 1", "resultado"])
        aviso = next(a for a in rev.avisos if a.donde == "lectura")
        self.assertIn("2 bloques", aviso.mensaje)
        self.assertEqual(aviso.nivel, "sugerencia", "estirar la lectura no es un error del guion")

    def test_un_guion_que_ya_se_puede_leer_no_avisa_nada(self):
        rev = revisar(_guion([{"voz": VOZ_LARGA, "tex": "x^2 - 5x = 0"}], resultado_voz=VOZ_LARGA), "Sígueme.")
        self.assertEqual(rev.estirados, [])
        self.assertFalse(any(a.donde == "lectura" for a in rev.avisos))

    def test_la_revision_y_el_calculo_del_panel_usan_el_mismo_numero(self):
        guion = _guion([{"voz": "Factorizo la equis.", "tex": "x (x - 5) = 0"}])
        ritmo = necesita_segundos(guion, "Sígueme.")
        self.assertEqual(revisar(guion, "Sígueme.").estirados, ritmo.estirados)


if __name__ == "__main__":
    unittest.main()
