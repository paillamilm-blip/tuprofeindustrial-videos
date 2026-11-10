"""Blindaje contra guiones incoherentes, pausas en la voz y metadatos para redes."""

import math
import tempfile
import unittest
import wave
from pathlib import Path

import yaml
from pydantic import ValidationError

from tpi_videos.guion import Guion, Metadatos, Paso, Resultado, Visual, a_yaml
from tpi_videos.pausas import segundos_de_pausa, sin_pausas, trozos, validar_pausas
from tpi_videos.revision import estimar_segundos

try:
    import manim_voiceover  # noqa: F401
    import pydub  # noqa: F401

    VOZ = True
except ImportError:
    VOZ = False

TOLVA = {
    "tipo": "tolva_3d",
    "radio": "1,5 m",
    "altura": "2 m",
    "radio_salida": "0,3 m",
    "altura_cono": "1,2 m",
}
GRAFICO = {"tipo": "grafico_funcion", "funcion": "x^2", "rango": [-3, 3]}


def _guion(**extra):
    return {
        "titulo": "T",
        "materia": "fisica",
        "gancho": {"texto": "¿Sí?"},
        "enunciado": {"texto": "E"},
        "pasos": [{"voz": "Una voz.", "tex": "x = 1"}],
        "resultado": {"tex": "x = 1", "voz": "Listo."},
        **extra,
    }


class ReglaATest(unittest.TestCase):
    def test_el_despiece_va_en_los_cuerpos_3d(self):
        for tipo in ("tolva_3d", "tuberia_3d", "eje_3d", "solido_3d"):
            datos = {
                "tolva_3d": TOLVA,
                "tuberia_3d": {
                    "tipo": "tuberia_3d",
                    "radio": "10 cm",
                    "espesor": "1 cm",
                    "longitud": "80 cm",
                },
                "eje_3d": {"tipo": "eje_3d", "radios": [20, 30], "largos": [60, 90], "unidad": "mm"},
                "solido_3d": {"tipo": "solido_3d", "figura": "cilindro", "radio": "3 cm", "altura": "5 cm"},
            }[tipo]
            self.assertTrue(Visual.model_validate({**datos, "despiece": True}).despiece, tipo)

    def test_en_un_dibujo_plano_se_rechaza_con_un_mensaje_claro(self):
        for datos in (GRAFICO, {"tipo": "proyectil", "velocidad": "20 m/s", "angulo": 30}):
            with self.assertRaises(ValidationError) as error:
                Visual.model_validate({**datos, "despiece": True})
            self.assertIn("despiece solo va en un cuerpo 3D", str(error.exception))


class ReglaBTest(unittest.TestCase):
    def test_desde_y_hasta_piden_movimiento(self):
        for campo in ("desde", "hasta"):
            with self.assertRaises(ValidationError) as error:
                Visual.model_validate({**GRAFICO, campo: 0})
            self.assertIn("movimiento", str(error.exception))
        self.assertEqual(Visual.model_validate({**GRAFICO, "movimiento": "tangente", "desde": 0}).desde, 0)

    def test_desde_en_un_dibujo_que_no_es_grafico_se_rechaza(self):
        with self.assertRaises(ValidationError):
            Visual.model_validate(
                {"tipo": "proyectil", "velocidad": "20 m/s", "angulo": 30, "desde": 0, "hasta": 5}
            )

    def test_movimiento_true_se_explica(self):
        with self.assertRaises(ValidationError) as error:
            Visual.model_validate({**GRAFICO, "movimiento": True})
        self.assertIn('"tangente" o "area"', str(error.exception))
        self.assertEqual(Visual.model_validate({**GRAFICO, "movimiento": False}).movimiento, "")


class ReglaCTest(unittest.TestCase):
    def test_los_interruptores_solo_aceptan_true_o_false(self):
        for valor in ("si", "true", 1, "yes"):
            with self.assertRaises(ValidationError, msg=repr(valor)):
                Visual.model_validate({**TOLVA, "despiece": valor})
            with self.assertRaises(ValidationError, msg=repr(valor)):
                Resultado.model_validate({"tex": "x", "voz": "Listo.", "destello": valor})
            with self.assertRaises(ValidationError, msg=repr(valor)):
                Paso.model_validate({"voz": "V", "tex": "x = 1", "resaltar_cambio": valor})
        self.assertTrue(Resultado.model_validate({"tex": "x", "voz": "Listo.", "destello": True}).destello)

    def test_el_yaml_de_siempre_sigue_entrando(self):
        texto = "tipo: tolva_3d\nradio: '1,5 m'\naltura: '2 m'\nradio_salida: '0,3 m'\naltura_cono: '1,2 m'\ndespiece: true\n"
        self.assertTrue(Visual.model_validate(yaml.safe_load(texto)).despiece)


class AlgebraTest(unittest.TestCase):
    def test_un_halo_inventado_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            Paso.model_validate({"voz": "V", "tex": "x^2 = 25", "halo": ["y^3"]})
        self.assertIn("no aparece en la fórmula", str(error.exception))
        self.assertEqual(Paso.model_validate({"voz": "V", "tex": "x^2 = 25", "halo": "x^2"}).halo, ["x^2"])

    def test_cambio_sin_formula_o_en_un_error_se_rechaza(self):
        with self.assertRaises(ValidationError):
            Paso.model_validate({"voz": "V", "resaltar_cambio": True})
        with self.assertRaises(ValidationError):
            Paso.model_validate({"voz": "V", "tex": "x = 1", "error": True, "resaltar_cambio": True})


