"""Dos dibujos que salen de una integral: el oscilador amortiguado y el péndulo doble.

La física ya está probada en ``test_simulacion.py``; aquí se prueba que el guion los puede pedir,
que las unidades del guion son las que salen en pantalla y que el catálogo las ofrece.
"""

import unittest

from pydantic import ValidationError

from tpi_videos.guion import Visual, _visual_yaml
from tpi_videos.redactor import PasoIA, _visual
from tpi_videos.visuales import (
    MARCAS_OSCILADOR,
    MARCAS_PENDULO_DOBLE,
    SEGUNDOS_VISUAL,
    VISUALES,
    analizar_oscilador,
    analizar_pendulo_doble,
)

ANCHO_HOJA = 7.0  # el ancho útil de la hoja cuadriculada (componentes.ANCHO_UTIL)

try:
    import manim  # noqa: F401

    MANIM = True
except ImportError:  # el panel y las pruebas corren sin Manim
    MANIM = False

if MANIM:
    from manim import Text

    from tpi_videos.dibujos import ALTO_DIBUJO, oscilador, pendulo_doble
    from tpi_videos.temas import ColoresTema


class OsciladorTest(unittest.TestCase):
    def test_el_amortiguamiento_se_midemedio_de_la_resistencia_critica(self):
        """ζ = c / 2√(k·m): con 8 N·s/m sobre 2 kg y 200 N/m queda ζ = 0,2 y sigue oscilando."""
        o = analizar_oscilador("2 kg", "200 N/m", "10 cm", "8 N·s/m")
        self.assertAlmostEqual(o.zeta, 0.2, places=6)
        self.assertEqual(o.regimen, "subamortiguado")
        self.assertGreater(o.periodo, 0.0)

    def test_la_amplitud_se_muestra_en_la_unidad_del_guion(self):
        """Si el guion dice «10 cm», la pantalla tiene que decir 10, no 0,1."""
        o = analizar_oscilador("2 kg", "200 N/m", "10 cm", "8 N·s/m", 4.0)
        self.assertEqual(o.unidad, "cm")
        self.assertAlmostEqual(o.amplitud, 10.0, places=6)
        self.assertAlmostEqual(max(abs(v) for v in o.x), 10.0, places=4)

    def test_sin_amortiguamiento_sigue_siendo_el_mismo_dibujo(self):
        o = analizar_oscilador("1 kg", "50 N/m", "0,3 m")
        self.assertEqual(o.regimen, "sin amortiguamiento")
        self.assertEqual(o.unidad, "m")
        self.assertIsNone(o.decaimiento)

    def test_los_gramos_y_los_kilos_mandan_lo_mismo(self):
        gramos = analizar_oscilador("500 g", "200 N/m", "10 cm")
        kilos = analizar_oscilador("0,5 kg", "200 N/m", "10 cm")
        self.assertAlmostEqual(gramos.periodo, kilos.periodo, places=9)

    def test_mas_amortiguamiento_llega_antes_al_equilibrio(self):
        suave = analizar_oscilador("1 kg", "100 N/m", "10 cm", "2 N·s/m", 6.0)
        duro = analizar_oscilador("1 kg", "100 N/m", "10 cm", "30 N·s/m", 6.0)
        self.assertLess(abs(duro.x[-1]), abs(suave.x[-1]), "el más amortiguado no se quieto antes")

    def test_un_numero_que_no_es_dice_su_campo_en_espanol(self):
        with self.assertRaises(ValueError) as error:
            analizar_oscilador("2 kg", "fuerte", "10 cm")
        self.assertIn("constante", str(error.exception))
        with self.assertRaises(ValueError):
            analizar_oscilador("", "200 N/m", "10 cm")
        with self.assertRaises(ValueError):
            analizar_oscilador("2 kg", "200 N/m", "")


