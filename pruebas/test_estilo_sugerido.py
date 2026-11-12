"""El estilo de cada video: una sola regla en el motor (temas.py) y un solo lugar para cambiarlo (QC)."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tpi_videos.config import cargar_marca
from tpi_videos.entorno import PLANTILLAS_DIR
from tpi_videos.errores import ErrorMotor
from tpi_videos.guion import Guion, cargar_guion, fijar_tema
from tpi_videos.moldes import MOLDES
from tpi_videos.temas import (
    ARCHIVO_DIR,
    FAMILIA,
    TEMA_DE_ERROR,
    TEMA_DE_PASOS,
    TEMA_POR_MOLDE,
    cargar_tema,
    cuando_se_sugiere,
    estilo_del_guion,
    listar_temas,
    resolver_tema,
    sugerir_tema,
    sugerir_tema_de_guion,
)
from tpi_videos.visuales import VISUALES

RAIZ = Path(__file__).resolve().parents[1]
MARCA = SimpleNamespace(tema="consola_pasos")


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


class FamiliaTest(unittest.TestCase):
    """Todo video es de la familia Consola neón: la forma del contenido elige la variante."""

    def test_el_catalogo_es_solo_la_familia_y_en_su_orden(self):
        self.assertEqual(tuple(clave for clave, _t, propio in listar_temas() if not propio), FAMILIA)

    def test_cada_variante_comparte_la_base_y_dice_que_es(self):
        marca = cargar_marca()
        for clave in FAMILIA:
            t = cargar_tema(clave, marca)
            self.assertEqual(t.marco, "pizarra", clave)
            self.assertFalse(t.resplandor, clave)  # versión sobria: sin brillo neón
            self.assertEqual(t.animacion.titulos, "plumon", clave)
            self.assertEqual(t.tipografia.titulos.familia, "Montserrat", clave)
            self.assertEqual(t.subtitulos.fuente, "Montserrat Black", clave)
            self.assertEqual(t.fondo.tipo, "degradado", clave)  # grafito liso, sin rejas ni viñetas
            self.assertTrue(t.rotulo, clave)
            self.assertTrue(t.gramatica.mapa_color, clave)

    def test_cada_variante_tiene_su_propio_color(self):
        marca = cargar_marca()
        acentos = {cargar_tema(clave, marca).colores.acento for clave in FAMILIA}
        self.assertEqual(len(acentos), len(FAMILIA))

    def test_el_panel_va_donde_hay_pasos_que_seguir(self):
        marca = cargar_marca()
        con_panel = {clave for clave in FAMILIA if cargar_tema(clave, marca).gramatica.panel}
        self.assertEqual(con_panel, {"consola_pasos", "consola_error", "consola_reto"})
        for clave in con_panel:
            self.assertGreater(cargar_tema(clave, marca).layout.banda_panel, 0, clave)

    def test_los_estilos_archivados_siguen_funcionando_por_su_nombre(self):
        marca = cargar_marca()
        archivados = sorted(r.stem for r in ARCHIVO_DIR.glob("*.yaml"))
        self.assertEqual(len(archivados), 20)
        for clave in archivados:
            self.assertTrue(cargar_tema(clave, marca).nombre, clave)
        self.assertNotIn("hoja_de_desarrollo", {c for c, _t, _p in listar_temas()})


class ReglaTest(unittest.TestCase):
    def test_todo_lo_que_se_sugiere_es_de_la_familia(self):
        sugeridos = {*TEMA_POR_MOLDE.values(), TEMA_DE_ERROR, TEMA_DE_PASOS}
        self.assertEqual(sugeridos, set(FAMILIA))
        for clave in sugeridos:
            self.assertTrue((PLANTILLAS_DIR / "temas" / f"{clave}.yaml").is_file(), clave)

    def test_cada_molde_tiene_su_variante(self):
        self.assertEqual(set(TEMA_POR_MOLDE), set(MOLDES))
        self.assertEqual(sugerir_tema(molde="pov").clave, "consola_pasos")
        self.assertEqual(sugerir_tema(molde="tres_errores").clave, "consola_error")
        self.assertEqual(sugerir_tema(molde="mito_realidad").clave, "consola_mito")
        self.assertEqual(sugerir_tema(molde="nadie_te_enseno").clave, "consola_dato")
        self.assertEqual(sugerir_tema(molde="reto").clave, "consola_reto")

    def test_el_orden_molde_error_paso_a_paso(self):
        todo = {"molde": "reto", "categoria": "fisica", "dibujos": {"circuito"}, "con_error": True}
        self.assertEqual(sugerir_tema(**todo).origen, "molde")
        self.assertEqual(sugerir_tema(**{**todo, "molde": None}).clave, TEMA_DE_ERROR)
        self.assertEqual(sugerir_tema(**{**todo, "molde": None, "con_error": False}).clave, TEMA_DE_PASOS)
        self.assertEqual(sugerir_tema().origen, "forma")

    def test_la_materia_los_dibujos_y_la_marca_ya_no_cambian_el_estilo(self):
        for extra in ({"categoria": "fisica"}, {"dibujos": {"tuberia_3d"}}, {"de_siempre": "kraft_claro"}):
            self.assertEqual(sugerir_tema(**extra).clave, TEMA_DE_PASOS, extra)

    def test_cada_sugerencia_dice_por_que(self):
        for s in (
            *(sugerir_tema(molde=m) for m in MOLDES),
            sugerir_tema(con_error=True),
            sugerir_tema(),
        ):
            self.assertTrue(s.razon.endswith("."), s)


class GuionTest(unittest.TestCase):
    def test_lee_el_molde_y_los_errores_del_guion(self):
        self.assertEqual(sugerir_tema_de_guion(_guion("ingenieria", dibujo="tuberia_3d")).clave, TEMA_DE_PASOS)
        self.assertEqual(sugerir_tema_de_guion(_guion("fisica", dibujo="circuito")).clave, TEMA_DE_PASOS)
        self.assertEqual(sugerir_tema_de_guion(_guion("matematica", error=True)).clave, TEMA_DE_ERROR)
        self.assertEqual(sugerir_tema_de_guion(_guion("fisica", molde="reto", error=True)).clave, "consola_reto")

    def test_lo_elegido_en_qc_le_gana_a_la_sugerencia(self):
        g = _guion("fisica", tema="kraft_claro")
        self.assertEqual(estilo_del_guion(g).origen, "guion")
        self.assertEqual(sugerir_tema_de_guion(g).clave, TEMA_DE_PASOS)  # la sugerencia no mira el «tema:»
        self.assertEqual(resolver_tema(None, g, MARCA), "kraft_claro")  # un archivado, pedido por nombre
        self.assertEqual(resolver_tema("tiza_verde", g, MARCA), "tiza_verde")  # --tema en la Terminal

    def test_sin_guion_queda_el_de_la_marca(self):
        self.assertEqual(resolver_tema(None, None, MARCA), "consola_pasos")
        self.assertEqual(resolver_tema(None, None, SimpleNamespace(tema="")), "consola_pasos")

    def test_el_catalogo_dice_cuando_se_sugiere_cada_estilo(self):
        self.assertIn("videos que corrigen un error", cuando_se_sugiere("consola_error"))
        self.assertIn("ejercicios sin molde", cuando_se_sugiere("consola_pasos"))
        for clave in FAMILIA:
            self.assertTrue(cuando_se_sugiere(clave), clave)
        self.assertEqual(cuando_se_sugiere("comic_azul"), [])


class GuionesDelRepoTest(unittest.TestCase):
    def test_todos_cargan_y_su_estilo_existe(self):
        from tpi_videos.temas import listar_temas

        existentes = {clave for clave, _t, _p in listar_temas()}
        for ruta in sorted((RAIZ / "guiones").glob("*.yaml")):
            estilo = estilo_del_guion(cargar_guion(ruta), MARCA)
            self.assertIn(estilo.clave, existentes, ruta.name)


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
        self.assertEqual(f.sugerido.clave, "consola_pasos")  # ejercicio sin molde: paso a paso
        self.assertEqual(f.estilo.origen, "forma")
        self.assertEqual(qc.cambiar_estilo(self.guion, "kraft_claro").origen, "guion")
        self.assertEqual(cargar_guion(self.guion).tema, "kraft_claro")
        self.assertEqual(qc.cambiar_estilo(self.guion, "consola_pasos").origen, "forma")
        self.assertIsNone(cargar_guion(self.guion).tema)  # el sugerido no se escribe: queda automático

    def test_todos_al_sugerido_de_una_vez(self):
        from tpi_videos.panel import qc

        otro = self.guion.with_name("otro.yaml")
        shutil.copy(self.guion, otro)
        fijar_tema(self.guion, "kraft_claro")
        fijar_tema(otro, "tiza_verde")
        qc.aprobar(otro, "lote-9")
        self.assertEqual(len(qc.con_estilo_propio()), 2)
        self.assertEqual(sorted(p.name for p in qc.todos_al_sugerido()), ["mohr.yaml", "otro.yaml"])
        self.assertEqual(qc.con_estilo_propio(), [])
        self.assertIsNone(cargar_guion(otro).tema)
        self.assertEqual(qc.estado(otro), qc.APROBADO)  # la aprobación sigue en pie
        self.assertEqual(qc.todos_al_sugerido(), [])  # una segunda vez no hace nada

    def test_cambiar_el_estilo_no_deshace_la_aprobacion(self):
        from tpi_videos.panel import qc

        qc.aprobar(self.guion, "lote-1")
        qc.cambiar_estilo(self.guion, "kraft_claro")
        self.assertEqual(qc.estado(self.guion), qc.APROBADO)  # no vuelve a la cola dos veces
        self.assertEqual(qc.decision(self.guion)["cola_id"], "lote-1")


if __name__ == "__main__":
    unittest.main()
