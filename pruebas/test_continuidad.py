"""El dibujo que se queda entre pasos: cuándo sigue y qué piezas cambian (sin Manim)."""

import unittest
from types import SimpleNamespace

from tpi_videos.continuidad import cambia_de_tipo, campos_del_visual, emparejar, repartir_salida, sigue

LAZO = {"tipo": "bloques", "adelante": "8", "retro": "0.5"}
LATA = {"tipo": "solido_3d", "figura": "cilindro", "radio": "3 cm", "altura": "5 cm"}


class SigueTest(unittest.TestCase):
    def test_el_mismo_dibujo_con_otra_marca_sigue(self):
        self.assertTrue(sigue({**LAZO, "anotar": ["malla"]}, {**LAZO, "anotar": ["lazo_cerrado"]}))

    def test_cambiar_la_vista_o_el_despiece_sigue(self):
        self.assertTrue(sigue({**LATA, "vista": "piso"}, {**LATA, "vista": "axonometrica", "despiece": True}))

    def test_otros_numeros_no_siguen(self):
        self.assertFalse(sigue(LAZO, {**LAZO, "adelante": "10"}))

    def test_otro_tipo_no_sigue(self):
        self.assertFalse(sigue(LAZO, LATA))

    def test_otro_tamano_no_sigue(self):
        self.assertFalse(sigue({**LAZO, "tamano": "chico"}, {**LAZO, "tamano": "grande"}))
        self.assertTrue(sigue({**LAZO, "tamano": "chico"}, {**LAZO, "tamano": "chico"}))

    def test_sin_dibujo_antes_o_despues_no_sigue(self):
        self.assertFalse(sigue(None, LAZO))
        self.assertFalse(sigue(LAZO, None))

    def test_lee_un_visual_de_pydantic(self):
        visual = SimpleNamespace(tipo="bloques", model_dump=lambda **_: {"adelante": "8", "retro": "0.5"})
        self.assertEqual(campos_del_visual(visual), LAZO)
        self.assertIsNone(campos_del_visual(None))


class EmparejarTest(unittest.TestCase):
    def _repartir(self, viejas, nuevas):
        return emparejar(viejas, nuevas, lambda x: x["clave"], lambda x: x["clave"])

    def test_lo_identico_se_queda_lo_demas_sale_o_entra(self):
        viejas = [{"clave": "caja G"}, {"clave": "caja H"}, {"clave": "GH = 4"}]
        nuevas = [{"clave": "caja G"}, {"clave": "caja H"}, {"clave": "T = 1,6"}]
        quedan, salen, entran = self._repartir(viejas, nuevas)
        self.assertEqual(
            [(v["clave"], n["clave"]) for v, n in quedan], [("caja G", "caja G"), ("caja H", "caja H")]
        )
        self.assertEqual([v["clave"] for v in salen], ["GH = 4"])
        self.assertEqual([n["clave"] for n in entran], ["T = 1,6"])

    def test_las_claves_repetidas_se_emparejan_de_a_una(self):
        viejas = [{"clave": "letra"}, {"clave": "letra"}]
        nuevas = [{"clave": "letra"}, {"clave": "letra"}, {"clave": "letra"}]
        quedan, salen, entran = self._repartir(viejas, nuevas)
        self.assertEqual((len(quedan), len(salen), len(entran)), (2, 0, 1))
        self.assertEqual(len({id(v) for v, _ in quedan}), 2)  # cada vieja se usa una sola vez

    def test_si_nada_coincide_es_un_fundido_completo(self):
        quedan, salen, entran = self._repartir([{"clave": "a"}], [{"clave": "b"}])
        self.assertEqual((quedan, len(salen), len(entran)), ([], 1, 1))


class RepartirSalidaTest(unittest.TestCase):
    """El dibujo que no sigue: si el paso trae otro dibujo, se va con su entrada (fundido cruzado)."""

    def test_con_dibujo_nuevo_la_salida_viaja_con_el(self):
        self.assertEqual(repartir_salida(["viejo"], trae_dibujo=True), ([], ["viejo"]))

    def test_sin_dibujo_nuevo_sale_antes_como_siempre(self):
        self.assertEqual(repartir_salida(["viejo"], trae_dibujo=False), (["viejo"], []))

    def test_sin_nada_que_sacar_no_hay_fundido(self):
        self.assertEqual(repartir_salida([], trae_dibujo=True), ([], []))

class CambiaDeTipoTest(unittest.TestCase):
    """Solo el cambio de tipo de dibujo se funde cruzado: el mismo tipo con otros números se borra antes.

    Dos cubos de distinto lado en el mismo sitio se verían dobles mientras entra el nuevo.
    """

    def test_otro_tipo_se_funde_cruzado(self):
        self.assertTrue(cambia_de_tipo(LAZO, LATA))

    def test_el_mismo_tipo_con_otros_numeros_no(self):
        self.assertFalse(cambia_de_tipo({"tipo": "solido_3d", "lado": "4 cm"}, {"tipo": "solido_3d", "lado": "8 cm"}))

    def test_sin_dibujo_antes_o_ahora_no_hay_fundido(self):
        self.assertFalse(cambia_de_tipo(None, LATA))
        self.assertFalse(cambia_de_tipo(LAZO, None))


if __name__ == "__main__":
    unittest.main()