class PenduloDobleTest(unittest.TestCase):
    def test_los_centimetros_se_suman_en_metros_para_la_traza(self):
        p = analizar_pendulo_doble("1 kg", "1 kg", "80 cm", "1,2 m", 170.0, 170.0)
        self.assertAlmostEqual(p.radio_maximo(), 2.0, places=9)
        self.assertEqual(p.unidad, "m")
        for x, y in p.traza:
            self.assertLessEqual((x * x + y * y) ** 0.5, 2.0 + 1e-9)

    def test_se_suelta_desde_el_angulo_del_guion(self):
        p = analizar_pendulo_doble("1 kg", "1 kg", "1 m", "1 m", 120.0, -40.0, duracion=6.0)
        self.assertAlmostEqual(p.angulo_1[0], 120.0, places=6)
        self.assertAlmostEqual(p.angulo_2[0], -40.0, places=6)
        self.assertEqual(len(p.t), len(p.traza))

    def test_un_pendulo_doble_sin_masas_no_se_puede_simular(self):
        with self.assertRaises(ValueError) as error:
            analizar_pendulo_doble("", "1 kg", "1 m", "1 m", 60.0, 60.0)
        self.assertIn("masa_1", str(error.exception))


class CatalogoTest(unittest.TestCase):
    def test_la_tabla_ofrece_a_los_dos_con_sus_campos(self):
        for clave, nombre in (("oscilador", "Oscilador"), ("pendulo_doble", "Péndulo doble")):
            self.assertIn(clave, VISUALES, clave)
            tipo = VISUALES[clave]
            self.assertEqual(tipo.materia, "fisica", clave)
            self.assertTrue(tipo.ejemplo, clave)
            self.assertGreaterEqual(SEGUNDOS_VISUAL[clave], 2.5, clave)
            for campo in tipo.campos:
                self.assertIn(campo, Visual.model_fields, f"{clave} pide {campo}")

    def test_las_marcas_prometidas_son_las_del_motor(self):
        self.assertEqual(MARCAS_OSCILADOR, ("regimen", "periodo", "decaimiento"))
        self.assertEqual(MARCAS_PENDULO_DOBLE, ("energia", "angulos"))
        self.assertEqual(VISUALES["oscilador"].marcas, MARCAS_OSCILADOR)
        self.assertEqual(VISUALES["pendulo_doble"].marcas, MARCAS_PENDULO_DOBLE)


