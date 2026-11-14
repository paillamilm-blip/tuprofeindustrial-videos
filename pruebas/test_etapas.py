"""Las etapas de un video en la sala: cada una con su porcentaje y su check (sin abrir el panel)."""

import unittest

from tpi_videos.panel.etapas import ACTIVA, ERROR, ESPERA, HECHA, avance_total, etapas_de
from tpi_videos.panel.supervision import EN_RENDER, PENDIENTES, columnas


def _resumen(etapas):
    return [(e.clave, e.estado, e.porcentaje) for e in etapas]


class EtapasTest(unittest.TestCase):
    def test_son_cuatro_y_en_orden(self):
        etapas = etapas_de("en_cola", 0.0)
        self.assertEqual([e.nombre for e in etapas], ["Guion", "Animación", "Video", "Kit"])

    def test_un_video_en_espera_no_tiene_nada_hecho(self):
        etapas = etapas_de("en_cola", 0.0)
        self.assertTrue(all(e.estado == ESPERA and e.porcentaje == 0 for e in etapas))
        self.assertEqual(avance_total(etapas), 0)

    def test_el_guion_escrito_deja_su_check_aunque_el_video_espere(self):
        etapas = etapas_de("en_cola", 0.0, {"guion"})
        self.assertEqual(_resumen(etapas)[0], ("guion", HECHA, 100))
        self.assertTrue(all(e.estado == ESPERA for e in etapas[1:]))

    def test_animando_muestra_el_porcentaje_de_la_animacion(self):
        # lote._traducir: la animación va de 0,25 a 0,90 del video
        etapas = etapas_de("animando", 0.25 + 0.65 * 0.6, {"guion"})
        self.assertEqual(_resumen(etapas)[:2], [("guion", HECHA, 100), ("animacion", ACTIVA, 60)])
        self.assertEqual(avance_total(etapas), 64)

    def test_los_subtitulos_cierran_la_animacion_y_abren_el_video_final(self):
        etapas = etapas_de("subtitulos", 0.90, {"guion"})
        self.assertEqual(_resumen(etapas)[1:3], [("animacion", HECHA, 100), ("video", ACTIVA, 0)])

    def test_el_kit_es_lo_ultimo(self):
        etapas = etapas_de("kit", 0.97, {"guion", "video"})
        self.assertEqual([e.estado for e in etapas], [HECHA, HECHA, HECHA, ACTIVA])
        self.assertEqual(etapas[3].porcentaje, 40)

    def test_listo_tiene_todo_en_cien_con_su_check(self):
        etapas = etapas_de("listo", 1.0)
        self.assertTrue(all(e.hecha and e.porcentaje == 100 for e in etapas))
        self.assertEqual(avance_total(etapas), 100)

    def test_un_fallo_marca_la_etapa_donde_quedo(self):
        etapas = etapas_de("fallo", 0.5, {"guion"})
        self.assertEqual(_resumen(etapas)[:2], [("guion", HECHA, 100), ("animacion", ERROR, 38)])
        self.assertTrue(all(e.estado == ESPERA for e in etapas[2:]))

    def test_un_hito_de_video_deja_lista_la_animacion_aunque_el_avance_se_reinicie(self):
        etapas = etapas_de("interrumpido", 0.1, {"guion", "video"})
        self.assertEqual([e.estado for e in etapas], [HECHA, HECHA, HECHA, ESPERA])

    def test_nunca_se_pasa_de_cien_ni_baja_de_cero(self):
        self.assertTrue(all(0 <= e.porcentaje <= 100 for e in etapas_de("animando", 7)))
        self.assertTrue(all(0 <= e.porcentaje <= 100 for e in etapas_de("animando", -3)))
        self.assertEqual(avance_total(etapas_de("en_cola", None)), 0)

    def test_un_avance_a_medias_nunca_muestra_cien(self):
        # 100 % es para lo que ya terminó: el check
        e = etapas_de("animando", 0.8999, {"guion"})[1]
        self.assertEqual((e.estado, e.porcentaje), (ACTIVA, 99))

    def test_el_texto_para_lectores_de_pantalla(self):
        etapas = etapas_de("animando", 0.25 + 0.65 * 0.6, {"guion"})
        self.assertEqual(etapas[0].texto, "Guion: listo")
        self.assertEqual(etapas[1].texto, "Animación: 60 %")
        self.assertEqual(etapas_de("fallo", 0.5, {"guion"})[1].texto, "Animación: falló en 38 %")


class FichaTraeSusEtapasTest(unittest.TestCase):
    def _datos(self, estado, avance, hitos=None):
        video = {
            "id": "L1-1",
            "posicion": 1,
            "estado": estado,
            "avance": avance,
            "idea": {"titulo": "Video 1"},
            "actualizado": "2026-11-10T10:00:00",
        }
        if hitos is not None:
            video["hitos"] = hitos
        return {
            "version": 1,
            "lotes": [{"id": "L1", "tema": "Tema", "estado": "en_curso", "videos": [video]}],
        }

    def test_la_ficha_en_render_trae_el_avance_de_cada_etapa(self):
        datos = self._datos("animando", 0.25 + 0.65 * 0.5, {"guion": {"ruta": "x.yaml"}})
        ficha = columnas(datos)[EN_RENDER][0]
        self.assertEqual(_resumen(ficha.etapas)[:2], [("guion", HECHA, 100), ("animacion", ACTIVA, 50)])

    def test_el_avance_en_vivo_mueve_las_etapas(self):
        datos = self._datos("en_cola", 0.0)
        ficha = columnas(datos, {"L1-1": {"estado": "animando", "avance": 0.25 + 0.65 * 0.2}})[EN_RENDER][0]
        self.assertEqual(ficha.etapas[1].porcentaje, 20)

    def test_un_video_que_falla_queda_con_su_etapa_en_error(self):
        ficha = columnas(self._datos("fallo", 0.5, {"guion": {}}))[PENDIENTES][0]
        self.assertTrue(ficha.fallo)
        self.assertEqual(ficha.etapas[1].estado, ERROR)

    def test_sin_hitos_en_la_cola_no_se_rompe(self):
        ficha = columnas(self._datos("en_cola", 0.0))[PENDIENTES][0]
        self.assertEqual(len(ficha.etapas), 4)


if __name__ == "__main__":
    unittest.main()
