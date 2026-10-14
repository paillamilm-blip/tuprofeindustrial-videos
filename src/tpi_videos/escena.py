"""Escena principal de Manim: arma el video completo a partir del guion.

Estructura (pensada para retener en video corto y para aprender):
1. Gancho: pregunta o dato sorprendente en los primeros 3 segundos.
2. Enunciado: lo concreto antes que lo abstracto; se subraya cada dato cuando la voz lo dice.
3. Datos: lista breve que luego queda fija arriba como referencia.
4. Pasos: cada paso es una idea; los términos se mueven de una ecuación a la siguiente
   (``TransformMatchingTex``) para MOSTRAR el cambio en vez de solo narrarlo.
5. Resultado destacado, verificación opcional ("¿tiene sentido?") y un reto final para
   practicar recordando (y generar comentarios).
6. Cierre con la marca y un solo llamado a la acción.

Las transiciones se hacen mientras la voz habla, para que no haya silencios muertos.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from manim import (
    DOWN,
    HEAVY,
    LEFT,
    MEDIUM,
    PI,
    RIGHT,
    SEMIBOLD,
    ULTRABOLD,
    UP,
    Animation,
    Circumscribe,
    Create,
    Dot,
    FadeIn,
    FadeOut,
    Group,
    Indicate,
    LaggedStart,
    Mobject,
    Rotate,
    RoundedRectangle,
    SurroundingRectangle,
    TransformMatchingTex,
    VGroup,
    Write,
    config,
)
from manim_voiceover import VoiceoverScene
from manim_voiceover.helper import remove_bookmarks

from . import componentes as c
from .config import Marca
from .guion import Bloque, Guion, sin_tildes
from .voces import RESOLUCION, crear_servicio


@dataclass
class OpcionesEscena:
    proveedor: str
    voz: str
    velocidad: str
    linea_de_tiempo: Path


class VideoEjercicio(VoiceoverScene):
    def __init__(self, guion: Guion, marca: Marca, opciones: OpcionesEscena, **kwargs: Any) -> None:
        self.guion = guion
        self.marca = marca
        self.op = opciones
        self.col = marca.colores
        self.color_materia = getattr(marca.materias, guion.materia)
        self.bloques_voz: list[dict[str, Any]] = []
        self._pendientes: list[Animation] = []  # transiciones para el próximo bloque de voz
        super().__init__(**kwargs)

    # --------------------------------------------------------------------------------------
    # Voz y tiempos
    # --------------------------------------------------------------------------------------

    @contextmanager
    def hablar(self, texto: str, seccion: str):
        with self.voiceover(text=texto) as tracker:
            self._registrar(tracker, seccion)
            yield tracker

    def _registrar(self, tracker: Any, seccion: str) -> None:
        datos = tracker.data
        servicio = (datos.get("input_data") or {}).get("service")
        marcas = datos.get("word_boundaries") or []
        palabras = [
            {
                "texto": m["text"],
                "inicio": m["audio_offset"] / RESOLUCION,
                "fin": m["audio_offset"] / RESOLUCION + m.get("duration_milliseconds", 0) / 1000,
            }
            for m in marcas
        ]
        self.bloques_voz.append(
            {
                "seccion": seccion,
                "inicio": round(float(tracker.start_t), 3),
                "duracion": round(float(tracker.duration), 3),
                "texto": " ".join(remove_bookmarks(datos["input_text"]).split()),
                "audio": str(Path(self.speech_service.cache_dir) / datos["final_audio"]),
                "servicio": servicio,
                # "exactas": vienen del sintetizador; "estimadas": reparto proporcional (sin voz)
                "marcas": "exactas"
                if servicio == "edge-tts" and palabras
                else ("estimadas" if palabras else None),
                "palabras": palabras or None,
            }
        )

    def hasta(self, tracker: Any, segundos: float) -> None:
        """Espera hasta ``segundos`` contados desde que empezó a hablar el bloque."""
        restante = tracker.start_t + segundos - self.renderer.time
        if restante > 1 / config.frame_rate:
            self.wait(restante)

    def momento(self, tracker: Any, frase: str) -> float | None:
        """Segundo (dentro del bloque) en que la voz dice ``frase``."""
        texto = " ".join(remove_bookmarks(tracker.data["input_text"]).split())
        idx = sin_tildes(texto.lower()).find(sin_tildes(frase.lower()))
        if idx < 0:
            return None
        marcas = tracker.data.get("word_boundaries") or []
        if len(marcas) >= 2:
            xs = [m["text_offset"] for m in marcas]
            ys = [m["audio_offset"] / RESOLUCION for m in marcas]
            return float(np.interp(idx, xs, ys))
        return tracker.duration * idx / max(len(texto), 1)

    def _con_pendientes(self, *animaciones: Animation, run_time: float) -> None:
        todas = [*self._pendientes, *animaciones]
        self._pendientes = []
        if todas:
            self.play(*todas, run_time=run_time)

    def _restante(self, tracker: Any) -> float:
        return tracker.get_remaining_duration()

    # --------------------------------------------------------------------------------------
    # Construcción
    # --------------------------------------------------------------------------------------

    def construct(self) -> None:
        servicio = crear_servicio(self.op.proveedor, self.op.voz, self.op.velocidad)
        self.set_speech_service(servicio, create_subcaption=False)
        self.fondo = c.fondo_cuadricula(self.col.cuadricula).set_z_index(-1)
        self.add(self.fondo)

        self._gancho()
        self._enunciado()
        if self.guion.datos:
            self._datos()
        self._pasos()
        self._resultado()
        if self.guion.verificacion:
            self._verificacion()
        if self.guion.reto:
            self._reto()
        self._cierre()
        self._guardar_linea_de_tiempo()

    def _cabecera(self) -> VGroup:
        icono = c.engranaje(0.17, self.col.acento, self.col.fondo)
        nombre = c.texto(self.marca.nombre.upper(), 19, ULTRABOLD, self.col.texto)
        izquierda = VGroup(icono, nombre).arrange(RIGHT, buff=0.16)
        izquierda.move_to([0, c.Y_CABECERA, 0]).to_edge(LEFT, buff=0.6)
        materia = c.chip(self.guion.etiqueta_materia, self.color_materia)
        materia.move_to([0, c.Y_CABECERA, 0]).to_edge(RIGHT, buff=0.6)
        return VGroup(izquierda, materia)

    def _gancho(self) -> None:
        g = self.guion.gancho
        destacar = g.destacar or c.numeros_en(g.texto)
        p = c.parrafo(
            g.texto,
            c.TAM_GANCHO,
            HEAVY,
            self.col.texto,
            destacar=destacar,
            color_destacado=self.col.acento,
            interlineado=0.3,
            max_lineas=4,
        )
        p.move_to([0, c.CENTRO_ZONA + 0.9, 0])
        self.cabecera = self._cabecera()
        with self.hablar(g.voz_final, "gancho") as tr:
            self.play(
                FadeIn(self.cabecera, shift=DOWN * 0.15),
                LaggedStart(*[FadeIn(linea, scale=0.6) for linea in p], lag_ratio=0.15),
                run_time=0.7,
            )
            for frase in destacar:
                letras = c.frase_en_parrafo(p, frase)
                t = self.momento(tr, frase)
                if len(letras) and t is not None:
                    self.hasta(tr, t)
                    self.play(Indicate(letras, color=self.col.acento, scale_factor=1.18), run_time=0.5)
        self._pendientes.append(FadeOut(p, shift=UP * 0.5))

    def _enunciado(self) -> None:
        e = self.guion.enunciado
        self.titulo = c.parrafo(
            self.guion.titulo, c.TAM_TITULO, ULTRABOLD, self.col.texto, interlineado=0.3, max_lineas=2
        )
        if self.titulo.height > 0.95:
            self.titulo.scale_to_fit_height(0.95)
        self.titulo.move_to([0, c.Y_TITULO, 0])

        etiqueta = c.texto("PROBLEMA", c.TAM_ETIQUETA, ULTRABOLD, self.color_materia)
        cuerpo = c.parrafo(
            e.texto,
            c.TAM_CUERPO,
            SEMIBOLD,
            self.col.texto,
            ancho_max=c.ANCHO_UTIL - 0.8,
            alineacion="left",
            destacar=e.destacar,
            color_destacado=self.col.acento,
        )
        contenido = VGroup(etiqueta, cuerpo).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        tarjeta = c.tarjeta(contenido, c.ANCHO_UTIL, self.col.panel, self.col.borde)
        if tarjeta.height > c.ALTO_ZONA - 0.4:
            tarjeta.scale_to_fit_height(c.ALTO_ZONA - 0.4)
        tarjeta.move_to([0, c.CENTRO_ZONA + 0.5, 0])
        subrayados = VGroup()

        with self.hablar(e.voz_final, "enunciado") as tr:
            self._con_pendientes(
                FadeIn(self.titulo, shift=DOWN * 0.15),
                FadeIn(tarjeta[0], scale=0.97),
                FadeIn(etiqueta),
                run_time=0.5,
            )
            self.play(
                LaggedStart(*[FadeIn(linea, shift=RIGHT * 0.12) for linea in cuerpo], lag_ratio=0.25),
                run_time=min(1.6, 0.3 * len(cuerpo) + 0.4),
            )
            eventos = sorted((t, frase) for frase in e.destacar if (t := self.momento(tr, frase)) is not None)
            for t, frase in eventos:
                letras = c.frase_en_parrafo(cuerpo, frase)
                if not len(letras):
                    continue
                self.hasta(tr, t)
                lineas = VGroup(*[c.subrayado(m, self.col.acento, 5, 0.08) for m in letras])
                subrayados.add(lineas)
                self.play(
                    Create(lineas), Indicate(letras, color=self.col.acento, scale_factor=1.06), run_time=0.45
                )
        self._pendientes.append(FadeOut(VGroup(tarjeta, subrayados), shift=UP * 0.3))

    def _datos(self) -> None:
        etiqueta = c.texto("DATOS", c.TAM_ETIQUETA, ULTRABOLD, self.color_materia)
        items = [
            c.ecuacion(d.tex, c.TAM_DATO, self.col.texto, ancho_max=c.ANCHO_UTIL - 1.5).set_z_index(1)
            for d in self.guion.datos
        ]
        vinetas = [Dot(radius=0.07, color=self.color_materia) for _ in items]
        filas = [VGroup(v, it).arrange(RIGHT, buff=0.3) for v, it in zip(vinetas, items, strict=True)]
        lista = VGroup(*filas).arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        contenido = VGroup(etiqueta, lista).arrange(DOWN, aligned_edge=LEFT, buff=0.34)
        tarjeta = c.tarjeta(contenido, c.ANCHO_UTIL, self.col.panel, self.col.borde)
        if tarjeta.height > c.ALTO_ZONA - 0.4:
            tarjeta.scale_to_fit_height(c.ALTO_ZONA - 0.4)
        tarjeta.move_to([0, c.CENTRO_ZONA + 0.5, 0])

        for i, (dato, fila) in enumerate(zip(self.guion.datos, filas, strict=True), 1):
            with self.hablar(dato.voz, f"dato {i}"):
                if i == 1:
                    self._con_pendientes(FadeIn(tarjeta[0], scale=0.97), FadeIn(etiqueta), run_time=0.4)
                self.play(FadeIn(fila, shift=RIGHT * 0.2), run_time=0.45)

        # Los datos quedan fijos arriba, en pequeño, como referencia durante la solución.
        ancho_franja = c.ANCHO_UTIL - 0.5
        compactos = VGroup(*[it.copy() for it in items]).scale(0.72).arrange(RIGHT, buff=0.5)
        if compactos.width > ancho_franja:
            compactos.arrange_in_grid(cols=2, buff=(0.5, 0.2))
        if compactos.width > ancho_franja:
            compactos.scale_to_fit_width(ancho_franja)
        compactos.next_to(self.titulo, DOWN, buff=0.4)
        marco = RoundedRectangle(corner_radius=0.2, width=c.ANCHO_UTIL, height=compactos.height + 0.36)
        marco.set_fill(self.col.panel, 0.9).set_stroke(self.col.borde, 2).move_to(compactos)
        self._pendientes += [
            FadeOut(VGroup(tarjeta[0], etiqueta, *vinetas)),
            FadeIn(marco),
            *[
                it.animate.move_to(comp).scale(comp.height / it.height)
                for it, comp in zip(items, compactos, strict=True)
            ],
        ]
        self.datos_fijos = VGroup(marco, *items)
        self.y_inicio_pasos = marco.get_bottom()[1] - 0.4

    def _pasos(self) -> None:
        """Pizarra vertical: cada paso aparece bajo el anterior. Los pasos anteriores se
        achican y atenúan (quedan como historial) y solo salen por arriba si ya no caben."""
        tope = getattr(self, "y_inicio_pasos", c.Y_ZONA_SUPERIOR - 0.2)
        self.tope_pasos = tope
        alto_zona = tope - c.Y_ZONA_INFERIOR
        pila: list[list[Mobject]] = []  # cada línea: [nota?, ecuación] (se animan por separado)
        en_historial: set[int] = set()  # líneas ya achicadas (por id de la ecuación)
        resaltes: list[VGroup] = []
        ultima: Any = None

        for i, paso in enumerate(self.guion.pasos, 1):
            with self.hablar(paso.voz, f"paso {i}") as tr:
                if paso.tex is None:  # paso solo hablado
                    self._con_pendientes(run_time=0.5)
                    if ultima is not None:
                        self.play(Indicate(ultima, color=self.col.acento, scale_factor=1.04), run_time=0.6)
                    continue

                eq = c.ecuacion(paso.tex, c.TAM_ECUACION, self.col.texto).set_z_index(1)
                if eq.height > c.ALTO_MAX_ECUACION:
                    eq.scale_to_fit_height(c.ALTO_MAX_ECUACION)
                nota = c.texto(paso.nota, 24, SEMIBOLD, self.color_materia) if paso.nota else None
                nueva = VGroup(*[m for m in (nota, eq) if m is not None]).arrange(DOWN, buff=0.16)

                # Destino de cada línea anterior: más pequeña y tenue. Si no cabe todo,
                # salen las más antiguas.
                salen: list[list[Mobject]] = []
                while True:
                    destinos = []
                    for linea in pila:
                        copia = VGroup(*[m.copy() for m in linea])
                        if id(linea[-1]) not in en_historial:
                            copia.scale(c.ESCALA_HISTORIAL)
                        destinos.append(copia.set_fill(opacity=0.35))
                    columna = VGroup(*destinos, nueva).arrange(DOWN, buff=0.34)
                    if columna.height <= alto_zona or not pila:
                        break
                    salen.append(pila.pop(0))
                if columna.height > alto_zona:
                    columna.scale_to_fit_height(alto_zona)
                columna.move_to([0, (tope + c.Y_ZONA_INFERIOR) / 2, 0])  # pizarra centrada

                previas: list[Animation] = [FadeOut(r) for r in resaltes]
                resaltes = []
                for linea in salen:
                    previas += [FadeOut(m, shift=UP * 0.5) for m in linea]
                for linea, destino in zip(pila, destinos, strict=True):
                    previas += [m.animate.become(d) for m, d in zip(linea, destino, strict=True)]
                    en_historial.add(id(linea[-1]))
                self._con_pendientes(*previas, run_time=0.45)

                # Si comparte términos con la ecuación anterior, esos términos "viajan" a la nueva.
                fuente = None
                if ultima is not None and paso.transformar:
                    fuente = (destinos[-1][-1] if pila else ultima).copy().set_fill(opacity=1)
                mapa = c.coincidencias(fuente, eq) if fuente is not None else None
                aparecer: list[Animation] = [FadeIn(nota, shift=DOWN * 0.1)] if nota else []
                if mapa is not None:
                    aparecer.append(TransformMatchingTex(fuente, eq, key_map=mapa))
                else:
                    aparecer.append(Write(eq))
                self.play(*aparecer, run_time=float(np.clip(tr.duration * 0.45, 0.8, 1.6)))

                marcos = VGroup(
                    *[
                        SurroundingRectangle(
                            VGroup(*ps), color=self.col.acento, buff=0.09, corner_radius=0.1, stroke_width=5
                        )
                        for ps in (c.partes_por_tex(eq, d) for d in paso.destacar)
                        if ps
                    ]
                )
                if len(marcos):
                    self.play(Create(marcos), run_time=0.4)
                    resaltes.append(marcos)
                pila.append(list(nueva))
                ultima = eq

        self.pila, self.resaltes, self.ultima = pila, resaltes, ultima

    def _resultado(self) -> None:
        r = self.guion.resultado
        eq = c.ecuacion(r.tex, c.TAM_RESULTADO, self.col.texto, ancho_max=c.ANCHO_UTIL - 1.0).set_z_index(1)
        caja = RoundedRectangle(corner_radius=0.22, width=eq.width + 0.9, height=eq.height + 0.7)
        caja.set_fill(self.col.acento, 0.12).set_stroke(self.col.acento, 5)
        eq.move_to(caja)
        cabeza = VGroup(
            c.visto(self.col.exito), c.texto("RESULTADO", c.TAM_ETIQUETA + 2, ULTRABOLD, self.col.exito)
        )
        cabeza.arrange(RIGHT, buff=0.2)
        grupo = VGroup(cabeza, VGroup(caja, eq)).arrange(DOWN, buff=0.32)
        grupo.move_to([0, (self.tope_pasos + c.Y_ZONA_INFERIOR) / 2 + 0.3, 0])

        salen: list[Mobject] = [*self.resaltes]
        for linea in self.pila:
            salen += [m for m in linea if m is not self.ultima]
        with self.hablar(r.voz, "resultado"):
            mapa = c.coincidencias(self.ultima, eq) if self.ultima is not None else None
            if mapa is not None:
                aparecer = [TransformMatchingTex(self.ultima, eq, key_map=mapa)]
            else:
                aparecer = [Write(eq)] + ([FadeOut(self.ultima)] if self.ultima is not None else [])
            self._con_pendientes(*[FadeOut(m) for m in salen], *aparecer, run_time=0.9)
            self.play(FadeIn(caja), Create(cabeza[0]), FadeIn(cabeza[1], shift=UP * 0.1), run_time=0.5)
            self.play(
                Circumscribe(VGroup(caja, eq), color=self.col.acento, fade_out=True, time_width=0.5),
                run_time=1.0,
            )
        self.bloque_resultado = VGroup(cabeza, caja, eq)

    def _verificacion(self) -> None:
        v = self.guion.verificacion
        etiqueta = c.texto("¿TIENE SENTIDO?", c.TAM_ETIQUETA, ULTRABOLD, self.color_materia)
        cuerpo = c.parrafo(v.texto, 30, MEDIUM, self.col.texto, ancho_max=c.ANCHO_UTIL - 0.3)
        bloque = VGroup(etiqueta, cuerpo).arrange(DOWN, buff=0.2)
        bloque.next_to(self.bloque_resultado, DOWN, buff=0.55)
        subir = max(0.0, c.Y_ZONA_INFERIOR - bloque.get_bottom()[1])
        with self.hablar(v.voz_final, "verificación"):
            animaciones = [FadeIn(bloque.shift(UP * subir), shift=UP * 0.15)]
            if subir:
                animaciones.append(self.bloque_resultado.animate.shift(UP * subir))
            self.play(*animaciones, run_time=0.5)

    def _limpiar_tablero(self) -> list[Animation]:
        """FadeOut de todo menos el fondo y la cabecera.

        Un solo FadeOut sobre un grupo: en Manim, agregar un grupo a la escena "absorbe" a
        sus hijos, así todo sale junto aunque haya objetos anidados (con varios FadeOut
        sueltos, un objeto podía reaparecer al terminar la animación)."""
        quedan = {id(self.fondo), id(self.cabecera)}
        salen = [m for m in self.mobjects if id(m) not in quedan]
        return [FadeOut(Group(*salen))] if salen else []  # Group: la escena puede tener no-vectoriales

    def _reto(self) -> None:
        reto = self.guion.reto
        etiqueta = c.texto("AHORA TÚ", 26, HEAVY, self.col.acento)
        cuerpo = c.parrafo(
            reto.texto,
            c.TAM_CUERPO,
            SEMIBOLD,
            self.col.texto,
            ancho_max=c.ANCHO_UTIL - 0.8,
            alineacion="left",
        )
        pie = c.texto("Responde en los comentarios", 22, MEDIUM, self.col.tenue)
        contenido = VGroup(etiqueta, cuerpo, pie).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        tarjeta = c.tarjeta(contenido, c.ANCHO_UTIL, self.col.panel, self.color_materia)
        tarjeta.move_to([0, c.CENTRO_ZONA + 0.8, 0])
        with self.hablar(reto.voz_final, "reto"):
            self.play(*self._limpiar_tablero(), run_time=0.35)  # primero despejar, sin superponer
            self.play(FadeIn(tarjeta, shift=UP * 0.2), run_time=0.45)

    def _cierre(self) -> None:
        cierre = self.guion.cierre or Bloque(texto=self.marca.cierre.texto, voz=self.marca.cierre.voz)
        engranaje = c.engranaje(0.85, self.col.acento, self.col.fondo, dientes=12)
        nombre = c.texto(self.marca.nombre.upper(), 40, HEAVY, self.col.texto)
        usuario = c.texto(self.marca.usuario, 28, SEMIBOLD, self.col.acento)
        llamado = c.parrafo(cierre.texto, 30, SEMIBOLD, self.col.texto)
        grupo = VGroup(engranaje, nombre, usuario, llamado).arrange(DOWN, buff=0.38)
        grupo.move_to([0, c.CENTRO_ZONA + 0.7, 0])
        with self.hablar(cierre.voz_final, "cierre") as tr:
            self.play(*self._limpiar_tablero(), run_time=0.35)
            self.play(FadeIn(engranaje, scale=0.5), run_time=0.4)
            self.play(
                Rotate(engranaje, angle=PI / 3),
                FadeIn(nombre, shift=UP * 0.2),
                FadeIn(usuario),
                FadeIn(llamado, shift=UP * 0.1),
                run_time=0.8,
            )
            resto = self._restante(tr)
            if resto > 0.1:
                self.play(Rotate(engranaje, angle=PI / 2, rate_func=lambda t: t), run_time=resto)
        self.wait(0.6)

    def _guardar_linea_de_tiempo(self) -> None:
        datos = {
            "titulo": self.guion.titulo,
            "duracion_total": round(float(self.renderer.time), 3),
            "ancho": config.pixel_width,
            "alto": config.pixel_height,
            "fps": config.frame_rate,
            "bloques": self.bloques_voz,
        }
        self.op.linea_de_tiempo.parent.mkdir(parents=True, exist_ok=True)
        self.op.linea_de_tiempo.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