class GuionTest(unittest.TestCase):
    def test_el_guion_pide_un_oscilador_y_sale_la_curva(self):
        visual = Visual(
            tipo="oscilador",
            masa="2 kg",
            constante="200 N/m",
            amplitud="10 cm",
            amortiguamiento="8 N·s/m",
            duracion=4.0,
            anotar=["regimen", "periodo"],
        )
        o = visual.oscilador()
        self.assertAlmostEqual(o.zeta, 0.2, places=6)
        self.assertEqual(o.hasta, 4.0)

    def test_sin_amplitud_el_guion_la_pide(self):
        with self.assertRaises(ValidationError) as error:
            Visual(tipo="oscilador", masa="2 kg", constante="200 N/m")
        self.assertIn("amplitud", str(error.exception))

    def test_anotar_el_periodo_exige_que_este_subamortiguado(self):
        with self.assertRaises(ValidationError) as error:
            Visual(
                tipo="oscilador",
                masa="1 kg",
                constante="100 N/m",
                amplitud="10 cm",
                amortiguamiento="40 N·s/m",
                anotar=["periodo"],
            )
        self.assertIn("subamortiguado", str(error.exception))

    def test_anotar_el_decaimiento_necesita_amortiguador(self):
        with self.assertRaises(ValidationError) as error:
            Visual(
                tipo="oscilador",
                masa="1 kg",
                constante="100 N/m",
                amplitud="10 cm",
                anotar=["decaimiento"],
            )
        self.assertIn("amortiguamiento", str(error.exception))

    def test_el_pendulo_doble_se_guarda_en_el_yaml(self):
        texto = "\n".join(
            _visual_yaml(
                {
                    "tipo": "pendulo_doble",
                    "masa_1": "1 kg",
                    "masa_2": "800 g",
                    "longitud_1": "1 m",
                    "longitud_2": "1 m",
                    "angulo_1": 170,
                    "angulo_2": 170,
                    "duracion": 8.0,
                    "anotar": ["energia"],
                }
            )
        )
        self.assertIn("tipo: pendulo_doble", texto)
        self.assertIn("masa_2: '800 g'", texto)
        self.assertIn("angulo_1: 170", texto)
        self.assertIn("duracion: 8", texto)
        self.assertIn("anotar: ['energia']", texto)

    def test_la_ia_puede_pedir_el_pendulo_doble(self):
        paso = PasoIA(
            nota="Nadie predice dónde termina",
            tex=r"\theta_1(t)",
            voz="Mira el péndulo doble.",
            dibujo="pendulo_doble",
            masa_1="1 kg",
            masa_2="1 kg",
            longitud_1="1 m",
            longitud_2="1 m",
            angulo_1=170,
            angulo_2=170,
            duracion=8,
            anotar=["energia"],
        )
        visual = Visual(**_visual(paso))
        self.assertEqual(visual.tipo, "pendulo_doble")
        self.assertEqual(visual.longitud_2, "1 m")
        self.assertAlmostEqual(visual.duracion, 8.0, places=6)

    def test_la_ia_puede_pedir_el_oscilador(self):
        paso = PasoIA(
            nota="La amplitud se apaga",
            tex=r"x(t)=Ae^{-ct/2m}\cos\omega t",
            voz="Mira cómo se apaga.",
            dibujo="oscilador",
            masa="2 kg",
            constante="200 N/m",
            amplitud="10 cm",
            amortiguamiento="8 N·s/m",
            anotar=["regimen"],
        )
        visual = Visual(**_visual(paso))
        self.assertEqual(visual.tipo, "oscilador")
        self.assertAlmostEqual(visual.oscilador().zeta, 0.2, places=6)


@unittest.skipUnless(MANIM, "manim no está instalado")
class DibujoOsciladorPenduloTest(unittest.TestCase):
    """El motor los mete en la franja del pie y escribe sólo lo que el guion pidió anotar."""

    def _textos(self, dib) -> str:
        return " | ".join(m.original_text for m in dib.mobs.get_family() if isinstance(m, Text))

    def test_el_oscilador_entra_en_la_franja_y_escribe_su_regimen(self):
        dib = oscilador(
            analizar_oscilador("2 kg", "200 N/m", "10 cm", "8 N·s/m", 4.0),
            ["regimen", "periodo"],
            ColoresTema(),
            ANCHO_HOJA,
            ALTO_DIBUJO,
        )
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        self.assertTrue(dib.trazo)
        textos = self._textos(dib)
        self.assertIn("subamortiguado", textos)
        self.assertIn("cm", textos)
        self.assertIn("T ≈", textos)

    def test_sin_marcas_el_oscilador_no_escribe_datos_de_mas(self):
        dib = oscilador(
            analizar_oscilador("1 kg", "50 N/m", "0,3 m"),
            [],
            ColoresTema(),
            ANCHO_HOJA,
            ALTO_DIBUJO,
        )
        self.assertTrue(dib.trazo)
        textos = self._textos(dib)
        self.assertNotIn("ζ", textos)
        self.assertNotIn("T ≈", textos)

    def test_el_pendulo_doble_entra_en_la_franja_con_su_traza(self):
        dib = pendulo_doble(
            analizar_pendulo_doble("1 kg", "1 kg", "1 m", "1 m", 170.0, 170.0, duracion=8.0),
            ["energia", "angulos"],
            ColoresTema(),
            ANCHO_HOJA,
            ALTO_DIBUJO,
        )
        self.assertLessEqual(dib.mobs.width, ANCHO_HOJA + 1e-6)
        self.assertLessEqual(dib.mobs.height, ALTO_DIBUJO + 1e-6)
        self.assertTrue(dib.trazo)
        textos = self._textos(dib)
        self.assertIn("J", textos)
        self.assertIn("°", textos)


if __name__ == "__main__":
    unittest.main()
