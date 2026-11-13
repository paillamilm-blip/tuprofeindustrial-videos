"""Herramientas de la explicación por guion: sugeridas por el contenido, sin tocar el estilo."""

import unittest
from copy import deepcopy

from pruebas.datos_didacticos import datos_base, datos_concepto
from tpi_videos.config import cargar_marca
from tpi_videos.didactica import RECURSOS, componer_tema, recursos_del_guion
from tpi_videos.guion import Guion
from tpi_videos.render import subtitulos_de
from tpi_videos.temas import Tema, cargar_tema


def _decisiones(guion, tema):
    return {d.clave: d for d in recursos_del_guion(guion, tema)}


def _con_pasos(n, *, error_en=None, mapa=False, contenido=True, recursos=None):
    datos = datos_concepto() if contenido else datos_base()
    datos["pasos"] = [{"voz": f"Paso {i}.", "tex": f"a = {i}"} for i in range(1, n + 1)]
    if error_en is not None:
        datos["pasos"][error_en]["error"] = True
    if mapa:
        datos["pasos"][0]["mapa"] = [{"termino": "a", "concepto": "arista"}]
    if recursos is not None:
        datos["recursos"] = recursos
    elif contenido:
        datos.pop("recursos", None)
    return Guion.model_validate(datos)


class RecursosTest(unittest.TestCase):
    def test_heredado_conserva_tema_entero(self):
        tema = Tema(nombre="Original", gramatica={"panel": True, "micro": True})
        antes = tema.model_dump()
        copia = componer_tema(tema, Guion.model_validate(datos_base()))
        self.assertEqual(copia.model_dump(), antes)
        self.assertEqual(tema.model_dump(), antes)
        self.assertIsNot(copia, tema)

    def test_false_manda_sobre_sugerencia_y_no_contamina_otro_video(self):
        tema = Tema(nombre="Hoja", marco="hoja")
        g = Guion.model_validate(datos_concepto())
        decisiones = _decisiones(g, tema)
        self.assertTrue(decisiones["panel"].sugerido)
        self.assertFalse(decisiones["panel"].activo)
        self.assertEqual(decisiones["panel"].origen, "guion")
        self.assertIn("fórmulas", decisiones["panel"].razon)
        self.assertFalse(componer_tema(tema, g).gramatica.panel)
        self.assertEqual(tema, Tema(nombre="Hoja", marco="hoja"))

    def test_orden_fijo(self):
        g = Guion.model_validate(datos_concepto())
        self.assertEqual([d.clave for d in recursos_del_guion(g, Tema(nombre="T"))], list(RECURSOS))
        self.assertEqual(RECURSOS, ("tabs", "panel", "mapa_color", "micro"))

    def test_tres_pasos_sugieren_tabs(self):
        d = _decisiones(_con_pasos(3), Tema(nombre="T"))
        self.assertTrue(d["tabs"].sugerido)
        self.assertTrue(d["tabs"].activo)
        self.assertEqual(d["tabs"].origen, "contenido")
        self.assertIn("3 pasos", d["tabs"].razon)

    def test_dos_pasos_no_sugieren_tabs(self):
        d = _decisiones(_con_pasos(2), Tema(nombre="T", gramatica={"tabs": True}))
        self.assertFalse(d["tabs"].activo)
        self.assertIn("Pocos pasos", d["tabs"].razon)

    def test_panel_cuenta_solo_formulas_correctas(self):
        # Dos pasos con fórmula, uno es error: queda una sola fórmula correcta → no hay qué resumir.
        d = _decisiones(_con_pasos(2, error_en=0), Tema(nombre="T", gramatica={"panel": True}))
        self.assertFalse(d["panel"].sugerido)
        d = _decisiones(_con_pasos(3, error_en=0), Tema(nombre="T"))
        self.assertTrue(d["panel"].sugerido)

    def test_panel_sin_formulas(self):
        g = _con_pasos(2)
        g = g.model_copy(update={"pasos": [p.model_copy(update={"tex": None}) for p in g.pasos]})
        d = _decisiones(g, Tema(nombre="T", gramatica={"panel": True}))
        self.assertFalse(d["panel"].sugerido)
        self.assertIn("No hay suficientes fórmulas", d["panel"].razon)

    def test_mapa_del_guion_sugiere_color(self):
        self.assertTrue(_decisiones(_con_pasos(2, mapa=True), Tema(nombre="T"))["mapa_color"].sugerido)
        d = _decisiones(_con_pasos(2), Tema(nombre="T", gramatica={"mapa_color": True}))
        self.assertFalse(d["mapa_color"].sugerido)
        self.assertIn("no trae relaciones", d["mapa_color"].razon)

    def test_mapa_activado_sin_datos_avisa_y_no_bloquea(self):
        g = _con_pasos(2, recursos={"mapa_color": True})
        d = _decisiones(g, Tema(nombre="T"))
        self.assertTrue(d["mapa_color"].activo)
        self.assertIn("no tendrá contenido", d["mapa_color"].razon)

    def test_micro_sugerido_apagado_sin_tocar_camara(self):
        g = _con_pasos(4)
        tema = Tema(nombre="T", gramatica={"micro": True})
        d = _decisiones(g, tema)
        self.assertFalse(d["micro"].sugerido)
        self.assertIn("puedes activarlo", d["micro"].razon)
        self.assertEqual(g.camara, "suave")
        self.assertFalse(componer_tema(tema, g).gramatica.micro)

    def test_null_hereda_sugerencia(self):
        g = _con_pasos(3, recursos={"tabs": None})
        d = _decisiones(g, Tema(nombre="T"))
        self.assertEqual(d["tabs"].origen, "contenido")
        self.assertTrue(d["tabs"].activo)

    def test_recursos_sin_contenido_heredan_el_tema_salvo_override(self):
        g = _con_pasos(3, contenido=False, recursos={"micro": False})
        tema = Tema(nombre="T", gramatica={"tabs": False, "panel": True, "micro": True})
        d = _decisiones(g, tema)
        self.assertEqual((d["tabs"].activo, d["tabs"].origen), (False, "tema"))
        self.assertEqual((d["panel"].activo, d["panel"].origen), (True, "tema"))
        self.assertEqual((d["micro"].activo, d["micro"].origen), (False, "guion"))
        compuesto = componer_tema(tema, g)
        self.assertEqual(
            (compuesto.gramatica.tabs, compuesto.gramatica.panel, compuesto.gramatica.micro), (False, True, False)
        )

    def test_la_variante_no_decide_las_herramientas(self):
        """Mito + ejercicio con fórmulas recibe panel aunque consola_mito no lo active; un dato sin
        fórmulas no lo recibe aunque consola_pasos sí lo active."""
        marca = cargar_marca()
        mito = cargar_tema("consola_mito", marca)
        pasos = cargar_tema("consola_pasos", marca)
        self.assertFalse(mito.gramatica.panel)
        self.assertTrue(pasos.gramatica.panel)
        datos = datos_concepto()
        datos.pop("recursos")
        datos["contenido"] = {"intenciones": ["mito", "ejercicio"], "objetivo": "Duplicar la arista."}
        datos["resultado"] = {"tex": "V = 8", "voz": "Ocho."}
        self.assertTrue(componer_tema(mito, Guion.model_validate(datos)).gramatica.panel)
        dato = Guion.model_validate(datos_concepto())
        dato = dato.model_copy(
            update={"recursos": None, "pasos": [p.model_copy(update={"tex": None}) for p in dato.pasos]}
        )
        self.assertFalse(componer_tema(pasos, dato).gramatica.panel)


