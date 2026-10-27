import unittest

from tpi_videos.guion import Visual, a_yaml
from tpi_videos.visuales import CAMPOS, SEGUNDOS_VISUAL, VISUALES


def _solido(**extra):
    base = {"tipo": "solido_3d", "figura": "cilindro", "radio": "3 cm", "altura": "5 cm"}
    return Visual.model_validate(base | extra)


class ModeloTest(unittest.TestCase):
    def test_el_tipo_esta_en_la_tabla_con_su_fila_completa(self):
        self.assertIn("solido_3d", VISUALES)
        tipo = VISUALES["solido_3d"]
        self.assertEqual(tipo.materia, "ingenieria")
        self.assertEqual(tipo.marcas, VISUALES["solido"].marcas)  # mismo anotar que el sólido plano
        self.assertIn("solido_3d", SEGUNDOS_VISUAL)
        for clave in ("vista", "corte"):
            self.assertIn(clave, CAMPOS)
            self.assertEqual(CAMPOS[clave].forma, "opcion")

    def test_reusa_la_matematica_del_solido_plano(self):
        plano = Visual.model_validate(
            {"tipo": "solido", "figura": "cilindro", "radio": "3 cm", "altura": "5 cm"}
        )
        self.assertEqual(_solido().solido(), plano.solido())

    def test_la_vista_por_defecto_es_la_axonometrica(self):
        self.assertEqual(_solido().vista, "axonometrica")
        with self.assertRaises(ValueError):
            _solido(vista="de_arriba")

    def test_el_corte_a_la_mitad_solo_se_pide_en_el_cubo(self):
        _solido(figura="cubo", lado="4 cm", corte="mitad")  # no debe lanzar
        for figura in ("cilindro", "cono", "esfera"):
            with self.assertRaises(Exception) as sube:
                _solido(figura=figura, corte="mitad")
            self.assertIn("cubo", str(sube.exception).lower(), figura)

    def test_escribir_y_volver_a_leer_conserva_vista_y_corte(self):
        import yaml

        from tpi_videos.guion import Guion

        visual = _solido(figura="cubo", lado="4 cm", corte="mitad", anotar=["volumen"])
        datos = {
            "titulo": "El cubo partido",
            "materia": "ingenieria",
            "gancho": {"texto": "g"},
            "enunciado": {"texto": "e"},
            "resultado": {"tex": "V = 32", "voz": "r"},
            "pasos": [{"tex": "V = 32", "voz": "p", "visual": visual.model_dump(exclude_none=True)}],
        }
        bloque = a_yaml(datos)
        self.assertIn("vista: axonometrica", bloque)
        self.assertIn("corte: mitad", bloque)
        leido = Guion.model_validate(yaml.safe_load(bloque))
        self.assertEqual(leido.pasos[0].visual.vista, "axonometrica")
        self.assertEqual(leido.pasos[0].visual.corte, "mitad")


class ElMotorAvisaTest(unittest.TestCase):
    def test_un_tipo_que_el_motor_no_sabe_dibujar_no_dibuja_un_circuito(self):
        """Hoy dibujar_visual() cae al final y dibuja un circuito para cualquier tipo desconocido.
        Con un catálogo que crece, eso es un dibujo equivocado en el video: tiene que gritar."""
        from tpi_videos.config import cargar_marca
        from tpi_videos.dibujos import dibujar_visual
        from tpi_videos.errores import ErrorMotor
        from tpi_videos.temas import cargar_tema

        col = cargar_tema("pizarra_nocturna", cargar_marca()).colores
        falso = Visual.model_validate({"tipo": "solido", "figura": "cubo", "lado": "4 cm"})
        object.__setattr__(falso, "tipo", "dibujo_inventado")
        with self.assertRaises(ErrorMotor):
            dibujar_visual(falso, col, 7.6, 3.3)
