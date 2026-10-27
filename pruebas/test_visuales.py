import unittest
from typing import get_args

from tpi_videos.guion import Visual
from tpi_videos.visuales import CAMPOS, SEGUNDOS_VISUAL, VISUALES, opciones_select


def tipos_del_modelo() -> set[str]:
    return set(get_args(Visual.model_fields["tipo"].annotation))


class TablaTest(unittest.TestCase):
    def test_la_tabla_cubre_todos_los_tipos_del_modelo(self):
        self.assertEqual(set(VISUALES), tipos_del_modelo())
        self.assertGreaterEqual(len(VISUALES), 24)

    def test_todo_campo_mencionado_existe_en_el_modelo(self):
        campos = set(Visual.model_fields)
        for tipo in VISUALES.values():
            for clave in tipo.campos:
                self.assertIn(clave, campos, f"{tipo.clave} usa {clave}, que Visual no tiene")

    def test_todo_campo_del_catalogo_tiene_etiqueta(self):
        for clave, campo in CAMPOS.items():
            self.assertTrue(campo.etiqueta, clave)
            self.assertIn(campo.forma, ("texto", "numero", "numeros", "lista", "opcion", "booleano"), clave)
        for tipo in VISUALES.values():
            for clave in tipo.campos:
                self.assertIn(clave, CAMPOS, f"{tipo.clave} pide {clave}, que no está en CAMPOS")

    def test_ningun_tipo_queda_sin_campos_ni_sin_segundos_estimados(self):
        for clave, tipo in VISUALES.items():
            self.assertTrue(tipo.nombre and tipo.icono and tipo.materia, clave)
            self.assertTrue(tipo.ejemplo, f"{clave} sin ejemplo para la miniatura")
            self.assertIn(clave, SEGUNDOS_VISUAL, f"{clave} no suma duración")

    def test_el_ejemplo_de_cada_tipo_valida_con_Visual(self):
        for clave, tipo in VISUALES.items():
            Visual.model_validate({"tipo": clave, **tipo.ejemplo})

    def test_las_marcas_prometidas_son_las_del_motor(self):
        from tpi_videos import visuales as v

        esperadas = {
            "poligono_regular": v.MARCAS_POLIGONO,
            "proyectil": v.MARCAS_PROYECTIL,
            "circulo_trig": v.MARCAS_CIRCULO,
            "solido": v.MARCAS_SOLIDO,
            "venn": v.MARCAS_VENN,
            "probabilidad": v.MARCAS_PROBABILIDAD,
            "onda": v.MARCAS_ONDA,
            "pendulo": v.MARCAS_PENDULO,
            "resorte": v.MARCAS_RESORTE,
            "polea": v.MARCAS_POLEA,
            "tanque": v.MARCAS_TANQUE,
            "viga": v.MARCAS_VIGA,
            "cercha": v.MARCAS_CERCHA,
            "bloques": v.MARCAS_BLOQUES,
            "engranaje": v.MARCAS_ENGRANAJE,
            "mohr": v.MARCAS_MOHR,
        }
        for clave, marcas in esperadas.items():
            self.assertEqual(VISUALES[clave].marcas, tuple(marcas), clave)

    def test_la_lista_del_select_trae_a_todos_con_su_materia(self):
        opciones = opciones_select()
        self.assertEqual(set(opciones), {"", *tipos_del_modelo()})
        self.assertEqual(opciones[""], "Sin dibujo")
        self.assertTrue(opciones["poligono_regular"].startswith("Matemática · "))
        self.assertTrue(opciones["mohr"].startswith("Ingeniería · "))

    def test_todo_dibujo_que_promete_una_familia_existe_en_la_tabla(self):
        """El spec (§9) lo pide, y en A.1 no se podía probar: la tabla nacía acá.

        Si una tarjeta ofrece un dibujo que el motor no sabe hacer, el video se cae en el paso 3.
        """
        from tpi_videos.formatos import cargar_formatos

        for clave, familia in cargar_formatos().items():
            for dibujo in familia.dibujos:
                self.assertIn(dibujo, VISUALES, f"la familia {clave} promete {dibujo}")


class Tipo3dTest(unittest.TestCase):
    def test_solido_3d_ya_esta_en_la_tabla_y_en_el_modelo(self):
        self.assertIn("solido_3d", VISUALES)
        self.assertIn("solido_3d", tipos_del_modelo())


if __name__ == "__main__":
    unittest.main()
