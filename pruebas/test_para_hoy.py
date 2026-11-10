"""«Para hoy»: una opción por materia, las tres del mismo nivel, y cada una dice por qué."""

import os
import tempfile
import time
import unittest
from pathlib import Path

GUION = """titulo: "{titulo}"
materia: {materia}
nivel: "{nivel}"
{extra}
gancho:
  texto: "¿Sí?"

enunciado:
  texto: "E"

pasos:
  - voz: "Una voz."
    tex: 'x = 1'

resultado:
  tex: 'x = 1'
  voz: "Listo."
"""

METADATOS = """
metadatos:
  titulo: "Un título"
  descripcion: "Una descripción."
  hashtags: ["#tuprofeindustrial", "#matematica", "#fisica"]
"""


class ParaHoyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.viejo = os.environ.get("TPI_RAIZ")
        os.environ["TPI_RAIZ"] = self.tmp.name
        self.raiz = Path(self.tmp.name).resolve()
        (self.raiz / "salida").mkdir()
        (self.raiz / "guiones").mkdir()

    def tearDown(self) -> None:
        if self.viejo is None:
            os.environ.pop("TPI_RAIZ", None)
        else:
            os.environ["TPI_RAIZ"] = self.viejo
        self.tmp.cleanup()

    def _guion(self, nombre, materia, nivel, extra="", dias=0, metadatos=False):
        ruta = self.raiz / "guiones" / f"{nombre}.yaml"
        texto = GUION.format(titulo=nombre, materia=materia, nivel=nivel, extra=extra)
        ruta.write_text(texto + (METADATOS if metadatos else ""), encoding="utf-8")
        hace = time.time() - dias * 86_400
        os.utime(ruta, (hace, hace))
        return ruta

    def test_el_nivel_se_lee_aunque_venga_escrito_distinto(self):
        from tpi_videos.panel.para_hoy import nivel_de

        self.assertEqual(nivel_de("3° medio"), "3° medio")
        self.assertEqual(nivel_de("3 medio"), "3° medio")
        self.assertEqual(nivel_de("4° medio · PAES"), "4° medio")
        self.assertEqual(nivel_de("2º Medio"), "2° medio")
        self.assertIsNone(nivel_de("enseñanza media (Chile)"))
        self.assertIsNone(nivel_de(None))

    def test_una_por_materia_y_las_tres_del_mismo_nivel(self):
        from tpi_videos.panel.para_hoy import CATEGORIAS, proponer

        self._guion("m1", "matematica", "1° medio")
        self._guion("m3", "matematica", "3° medio")
        self._guion("f3", "fisica", "3° medio")
        self._guion("i3", "ingenieria", "3° medio")
        p = proponer()
        self.assertEqual(p.nivel, "3° medio")  # el único nivel con las tres materias
        self.assertEqual(p.completos, ["3° medio"])
        for categoria in CATEGORIAS:
            self.assertEqual({o.nivel for o in p.opciones[categoria]}, {"3° medio"})
        self.assertEqual([o.titulo for o in p.opciones["matematicas"]], ["m3"])
        self.assertEqual(p.faltan("1° medio"), ["fisica", "ingenieria"])

    def test_el_nivel_que_toca_ella_manda_y_dice_lo_que_falta(self):
        from tpi_videos.panel.para_hoy import proponer

        self._guion("m1", "matematica", "1° medio")
        self._guion("m3", "matematica", "3° medio")
        self._guion("f3", "fisica", "3° medio")
        self._guion("i3", "ingenieria", "3° medio")
        p = proponer("1° medio")
        self.assertEqual(p.nivel, "1° medio")
        self.assertEqual(p.faltan(), ["fisica", "ingenieria"])
        self.assertEqual(p.opciones["fisica"], [])

    def test_el_nivel_de_ajustes_gana_si_esta_completo(self):
        from tpi_videos.panel.para_hoy import proponer

        for n in ("2° medio", "3° medio"):
            for materia in ("matematica", "fisica", "ingenieria"):
                self._guion(f"{materia}{n[0]}", materia, n)
        self._guion("extra3", "fisica", "3° medio")
        self.assertEqual(proponer().nivel, "3° medio")  # más guiones
        self.assertEqual(proponer(preferido="2° medio").nivel, "2° medio")

    def test_primero_el_listo_y_el_que_mas_espera(self):
        from tpi_videos.panel.para_hoy import proponer

        self._guion("nuevo", "fisica", "3° medio", dias=0)
        self._guion("viejo", "fisica", "3° medio", dias=6)
        self._guion("con_redes", "fisica", "3° medio", dias=1, metadatos=True)
        orden = [o.titulo for o in proponer("3° medio").opciones["fisica"]]
        self.assertEqual(orden, ["con_redes", "viejo", "nuevo"])
        razones = proponer("3° medio").opciones["fisica"][1].razones
        self.assertIn("Lleva 6 días esperando", razones)

    def test_los_ya_aprobados_no_se_ofrecen_y_se_recuerda_el_de_hoy(self):
        from tpi_videos.panel import qc
        from tpi_videos.panel.para_hoy import proponer

        elegido = self._guion("elegido", "fisica", "3° medio")
        self._guion("otro", "fisica", "3° medio")
        qc.aprobar(elegido, "lote-1")
        p = proponer("3° medio")
        self.assertEqual([o.titulo for o in p.opciones["fisica"]], ["otro"])
        self.assertEqual(p.hoy, ["elegido"])

    def test_un_guion_que_no_valida_no_se_ofrece(self):
        from tpi_videos.panel.para_hoy import proponer

        (self.raiz / "guiones" / "roto.yaml").write_text("titulo: x\nmateria: quimica\nnivel: 3° medio\n")
        self._guion("bien", "fisica", "3° medio")
        p = proponer()
        self.assertEqual([o.titulo for o in p.opciones["fisica"]], ["bien"])


if __name__ == "__main__":
    unittest.main()
