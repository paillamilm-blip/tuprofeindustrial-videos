import unittest
from pathlib import Path
from tempfile import mkdtemp

import yaml

from tpi_videos.errores import ErrorMotor
from tpi_videos.moldes import MOLDES
from tpi_videos.rodaje import RECETA_LIBRE, cargar_recetas, rodaje_de_guion, rodaje_para

import tpi_videos.rodaje as mod


class CatalogoTest(unittest.TestCase):
    def test_hay_receta_para_cada_molde_y_para_los_guiones_sin_molde(self):
        recetas = cargar_recetas()
        self.assertEqual(set(recetas), set(MOLDES) | {RECETA_LIBRE})

    def test_toda_receta_usa_valores_conocidos(self):
        for clave, r in cargar_recetas().items():
            self.assertIn(r.pasos, mod.PASOS, clave)
            self.assertIn(r.error, mod.ERROR, clave)
            self.assertIn(r.contador, mod.CONTADOR, clave)
            self.assertIn(r.primer_plano, mod.PRIMER_PLANO, clave)
            self.assertIn(r.gancho, mod.GANCHO, clave)
            self.assertIn(r.deriva, mod.DERIVA, clave)
            self.assertIn(r.partida, mod.PARTIDA, clave)
            self.assertIn(r.tapar_resultado, mod.TAPAR, clave)

    def test_los_tres_errores_muestran_contador_y_los_demas_no(self):
        recetas = cargar_recetas()
        self.assertEqual(recetas["tres_errores"].contador, "errores")
        # Un mito tiene un solo error: «✗ 1 de 1» es ruido, no información.
        self.assertEqual(recetas["mito_realidad"].contador, "ninguno")

    def test_los_moldes_que_abren_con_un_dato_llenan_el_cuadro_con_la_pregunta(self):
        """Ver la marca y el título antes de la pregunta es lo que hacía iguales a todos los videos."""
        recetas = cargar_recetas()
        for clave in ("pov", "nadie_te_enseno"):
            self.assertEqual(recetas[clave].gancho, "lleno", clave)
        for clave in ("libre", "mito_realidad", "tres_errores", "reto"):
            self.assertEqual(recetas[clave].gancho, "tarjeta", clave)

    def test_solo_el_pov_se_roda_con_camara_en_mano(self):
        """El resto se sostiene: un video que se mueve todo el tiempo marea, no engancha."""
        recetas = cargar_recetas()
        self.assertEqual(recetas["pov"].deriva, "en_mano")
        self.assertEqual({r.deriva for k, r in recetas.items() if k != "pov"}, {"fija"})

    def test_solo_el_mito_se_rueda_partido_en_dos_mitades(self):
        """El resto necesita la cadena de pasos; el mito vive de tener el error a la vista."""
        recetas = cargar_recetas()
        self.assertEqual(recetas["mito_realidad"].partida, "mitades")
        self.assertEqual({r.partida for k, r in recetas.items() if k != "mito_realidad"}, {"seguida"})

    def test_los_moldes_que_prometen_el_numero_lo_tapan_hasta_que_la_lo_dice(self):
        """Donde el gancho es un reto o un dato, la respuesta anticipada es lo que hace irse al video."""
        recetas = cargar_recetas()
        self.assertEqual(
            {k for k, r in recetas.items() if r.tapar_resultado == "tapada"},
            {"mito_realidad", "reto", "nadie_te_enseno"},
        )

    def test_clave_desconocida_dice_cuales_son(self):
        with self.assertRaises(ErrorMotor) as sube:
            rodaje_para("nada de esto")
        self.assertIn("pov", str(sube.exception))


class GuionTest(unittest.TestCase):
    def _guion(self, molde):
        from tpi_videos.guion import Guion

        datos = yaml.safe_load(Path("src/tpi_videos/plantillas/vista_previa.yaml").read_text(encoding="utf-8"))
        datos["molde"] = molde
        return Guion.model_validate(datos)

    def test_sin_molde_se_roda_con_la_receta_libre(self):
        self.assertEqual(rodaje_de_guion(self._guion(None)).pasos, "ancla")

    def test_el_molde_del_guion_elige_su_receta(self):
        self.assertEqual(rodaje_de_guion(self._guion("pov")).contador, "ninguno")
        self.assertEqual(rodaje_de_guion(self._guion("tres_errores")).contador, "errores")

    def test_el_molde_del_guion_tambien_elige_como_se_abre_y_como_respira(self):
        self.assertEqual(rodaje_de_guion(self._guion("pov")).gancho, "lleno")
        self.assertEqual(rodaje_de_guion(self._guion("pov")).deriva, "en_mano")
        self.assertEqual(rodaje_de_guion(self._guion("tres_errores")).deriva, "fija")
        self.assertEqual(rodaje_de_guion(self._guion(None)).gancho, "tarjeta")

    def test_el_molde_del_guion_tambien_parte_el_tablero_y_tapa_el_numero(self):
        self.assertEqual(rodaje_de_guion(self._guion("mito_realidad")).partida, "mitades")
        self.assertEqual(rodaje_de_guion(self._guion("mito_realidad")).tapar_resultado, "tapada")
        self.assertEqual(rodaje_de_guion(self._guion("pov")).partida, "seguida")
        self.assertEqual(rodaje_de_guion(self._guion(None)).tapar_resultado, "visible")


class OverridesTest(unittest.TestCase):
    def test_la_copia_del_autor_gana_sobre_la_del_motor(self):
        propio = yaml.safe_load(mod.PLANTILLA.read_text(encoding="utf-8"))
        propio["pov"]["pasos"] = "pila"
        with _recetas_de_autor(yaml.safe_dump(propio, allow_unicode=True)):
            self.assertEqual(rodaje_para("pov").pasos, "pila")

    def test_un_campo_mal_escrito_dice_cuales_son_los_buenos(self):
        roto = {"pov": {"pasos": "amontonados", "error": "sale", "contador": "ninguno",
                        "primer_plano": "destacar"}}
        with _recetas_de_autor(yaml.safe_dump(roto, allow_unicode=True)):
            with self.assertRaises(ErrorMotor) as sube:
                rodaje_para("pov")
        self.assertIn("pasos=ancla|pila", sube.exception.ayuda or "")

    def test_una_receta_incompleta_dice_qué_falta(self):
        with _recetas_de_autor("pov:\n  pasos: ancla\n"):
            with self.assertRaises(ErrorMotor) as sube:
                rodaje_para("pov")
        self.assertIn("error", str(sube.exception))


def _recetas_de_autor(texto: str):
    from contextlib import contextmanager

    @contextmanager
    def contexto():
        ruta = Path(mkdtemp()) / "rodaje.yaml"
        ruta.write_text(texto, encoding="utf-8")
        original = mod._ruta_usuario
        mod._ruta_usuario = lambda: ruta
        try:
            yield
        finally:
            mod._ruta_usuario = original

    return contexto()


if __name__ == "__main__":
    unittest.main()