class PausasTest(unittest.TestCase):
    def test_la_voz_se_parte_en_trozos_con_su_silencio(self):
        voz = 'Mira cómo se abre. <break time="1.5s"/> Son dos piezas. <break time="500ms"/>'
        self.assertEqual(trozos(voz), [("Mira cómo se abre.", 1.5), ("Son dos piezas.", 0.5)])
        self.assertEqual(sin_pausas(voz), "Mira cómo se abre. Son dos piezas.")
        self.assertAlmostEqual(segundos_de_pausa(voz), 2.0)
        self.assertEqual(trozos("Sin pausas."), [("Sin pausas.", 0.0)])

    def test_la_estimacion_suma_el_silencio(self):
        voz = "Mira cómo se abre la tolva."
        self.assertAlmostEqual(estimar_segundos(voz + ' <break time="1.5s"/>'), estimar_segundos(voz) + 1.5)

    def test_etiquetas_inventadas_y_pausas_absurdas_se_rechazan(self):
        for mala in (
            'Hola <prosody rate="slow">lento</prosody>',
            'Pausa <break time="10s"/> larga.',
            'Pausa <break time="0.05s"/> corta.',
            '<break time="1s"/>',
            'a <break time="2s"/> b <break time="2s"/> c <break time="2s"/>',
        ):
            with self.assertRaises(ValueError, msg=mala):
                validar_pausas(mala)
        Paso.model_validate({"voz": 'Mira. <break time="1,5s"/> Listo.', "tex": "x = 1"})

    def test_la_revision_no_confunde_la_pausa_con_un_simbolo(self):
        from tpi_videos.config import cargar_marca
        from tpi_videos.revision import revisar

        datos = _guion()
        datos["pasos"][0]["voz"] = 'Mira cómo se mueve. <break time="1.5s"/> Ahí está.'
        avisos = revisar(Guion.model_validate(datos), cargar_marca().cierre.voz).avisos
        self.assertFalse([a for a in avisos if a.donde == "paso 1" and a.nivel == "advertencia"])


@unittest.skipUnless(VOZ, "manim-voiceover o pydub no están instalados")
class ServicioConPausasTest(unittest.TestCase):
    def test_el_silencio_se_suma_al_audio_y_corre_las_marcas(self):
        from tpi_videos.voces import ServicioConPausas, SilencioService

        with tempfile.TemporaryDirectory() as carpeta:
            servicio = ServicioConPausas(SilencioService(), "silencio", cache_dir=carpeta)
            solo = servicio.generate_from_text("Mira cómo se abre la tolva.", cache_dir=carpeta)
            con = servicio.generate_from_text(
                'Mira cómo se abre la tolva. <break time="1.5s"/> Son dos piezas.', cache_dir=carpeta
            )

            def segundos(datos):
                with wave.open(str(Path(carpeta) / datos["original_audio"])) as w:
                    return w.getnframes() / w.getframerate()

            esperado = (
                estimar_segundos("Mira cómo se abre la tolva.") + 1.5 + estimar_segundos("Son dos piezas.")
            )
            self.assertTrue(math.isclose(segundos(con), esperado, abs_tol=0.05))
            self.assertAlmostEqual(segundos(solo), estimar_segundos("Mira cómo se abre la tolva."), places=2)
            self.assertEqual(con["input_text"], "Mira cómo se abre la tolva. Son dos piezas.")
            palabras = [m["text"] for m in con["word_boundaries"]]
            self.assertEqual(palabras[-3:], ["Son", "dos", "piezas."])
            despues = next(m for m in con["word_boundaries"] if m["text"] == "Son")
            self.assertGreater(despues["audio_offset"] / 10_000_000, segundos(solo) + 1.4)


class MetadatosTest(unittest.TestCase):
    def test_los_hashtags_quedan_limpios(self):
        m = Metadatos(
            titulo="¿Sube o baja?",
            descripcion="Lo vemos.",
            hashtags=["#Física", "tiro parabolico", "#fisica", "paes"],
        )
        self.assertEqual(m.hashtags, ["#fisica", "#tiroparabolico", "#paes"])

    def test_hashtags_con_signos_o_titulos_largos_se_rechazan(self):
        with self.assertRaises(ValidationError):
            Metadatos(titulo="T", descripcion="D", hashtags=["#fisica!", "#a", "#b"])
        with self.assertRaises(ValidationError):
            Metadatos(titulo="x" * 101, descripcion="D", hashtags=["#a", "#b", "#c"])
        with self.assertRaises(ValidationError):
            Metadatos(titulo="Mira #fisica", descripcion="D", hashtags=["#a", "#b", "#c"])

    def test_es_opcional_y_viaja_al_yaml(self):
        self.assertIsNone(Guion.model_validate(_guion()).metadatos)
        datos = _guion(
            metadatos={
                "titulo": "¿Sube? 🚀",
                "descripcion": "Una línea.\nOtra línea.",
                "hashtags": ["#a", "#b", "#c"],
            }
        )
        texto = a_yaml(datos)
        self.assertIn("metadatos:", texto)
        vuelta = Guion.model_validate(yaml.safe_load(texto))
        self.assertEqual(vuelta.metadatos.descripcion, "Una línea.\nOtra línea.")
        self.assertNotIn("metadatos:", a_yaml(_guion()))

    def test_el_kit_usa_los_metadatos_del_guion(self):
        from tpi_videos.publicar import textos_de_metadatos

        g = Guion.model_validate(
            _guion(metadatos={"titulo": "¿Sube?", "descripcion": "Lo vemos.", "hashtags": ["#a", "#b", "#c"]})
        )
        textos = textos_de_metadatos(g)
        self.assertEqual(textos.titulo_youtube, "¿Sube?")
        self.assertEqual(textos.hashtags, ["#a", "#b", "#c"])
        self.assertIsNone(textos_de_metadatos(Guion.model_validate(_guion())))


if __name__ == "__main__":
    unittest.main()
