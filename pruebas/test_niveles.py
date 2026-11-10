"""Los dos públicos: niveles leídos con tolerancia y la carrera opcional del guion."""

import unittest

from tpi_videos.niveles import CARRERAS, NIVELES, es_universidad, normalizar, publico_de


class NivelesTest(unittest.TestCase):
    def test_media_escrita_de_muchas_formas(self):
        for texto, nivel in (
            ("3° medio", "3° medio"),
            ("3 medio", "3° medio"),
            ("2º Medio", "2° medio"),
            ("4° medio · PAES", "4° medio"),
            ("1° año medio", "1° medio"),
        ):
            self.assertEqual(normalizar(texto), nivel, texto)

    def test_universidad_escrita_de_muchas_formas(self):
        for texto, nivel in (
            ("2° año ingeniería", "2° año ingeniería"),
            ("2° año de ingeniería", "2° año ingeniería"),
            ("segundo año ingeniería civil", "2° año ingeniería"),
            ("Primer año de universidad", "1° año ingeniería"),
            ("3er año de la carrera", None),  # «3er» no es un número claro: mejor no adivinar
            ("5° año de ingeniería", "4° año ingeniería"),  # la especialidad final es un nivel
            ("quinto año ingeniería eléctrica", "4° año ingeniería"),
        ):
            self.assertEqual(normalizar(texto), nivel, texto)

    def test_lo_que_no_es_un_nivel_claro(self):
        for texto in ("técnico en electricidad", "enseñanza media (Chile)", "2° año", "", None):
            self.assertIsNone(normalizar(texto), texto)

    def test_publico_de_cada_nivel(self):
        self.assertEqual([publico_de(n) for n in NIVELES], ["media"] * 4 + ["universidad"] * 4)
        self.assertTrue(es_universidad("segundo año de ingeniería"))
        self.assertFalse(es_universidad("3° medio"))
        self.assertEqual(set(CARRERAS), {"industrial", "electrica", "obras_civiles"})


class MallaTest(unittest.TestCase):
    def test_cada_nivel_y_materia_tiene_ramos(self):
        from tpi_videos.malla import MATERIAS_MALLA, ramos

        for nivel in NIVELES:
            for materia in MATERIAS_MALLA:
                self.assertTrue(ramos(nivel, materia), f"{nivel} · {materia} sin ramos")

    def test_desde_tercer_ano_ingenieria_va_por_carrera(self):
        from tpi_videos.malla import carreras_del_nivel, ramos

        for nivel in ("3° año ingeniería", "4° año ingeniería"):
            self.assertEqual(set(carreras_del_nivel(nivel)), set(CARRERAS), nivel)
            for carrera in CARRERAS:
                self.assertTrue(ramos(nivel, "ingenieria", carrera), (nivel, carrera))
        self.assertEqual(carreras_del_nivel("1° año ingeniería"), ())  # plan común
        electrica = ramos("3° año ingeniería", "ingenieria", "electrica")
        self.assertTrue(any("Thévenin" in r for r in electrica))
        self.assertGreater(len(ramos("3° año ingeniería", "ingenieria")), len(electrica))

    def test_una_malla_propia_le_gana_a_la_incluida(self):
        import os
        import tempfile
        from pathlib import Path

        from tpi_videos.malla import ramos

        with tempfile.TemporaryDirectory() as tmp:
            viejo = os.environ.get("TPI_RAIZ")
            os.environ["TPI_RAIZ"] = tmp
            try:
                (Path(tmp) / "mis_ajustes").mkdir()
                (Path(tmp) / "mis_ajustes" / "malla.yaml").write_text(
                    '"1° medio":\n  matematica: ["Mi tema"]\n', encoding="utf-8"
                )
                self.assertEqual(ramos("1° medio", "matematica"), ["Mi tema"])
            finally:
                if viejo is None:
                    os.environ.pop("TPI_RAIZ", None)
                else:
                    os.environ["TPI_RAIZ"] = viejo


class CarreraEnElGuionTest(unittest.TestCase):
    def _datos(self, **extra):
        return {
            "titulo": "T",
            "materia": "ingenieria",
            "nivel": "3° año ingeniería",
            "gancho": {"texto": "¿Sí?"},
            "enunciado": {"texto": "E"},
            "pasos": [{"voz": "Una voz.", "tex": "x = 1"}],
            "resultado": {"tex": "x = 1", "voz": "Listo."},
            **extra,
        }

    def test_es_opcional_valida_y_viaja_en_el_yaml(self):
        import yaml
        from pydantic import ValidationError

        from tpi_videos.guion import Guion, a_yaml

        self.assertIsNone(Guion.model_validate(self._datos()).carrera)
        g = Guion.model_validate(self._datos(carrera="electrica"))
        self.assertEqual(g.carrera, "electrica")
        texto = a_yaml(g.model_dump(exclude_none=True))
        self.assertIn("carrera: electrica", texto)
        self.assertEqual(Guion.model_validate(yaml.safe_load(texto)).carrera, "electrica")
        self.assertNotIn(
            "carrera:", a_yaml(Guion.model_validate(self._datos()).model_dump(exclude_none=True))
        )
        with self.assertRaises(ValidationError):
            Guion.model_validate(self._datos(carrera="quimica"))
        # escrita a mano con tildes o espacios también vale
        self.assertEqual(Guion.model_validate(self._datos(carrera="Obras Civiles")).carrera, "obras_civiles")


class PistaDeLaMallaTest(unittest.TestCase):
    def test_solo_la_universidad_lleva_la_malla(self):
        from tpi_videos.malla import pista_para_la_ia

        self.assertIsNone(pista_para_la_ia("3° medio", "fisica"))
        pista = pista_para_la_ia("3° año ingeniería", "ingenieria", "electrica")
        self.assertIn("PÚBLICO UNIVERSITARIO", pista)
        self.assertIn("Ing. Civil Eléctrica", pista)
        self.assertIn("Thévenin", pista)
        self.assertNotIn("programación lineal", pista)  # es de Industrial

    def test_redactar_manda_la_pista_y_guarda_nivel_y_carrera(self):
        try:
            from google import genai  # noqa: F401
        except ImportError:
            self.skipTest("google-genai no está instalado")
        import tempfile
        from pathlib import Path
        from unittest import mock

        import yaml

        from pruebas.ia_falsa import ClienteFalso
        from tpi_videos import redactor

        falso = ClienteFalso()
        with tempfile.TemporaryDirectory() as carpeta:
            with (
                mock.patch.object(redactor.ia, "cliente", return_value=falso),
                mock.patch.object(redactor, "raiz_proyecto", return_value=Path(carpeta)),
            ):
                r = redactor.redactar(
                    "Un balance de masa en una tolva de inyección",
                    materia="ingenieria",
                    nivel="segundo año de ingeniería",
                    carrera="industrial",
                    revisar_con_ia=False,
                )
            datos = yaml.safe_load(r.ruta.read_text(encoding="utf-8"))
        self.assertIn("PÚBLICO UNIVERSITARIO", falso.pedidos[0])
        self.assertIn("Estática", falso.pedidos[0])
        self.assertEqual(datos["nivel"], "2° año ingeniería")
        self.assertEqual(datos["carrera"], "industrial")
        self.assertEqual(r.guion.carrera, "industrial")


if __name__ == "__main__":
    unittest.main()
