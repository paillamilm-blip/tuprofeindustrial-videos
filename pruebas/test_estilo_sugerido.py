"""El estilo de cada video: una sola regla en el motor (temas.py) y un solo lugar para cambiarlo (QC)."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tpi_videos.entorno import PLANTILLAS_DIR
from tpi_videos.errores import ErrorMotor
from tpi_videos.guion import Guion, cargar_guion, fijar_tema
from tpi_videos.temas import (
    TEMA_DE_ERROR,
    TEMA_POR_CATEGORIA,
    TEMA_POR_DIBUJO,
    TEMA_POR_MOLDE,
    cuando_se_sugiere,
    estilo_del_guion,
    resolver_tema,
    sugerir_tema,
    sugerir_tema_de_guion,
)
from tpi_videos.visuales import VISUALES

RAIZ = Path(__file__).resolve().parents[1]
MARCA = SimpleNamespace(tema="hoja_de_desarrollo")


def _visual(tipo: str) -> dict:
    return {"tipo": tipo, **VISUALES[tipo].ejemplo}


def _guion(materia="matematica", molde=None, tema=None, dibujo=None, error=False) -> Guion:
    paso = {"voz": "Una voz.", "tex": "x = 1"}
    if dibujo:
        paso["visual"] = _visual(dibujo)
    if error:
        paso["error"] = True
    datos = {
        "titulo": "T",
        "materia": materia,
        "gancho": {"texto": "¿Sí?"},
        "enunciado": {"texto": "E"},
        "pasos": [paso],
        "resultado": {"tex": "x = 1", "voz": "Listo."},
    }
    if molde:
        datos["molde"] = molde
    if tema:
        datos["tema"] = tema
    return Guion.model_validate(datos)


class ReglaTest(unittest.TestCase):
    def test_todo_lo_que_se_sugiere_es_un_estilo_que_ya_existe(self):
        sugeridos = {
            *TEMA_POR_MOLDE.values(),
            *TEMA_POR_CATEGORIA.values(),
            *(t for _d, t, _r in TEMA_POR_DIBUJO),
            TEMA_DE_ERROR,
        }
        for clave in sugeridos:
            self.assertTrue((PLANTILLAS_DIR / "temas" / f"{clave}.yaml").is_file(), clave)

    def test_el_orden_molde_dibujo_error_materia_marca(self):
        todo = {"molde": "reto", "categoria": "fisica", "dibujos": {"circuito"}, "con_error": True}
        self.assertEqual(sugerir_tema(**todo).origen, "molde")
        self.assertEqual(sugerir_tema(**{**todo, "molde": None}).origen, "dibujo")
        self.assertEqual(sugerir_tema(**{**todo, "molde": None, "dibujos": set()}).origen, "error")
        sin_nada = {"categoria": "fisica"}
        self.assertEqual(sugerir_tema(**sin_nada).clave, "neon_cian")
        self.assertEqual(sugerir_tema(de_siempre="kraft_claro").clave, "kraft_claro")
        self.assertEqual(sugerir_tema().origen, "marca")

    def test_cada_sugerencia_dice_por_que(self):
        for s in (
            sugerir_tema(molde="pov"),
            sugerir_tema(dibujos={"tuberia_3d"}),
            sugerir_tema(con_error=True),
            sugerir_tema(categoria="ingenieria"),
        ):
            self.assertTrue(s.razon.endswith("."), s)


class GuionTest(unittest.TestCase):
    def test_lee_los_dibujos_los_errores_y_la_materia_del_guion(self):
        self.assertEqual(
            sugerir_tema_de_guion(_guion("ingenieria", dibujo="tuberia_3d")).clave, "plano_noche"
        )
        self.assertEqual(sugerir_tema_de_guion(_guion("fisica", dibujo="circuito")).clave, "plano_azul")
        self.assertEqual(sugerir_tema_de_guion(_guion("matematica", error=True)).clave, TEMA_DE_ERROR)
        self.assertEqual(sugerir_tema_de_guion(_guion("fisica")).clave, "neon_cian")
        self.assertEqual(sugerir_tema_de_guion(_guion("fisica", molde="reto", error=True)).clave, "neon_reja")

    def test_lo_elegido_en_qc_le_gana_a_la_sugerencia(self):
        g = _guion("fisica", tema="kraft_claro")
        self.assertEqual(estilo_del_guion(g).origen, "guion")
        self.assertEqual(sugerir_tema_de_guion(g).clave, "neon_cian")  # la sugerencia no mira el «tema:»
        self.assertEqual(resolver_tema(None, g, MARCA), "kraft_claro")
        self.assertEqual(resolver_tema("tiza_verde", g, MARCA), "tiza_verde")  # --tema en la Terminal

    def test_el_catalogo_dice_cuando_se_sugiere_cada_estilo(self):
        self.assertIn("Física", cuando_se_sugiere("neon_cian"))
        self.assertIn("piezas industriales", cuando_se_sugiere("plano_noche"))
        self.assertIn("circuitos", cuando_se_sugiere("plano_azul"))
        self.assertEqual(cuando_se_sugiere("comic_azul"), [])


class FijarTemaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / "g.yaml"
        self.ruta.write_text(
            "# escrito por la IA\n"
            "# - un supuesto\n\n"
            'titulo: "T"\nmateria: fisica\ncategoria: fisica  # comentario\n\n'
            'gancho:\n  texto: "¿Sí?"\n\nenunciado:\n  texto: "E"\n\n'
            "pasos:\n  - voz: \"Una voz.\"\n    tex: 'x = 1'\n\n"
            "resultado:\n  tex: 'x = 1'\n  voz: \"Listo.\"\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_escribe_reemplaza_y_borra_solo_esa_linea(self):
        antes = self.ruta.read_text(encoding="utf-8")
        self.assertEqual(fijar_tema(self.ruta, "kraft_claro").tema, "kraft_claro")
        texto = self.ruta.read_text(encoding="utf-8")
        self.assertIn("categoria: fisica  # comentario\ntema: kraft_claro\n", texto)
        self.assertIn("# - un supuesto", texto)
        fijar_tema(self.ruta, "tiza_verde")
        self.assertEqual(self.ruta.read_text(encoding="utf-8").count("tema:"), 1)
        self.assertIsNone(fijar_tema(self.ruta, None).tema)
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), antes)  # vuelve exacto a como estaba

    def test_un_nombre_raro_no_se_escribe(self):
        antes = self.ruta.read_text(encoding="utf-8")
        with self.assertRaises(ErrorMotor):
            fijar_tema(self.ruta, "malo: {x}")
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), antes)

    def test_si_el_guion_queda_invalido_el_archivo_no_cambia(self):
        self.ruta.write_text("titulo: T\nmateria: quimica\n", encoding="utf-8")
        with self.assertRaises(ErrorMotor):
            fijar_tema(self.ruta, "kraft_claro")
        self.assertEqual(self.ruta.read_text(encoding="utf-8"), "titulo: T\nmateria: quimica\n")


class CambiarEnQcTest(unittest.TestCase):
    """El único lugar del panel donde se elige: elegir el sugerido vuelve a lo automático."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.viejo = os.environ.get("TPI_RAIZ")
        os.environ["TPI_RAIZ"] = self.tmp.name
        raiz = Path(self.tmp.name).resolve()
        (raiz / "salida").mkdir()
        (raiz / "guiones").mkdir()
        self.guion = raiz / "guiones" / "mohr.yaml"
        shutil.copy(RAIZ / "guiones" / "el_circulo_de_mohr.yaml", self.guion)

    def tearDown(self) -> None:
        if self.viejo is None:
            os.environ.pop("TPI_RAIZ", None)
        else:
            os.environ["TPI_RAIZ"] = self.viejo
        self.tmp.cleanup()

    def test_elegir_otro_y_volver_al_sugerido(self):
        from tpi_videos.panel import qc

        f = qc.ficha(self.guion)
        self.assertEqual(f.sugerido.clave, "plano_noche")  # ingeniería con el círculo de Mohr
        self.assertEqual(f.estilo.origen, "dibujo")
        self.assertEqual(qc.cambiar_estilo(self.guion, "kraft_claro").origen, "guion")
        self.assertEqual(cargar_guion(self.guion).tema, "kraft_claro")
        self.assertEqual(qc.cambiar_estilo(self.guion, "plano_noche").origen, "dibujo")
        self.assertIsNone(cargar_guion(self.guion).tema)  # el sugerido no se escribe: queda automático

    def test_cambiar_el_estilo_no_deshace_la_aprobacion(self):
        from tpi_videos.panel import qc

        qc.aprobar(self.guion, "lote-1")
        qc.cambiar_estilo(self.guion, "kraft_claro")
        self.assertEqual(qc.estado(self.guion), qc.APROBADO)  # no vuelve a la cola dos veces
        self.assertEqual(qc.decision(self.guion)["cola_id"], "lote-1")


if __name__ == "__main__":
    unittest.main()