class ComposicionTest(unittest.TestCase):
    def test_tema_propio_conserva_apariencia(self):
        tema = Tema(
            nombre="Mío", marco="hoja", resplandor=True, rotulo="MITO",
            colores={"acento": "#123456"}, fondo={"tipo": "imagen", "imagen": "difuminado"},
            tipografia={"titulos": {"familia": "Montserrat", "escala": 1.2}},
            gramatica={"paleta_pasos": ["#111111", "#222222"]},
        )  # fmt: skip
        compuesto = componer_tema(tema, _con_pasos(3, recursos={"panel": True}))
        for campo in ("nombre", "marco", "resplandor", "rotulo", "colores", "fondo", "tipografia", "hoja"):
            self.assertEqual(getattr(compuesto, campo), getattr(tema, campo), campo)
        self.assertEqual(compuesto.gramatica.paleta_pasos, ["#111111", "#222222"])
        self.assertTrue(compuesto.gramatica.panel)
        self.assertFalse(tema.gramatica.panel)

    def test_panel_nuevo_reserva_banda_en_hoja_y_pizarra(self):
        for marco in ("hoja", "pizarra"):
            tema = Tema(nombre="T", marco=marco)
            compuesto = componer_tema(tema, _con_pasos(3, recursos={"panel": True}))
            self.assertEqual(compuesto.layout.banda_panel, 1.6, marco)
            self.assertEqual(compuesto.layout.y_zona_pasos, -2.2, marco)
            self.assertIsNone(tema.layout.y_zona_pasos)

    def test_panel_nuevo_respeta_banda_y_piso_propios(self):
        tema = Tema(nombre="T", layout={"banda_panel": 1.2, "y_zona_pasos": -1.8})
        compuesto = componer_tema(tema, _con_pasos(3, recursos={"panel": True}))
        self.assertEqual(compuesto.layout.banda_panel, 1.2)
        self.assertEqual(compuesto.layout.y_zona_pasos, -1.8)

    def test_composicion_repetida_no_acumula(self):
        g = _con_pasos(3, recursos={"panel": True})
        una = componer_tema(Tema(nombre="T", marco="hoja"), g)
        dos = componer_tema(una, g)
        self.assertEqual(una, dos)

    def test_sin_cambios_no_reajusta_layout(self):
        tema = Tema(nombre="T", gramatica={"tabs": True})
        g = _con_pasos(3, recursos={"panel": False, "mapa_color": False, "micro": False})
        self.assertEqual(componer_tema(tema, g).layout, tema.layout)

    def test_panel_apagado_no_baja_subtitulos(self):
        marca = cargar_marca()
        pasos = cargar_tema("consola_pasos", marca)
        g = _con_pasos(3, recursos={"panel": False})
        compuesto = componer_tema(pasos, g)
        self.assertEqual(subtitulos_de(compuesto).posicion_y, compuesto.subtitulos.posicion_y)
        self.assertLess(subtitulos_de(pasos).posicion_y, pasos.subtitulos.posicion_y)

    def test_no_muta_el_guion(self):
        g = _con_pasos(3, recursos={"panel": True})
        antes = deepcopy(g.model_dump())
        componer_tema(Tema(nombre="T"), g)
        recursos_del_guion(g, Tema(nombre="T"))
        self.assertEqual(g.model_dump(), antes)


if __name__ == "__main__":
    unittest.main()
