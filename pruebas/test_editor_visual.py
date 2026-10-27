"""El formulario del editor va de ida y vuelta con el guion, para los 24 dibujos del catálogo."""

import copy
import unittest

from tpi_videos.guion import Visual
from tpi_videos.panel.editor import PASO_VACIO, _visual_al_formulario, _visual_al_guardar
from tpi_videos.visuales import VISUALES


class IdaYVueltaTest(unittest.TestCase):
    def test_cada_tipo_sobrevive_a_guardar_y_recargar_sin_perder_datos(self):
        for clave, tipo in VISUALES.items():
            crudo = {"tipo": clave, **copy.deepcopy(tipo.ejemplo)}
            visual = Visual.model_validate(crudo).model_dump(exclude_none=True)
            guardado = _visual_al_guardar(_visual_al_formulario(visual))
            self.assertEqual(guardado["tipo"], clave)
            for campo in tipo.campos:
                if campo in crudo:
                    self.assertIn(campo, guardado, f"{clave} perdió {campo}")
            self.assertEqual(Visual.model_validate(guardado), Visual.model_validate(crudo), clave)

    def test_un_campo_lleno_de_otro_tipo_no_se_guarda(self):
        guardado = _visual_al_guardar(
            _visual_al_formulario(
                {"tipo": "torta", "categorias": ["A 1", "B 2"], "funcion": "x", "angulo": 30}
            )
        )
        self.assertNotIn("funcion", guardado)
        self.assertNotIn("angulo", guardado)

    def test_sin_tipo_no_hay_visual(self):
        self.assertIsNone(_visual_al_guardar(copy.deepcopy(PASO_VACIO["visual"])))

    def test_un_numero_se_ve_con_coma_chilena_y_se_guarda_como_numero(self):
        formulario = _visual_al_formulario({"tipo": "recta", "extremo_a": 2.5, "extremo_b": 7.0})
        self.assertEqual(formulario["extremo_a"], "2,5")
        guardado = _visual_al_guardar(formulario)
        self.assertEqual(guardado["extremo_a"], 2.5)

    def test_la_lista_del_editor_es_el_catalogo_completo(self):
        from tpi_videos.panel.editor import tipos_visual_del_editor

        self.assertEqual(set(tipos_visual_del_editor()), {"", *VISUALES})


class FormulaEnVivoTest(unittest.TestCase):
    def test_gana_la_ultima_peticion(self):
        from tpi_videos.panel.editor import _ultima_version

        versiones = _ultima_version()
        vieja, media, nueva = versiones.nueva(), versiones.nueva(), versiones.nueva()
        self.assertFalse(versiones.al_dia(vieja))
        self.assertFalse(versiones.al_dia(media))
        self.assertTrue(versiones.al_dia(nueva))

    def test_el_campo_de_latex_llega_frenado_mientras_se_escribe(self):
        import inspect

        from tpi_videos.panel.editor import EditorGuion

        fuente = inspect.getsource(EditorGuion._formula)
        self.assertIn("input-debounce=400", fuente)
        self.assertIn("on_value_change", fuente)
        self.assertNotIn('"blur"', fuente)  # el blur era la única puerta: sin sacar el foco, sin dibujo
        # El LaTeX se lee del evento: cuando llega el evento el `bind_value` todavía no escribió en el
        # diccionario, y la vista previa quedaba una letra detrás de lo tecleado.
        self.assertNotIn("formulas.dibujar(d.get(clave)", fuente)


class MoldeEnLaHojaTest(unittest.TestCase):
    """La familia decide un molde: en la hoja tiene que verse su valor y poder cambiarse."""

    def test_el_formulario_arranca_con_el_campo_del_molde(self):
        from tpi_videos.panel.editor import a_formulario

        self.assertEqual(a_formulario(None).get("molde"), "")

    def test_el_molde_elegido_viaja_de_la_hoja_al_yaml(self):
        from tpi_videos.panel.editor import a_formulario, desde_formulario

        datos = {**a_formulario(None), "titulo": "32 por 11 sin lápiz", "molde": "mito_realidad"}
        self.assertEqual(desde_formulario(datos)["molde"], "mito_realidad")


if __name__ == "__main__":
    unittest.main()
