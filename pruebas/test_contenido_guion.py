"""Contrato del contenido educativo (dato, mito, error, ejercicio) y su guardado fiel."""

import unittest
from copy import deepcopy

import yaml
from pydantic import ValidationError

from pruebas.datos_didacticos import datos_base, datos_concepto
from tpi_videos.guion import Guion, a_yaml
from tpi_videos.panel.editor import a_formulario, desde_formulario


class ContenidoGuionTest(unittest.TestCase):
    def test_conclusion_textual_sin_formula_round_trip(self):
        g = Guion.model_validate(datos_concepto())
        texto = a_yaml(g.model_dump(exclude_none=True), ["Comentario del dueño"])
        leido = Guion.model_validate(yaml.safe_load(texto))
        self.assertEqual(g, leido)
        self.assertIn("# Comentario del dueño", texto)
        self.assertFalse(leido.recursos.panel)
        self.assertIsNone(leido.recursos.micro)
        self.assertNotIn("micro:", texto)
        self.assertEqual(leido.resultado.tex, "")

    def test_ejercicio_heredado_sigue_exigiendo_formula(self):
        datos = datos_base()
        datos["resultado"].pop("tex")
        with self.assertRaises(ValidationError):
            Guion.model_validate(datos)

    def test_formulario_conserva_false_y_conclusion(self):
        g = Guion.model_validate(datos_concepto())
        vuelto = Guion.model_validate(desde_formulario(a_formulario(g)))
        self.assertEqual(g, vuelto)


class LimitesDelContratoTest(unittest.TestCase):
    def _con(self, **cambios):
        datos = datos_concepto()
        for clave, valor in cambios.items():
            datos[clave] = valor
        return datos

    def test_intencion_desconocida(self):
        with self.assertRaises(ValidationError):
            Guion.model_validate(self._con(contenido={"intenciones": ["curiosidad"], "objetivo": "Algo."}))

    def test_intenciones_vacias(self):
        with self.assertRaises(ValidationError):
            Guion.model_validate(self._con(contenido={"intenciones": [], "objetivo": "Algo."}))

    def test_intenciones_repetidas(self):
        with self.assertRaises(ValidationError):
            Guion.model_validate(self._con(contenido={"intenciones": ["dato", "dato"], "objetivo": "Algo."}))

    def test_mas_de_cuatro_intenciones(self):
        lista = ["dato", "mito", "error", "ejercicio", "dato"]
        with self.assertRaises(ValidationError):
            Guion.model_validate(self._con(contenido={"intenciones": lista, "objetivo": "Algo."}))

    def test_combinacion_conserva_orden(self):
        g = Guion.model_validate(
            self._con(
                contenido={"intenciones": ["mito", "dato"], "objetivo": "Algo."},
            )
        )
        self.assertEqual(g.contenido.intenciones, ["mito", "dato"])

    def test_objetivo_en_blanco(self):
        with self.assertRaises(ValidationError):
            Guion.model_validate(self._con(contenido={"intenciones": ["dato"], "objetivo": "   "}))

    def test_objetivo_demasiado_largo(self):
        with self.assertRaises(ValidationError):
            Guion.model_validate(self._con(contenido={"intenciones": ["dato"], "objetivo": "x" * 261}))

    def test_recurso_como_texto_no_vale(self):
        with self.assertRaises(ValidationError):
            Guion.model_validate(self._con(recursos={"panel": "false"}))

    def test_recurso_desconocido_no_vale(self):
        with self.assertRaises(ValidationError):
            Guion.model_validate(self._con(recursos={"brillo": True}))

    def test_ejercicio_combinado_sin_formula(self):
        datos = self._con(contenido={"intenciones": ["mito", "ejercicio"], "objetivo": "Algo."})
        with self.assertRaises(ValidationError):
            Guion.model_validate(datos)

    def test_conclusion_solo_espacios(self):
        datos = datos_concepto()
        datos["resultado"] = {"texto": "   ", "voz": "Algo dicho."}
        with self.assertRaises(ValidationError):
            Guion.model_validate(datos)

    def test_formula_solo_espacios_en_no_ejercicio(self):
        datos = datos_concepto()
        datos["resultado"] = {"tex": "   ", "voz": "Algo dicho."}
        with self.assertRaises(ValidationError):
            Guion.model_validate(datos)

    def test_voz_del_resultado_sigue_obligatoria(self):
        datos = datos_concepto()
        datos["resultado"].pop("voz")
        with self.assertRaises(ValidationError):
            Guion.model_validate(datos)

    def test_concepto_con_formula_y_texto(self):
        datos = datos_concepto()
        datos["resultado"]["tex"] = "V_2 = 8 V_1"
        g = Guion.model_validate(datos)
        self.assertEqual(g.resultado.tex, "V_2 = 8 V_1")
        self.assertEqual(g.resultado.texto, "Longitud y volumen crecen de distinta manera.")

    def test_heredado_sin_campos_nuevos(self):
        g = Guion.model_validate(datos_base())
        self.assertIsNone(g.contenido)
        self.assertIsNone(g.recursos)
        self.assertIsNone(g.resultado.texto)


class EscrituraFielTest(unittest.TestCase):
    def test_guion_heredado_se_escribe_igual_que_antes(self):
        """Sin campos nuevos, a_yaml no agrega líneas: el YAML antiguo sale idéntico."""
        g = Guion.model_validate(datos_base())
        texto = a_yaml(g.model_dump(exclude_none=True))
        self.assertNotIn("contenido:", texto)
        self.assertNotIn("recursos:", texto)
        self.assertNotIn("  texto:", texto.split("resultado:")[1])
        self.assertIn("resultado:\n  tex: 'V = 8'\n  voz: \"El volumen es ocho.\"", texto)

    def test_false_se_escribe_y_null_no(self):
        datos = datos_concepto()
        datos["recursos"] = {"tabs": True, "panel": False, "mapa_color": None}
        texto = a_yaml(Guion.model_validate(datos).model_dump(exclude_none=True))
        self.assertIn("panel: false", texto)
        self.assertIn("tabs: true", texto)
        self.assertNotIn("mapa_color", texto)

    def test_recursos_todos_null_no_escribe_bloque(self):
        datos = datos_concepto()
        datos["recursos"] = {"panel": None}
        texto = a_yaml(Guion.model_validate(datos).model_dump(exclude_none=True))
        self.assertNotIn("recursos:", texto)

    def test_llamado_y_texto_con_comillas_sobreviven(self):
        datos = datos_concepto()
        datos["llamado"] = "¿Tú también lo creías?"
        datos["resultado"]["texto"] = 'Dice "ocho": no es el doble.'
        datos["contenido"]["objetivo"] = "Objetivo: con dos puntos y 'comillas'."
        g = Guion.model_validate(datos)
        leido = Guion.model_validate(yaml.safe_load(a_yaml(g.model_dump(exclude_none=True))))
        self.assertEqual(g, leido)

    def test_formulario_de_guion_heredado_no_agrega_campos(self):
        g = Guion.model_validate(datos_base())
        d = desde_formulario(a_formulario(g))
        self.assertNotIn("contenido", d)
        self.assertNotIn("recursos", d)
        self.assertEqual(Guion.model_validate(d), g)

    def test_formulario_con_recursos_todos_vacios_los_quita(self):
        datos = deepcopy(datos_concepto())
        g = Guion.model_validate(datos)
        f = a_formulario(g)
        f["recursos"] = {"panel": None}
        d = desde_formulario(f)
        self.assertNotIn("recursos", d)


if __name__ == "__main__":
    unittest.main()
