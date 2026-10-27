import unittest
from pathlib import Path
from tempfile import mkdtemp

import yaml

from tpi_videos.errores import ErrorMotor
from tpi_videos.formatos import cargar_formatos, formato, formato_de_guion, puntuar_idea
from tpi_videos.moldes import MOLDES


class CatalogoTest(unittest.TestCase):
    def test_las_cuatro_familias_del_autor_estan_y_son_coherentes(self):
        familias = cargar_formatos()
        self.assertEqual(set(familias), {"trampas", "paso_a_paso", "datos", "hacks"})
        for f in familias.values():
            self.assertTrue(f.nombre and f.que_es and f.cta)
            self.assertTrue(f.moldes, f"{f.clave} sin molde")
            for molde in f.moldes:
                self.assertIn(molde, MOLDES, f"{f.clave} apunta a un molde que no existe")
            for dibujo in f.dibujos:
                self.assertRegex(dibujo, r"^[a-z_]+$", f"{f.clave} con dibujo mal escrito")
            self.assertRegex(f.color, r"^#[0-9A-Fa-f]{6}$")

    def test_clave_desconocida_dice_cuales_son(self):
        with self.assertRaises(ErrorMotor) as sube:
            formato("nada_de esto")
        self.assertIn("trampas", str(sube.exception))

    def test_formato_de_guion_devuelve_la_familia_de_su_molde(self):
        from tpi_videos.guion import Guion

        ruta = Path("src/tpi_videos/plantillas/vista_previa.yaml")
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        datos["molde"] = "reto"
        guion = Guion.model_validate(datos)
        self.assertEqual(formato_de_guion(guion).clave, "trampas")


class PuntadorTest(unittest.TestCase):
    def test_cada_idea_de_ejemplo_marca_su_familia(self):
        casos = {
            "32 por 11 sin lápiz: un atajo de dos segundos": "hacks",
            "¿Encuentras el error sutil en esta división?": "trampas",
            "POV: tienes que calcular la caída antes del timbre": "paso_a_paso",
            "Una parada de bus con datos de la ciudad": "datos",
        }
        for idea, esperado in casos.items():
            self.assertEqual(puntuar_idea(idea), esperado, idea)

    def test_texto_vacio_o_sin_palabras_no_marca_nada(self):
        for idea in ("", "   ", "hola", "la materia es difícil"):
            self.assertIsNone(puntuar_idea(idea), idea)

    def test_no_llama_a_ningun_proveedor_de_ia(self):
        import inspect

        from tpi_videos import formatos

        fuente = inspect.getsource(formatos)
        self.assertNotIn("ideas.", fuente)
        self.assertNotIn("redactor", fuente)


class ResolucionTest(unittest.TestCase):
    def test_la_copia_del_autor_gana_sobre_la_del_motor(self):
        from unittest import mock

        from tpi_videos import formatos as mod

        propio = yaml.safe_load(mod.PLANTILLA.read_text(encoding="utf-8"))
        propio["hacks"]["nombre"] = "Trucos míos"
        texto = yaml.safe_dump(propio, allow_unicode=True)
        with mock.patch.object(mod, "_ruta_usuario", lambda: _archivo_con(texto)):
            self.assertEqual(mod.cargar_formatos()["hacks"].nombre, "Trucos míos")


def _archivo_con(texto: str) -> Path:
    ruta = Path(mkdtemp()) / "formatos.yaml"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


if __name__ == "__main__":
    unittest.main()
