# Contenido demostrativo — Plan de implementación para Kiro

> **Para Kiro:** ejecuta las tareas en orden en tu sesión principal, sin subagente implementador. Aplica TDD y revisión por tarea. `superpowers:executing-plans` es la ruta prevista si está disponible; no instales herramientas para seguir este documento. Lee el diseño asociado antes de escribir código. Las casillas solo se marcan con evidencia.

**Goal:** permitir dato, mito, error y ejercicio con una explicación visual coherente y herramientas independientes de la apariencia, preservando los videos antiguos.

**Architecture:** conservar Guion y su secuencia de bloques; introducir contenido opcional y conclusión textual sin cálculo ficticio. Componer una copia de Tema con recursos por guion; integrar esa copia en escena, subtítulos y gancho. Reutilizar redactor, ideas, procesos y QC existentes.

**Tech Stack:** Python 3.11+ (Mac actual: 3.12), Pydantic v2, Manim Community `>=0.22,<0.23`, NiceGUI, unittest, voz sintética existente, FFmpeg, LaTeX y PyAV ya instalados.

**Spec:** [Diseño de contenido demostrativo](../specs/2026-11-12-contenido-demostrativo-design.md).

## Global Constraints

- Runner: `.venv/bin/python -m unittest discover -s pruebas -t . -v`. NO usar pytest.
- Solo Python. Panel NiceGUI: sin JavaScript ni HTML propios, sin Node ni npm; escuchar solo en `127.0.0.1`.
- Opt-in: NO cambiar `TEMA_POR_DEFECTO`, ni `mis_ajustes/marca.yaml`, ni el `tema:` de ningún guion existente.
- No crear ni modificar YAML incluidos de `src/tpi_videos/plantillas/temas/` para esta función. No borrar estilos ni agruparlos como sustituto de la innovación.
- Todo campo nuevo del guion o del tema es opcional. Sin campos nuevos, el comportamiento y los cuadros antiguos son idénticos.
- La apariencia se resuelve solo mediante `temas.resolver_tema`; su único selector de panel sigue en la ficha de Aprobación de Guiones (QC). Estudio es la pantalla principal, pero no añade un segundo selector de apariencia.
- La familia Consola neón (cinco variantes) sigue siendo el catálogo de apariencias: no reemplazarla ni resucitar los 20 estilos archivados como catálogo. Los archivados siguen cargando por nombre (`plantillas/temas/archivo/`) y sirven solo como prueba de regresión de capacidad.
- `PasoIA.mapa` ya existe (`redactor.py:126`, `list[MapaIA]` con validador `_mapa`): reutilizarlo, no incorporar un segundo formato de mapas.
- Lo que personaliza el usuario va en `mis_ajustes/` o en su guion; las pruebas usan TPI_RAIZ temporal. No escribir en originales durante QA.
- No usar subagente implementador. Una revisión independiente puede ser solo lectura; si no existe, declarar la limitación.
- No imprimir ni subir `.env`, claves, videos/audio, ajustes personales, salidas, capturas o temporales.
- No comprimir tiempo físico, inventar estadísticas/fuentes, rellenar duración con escenas inmóviles ni prometer viralidad.
- Niveles y carreras siguen en `niveles.py`; malla sigue en sus YAML existentes. Materia, dificultad, molde e intención no son sinónimos.
- La herencia de voz/velocidad/tono/tema de «Solo el gancho» ya está en main (`5a10033`, PR #42). La rama antigua `fix/gancho-hereda-ajustes` (`449e48f`) es redundante: no fusionarla ni borrarla sin autorización, y no reimplementar ese comportamiento.
- Este documento reemplaza la agrupación de estilos de prioridad 6 en `2026-11-11-auditoria-prioridades*`; no ejecutar esas tareas antiguas. No interviene en prioridades 7/8.
- Antes del código UI, mostrar un mock en el chat y obtener aprobación visual. No interpretar el encargo del plan como un «dale» al mock.
- Commits y PR de la implementación requieren la autorización aplicable de su sesión. Nunca push directo a main, amend, force, cambios de git config ni omisión de hooks.

## Base, alcance y lectura inicial

Repositorio: `/Users/documentos/Downloads/tuprofeindustrial-videos`.
Base verificada al diseñar: main `889f618` (merge del PR #51, Estudio de una pantalla). La corrección de «Solo el gancho» ya está en main (`5a10033`, PR #42); la rama `fix/gancho-hereda-ajustes` (`449e48f`) es redundante. Las líneas de la tabla son de `889f618`; volver a localizarlas por símbolo si se desplazan.

- [ ] Leer `.kiro/steering/reglas-del-repo.md` y revisar `git status --short --branch`, `git log -5 --oneline`, `git branch -a`.
- [ ] Elegir una rama de implementación nueva desde main actualizado (que ya incluye la herencia de gancho); si se requiere integración a main, solicitarla, no hacerla implícitamente. No sobreescribir trabajo ajeno ni copiar archivos completos desde una rama anterior.
- [ ] Ejecutar la suite completa y registrar el resultado de base. Si falla, separar fallos anteriores de los nuevos antes de avanzar.
- [ ] Leer completos los métodos enumerados en la tabla siguiente. Las líneas son pistas verificadas a fecha del diseño, no anclas permanentes.

| Unidad | Archivo y símbolo actual (base 889f618) | Responsabilidad |
| --- | --- | --- |
| Esquema/guardado | `guion.py:1158` Resultado; `1205` Guion; `1729` a_yaml; `1227` llamado | Nuevos campos, validación semántica y round-trip. |
| Edición | `panel/editor.py:142` a_formulario; `172` desde_formulario; `559` guardar | Conservar campos, false y comentarios. |
| Recursos | `temas.py:233` Gramatica, `248` Layout, `263` Tema; nuevo `didactica.py` | Decisiones razonadas y composición sin mutación. |
| Escena | `escena.py:490` gramatica_de; `1410` paso solo hablado; `1674` _resultado; `1845` timeline | Recursos existentes y conclusión visible. |
| Video | `render.py:165` subtitulos_de; `173` crear_video (`202` estilo_video); `341` crear_clip_gancho (`354` estilo) | Misma composición en todas las rutas. |
| IA | `redactor.py:64` PasoIA (`126` mapa ya existe); `426` GuionIA; `1197` a_guion; `1545` redactar | Salida educativa fija y revisión completa. |
| Ideas/producción | `ideas.py:94` Idea; `288` producir; `lote.py:591` llamada a producir | Contexto persistente, manual sobre IA, reintentos. |
| Procesos | `cli.py:387` cmd_redactar; `448` _producir; `591` cmd_ideas; `989` _idea_de_guion; `806` _producir_desde_ajustes | Transporte CLI/cola sin pérdida. |
| Cobertura curricular | `completar.py:83` _escribir; `93` redactar | Propagar la Idea sin tocar malla ni carreras. |
| Gancho | `ganchos.py:51` idea_desde_guion; `78` guion_de_vista_previa | Conservación de contenido y ajustes del guion base. |
| QC | `panel/qc.py:198` ficha; `244` cambiar_estilo; `43` huella | Mostrar intención/recursos y guardar de manera segura. |
| Estudio (pantalla principal) | `panel/paginas/estudio.py:82` Estudio; `panel/estudio.py:163` args_redactar | Pedir idea/nivel/tipo y transportar contenido; chips eligen molde. |
| Publicación | `publicar.py:158` aplicar_llamado; `246` crear_kit | Copy por contenido; respetar llamado del guion. |
| Plantillas | `src/tpi_videos/plantillas/ia/{sistema,revisor,ideas,publicar}.md` | Instrucciones reales; no existe `ia/redactor.md` ni `fabrica.py`. |

Todos los paths abreviados de código pertenecen a `src/tpi_videos/`.

## Entregables por tarea

1. Contrato de contenido/conclusión y guardado fiel.
2. Recursos razonados y composición sin modificar estilos.
3. Conclusión textual y composición efectiva en video/gancho.
4. IA que entiende contenido educativo, no solamente ejercicios.
5. Contexto conservado en ideas, procesos, lotes y reintentos.
6. Persistencia segura y ficha QC independiente de NiceGUI.
7. Tarjetas y edición en el panel existente, previa aprobación del mock.
8. Cuatro demostraciones reales y regresión de los videos antiguos.
9. Documentación y entrega verificadas, sin archivos privados.

Cada tarea tiene un producto comprobable. No ejecutar varias implementaciones antes de su prueba roja.

---

## Tarea 1 — Contrato y round-trip sin ejercicios de relleno

**Files:** modificar `src/tpi_videos/guion.py`, `src/tpi_videos/panel/editor.py`; crear `pruebas/datos_didacticos.py`, `pruebas/test_contenido_guion.py`.

**Consumes:** `_Base`, Resultado, Guion, a_yaml, a_formulario, desde_formulario.
**Produces:** `Contenido`, `RecursosDidacticos`, `Guion.contenido`, `Guion.recursos`, `Resultado.texto`, `Resultado.tex` opcional semánticamente; mismos nombres de bloques y voces.

### Paso 1: fixture y prueba roja

- [ ] Crear este helper de prueba, sin importar modelos nuevos todavía:

```python
from copy import deepcopy


def datos_base():
    return {
        "titulo": "Compara dos valores", "materia": "matematica",
        "gancho": {"texto": "¿Cambian de la misma manera?", "voz": "¿Cambian de la misma manera?"},
        "enunciado": {"texto": "Compara el doble de una longitud con el volumen del cubo."},
        "pasos": [
            {"voz": "Primero toma una arista.", "tex": "a = 1"},
            {"voz": "Después duplica la arista.", "tex": "a = 2"},
        ],
        "resultado": {"tex": "V = 8", "voz": "El volumen es ocho."},
    }


def datos_concepto():
    datos = deepcopy(datos_base())
    datos["contenido"] = {
        "intenciones": ["dato"],
        "objetivo": "Distinguir longitud y volumen sin confundir sus escalas.",
    }
    datos["recursos"] = {"panel": False, "micro": None}
    datos["resultado"] = {
        "texto": "Longitud y volumen crecen de distinta manera.",
        "voz": "La longitud y el volumen no crecen de la misma manera.",
    }
    return datos
```

- [ ] Añadir estas pruebas ejecutables en `pruebas/test_contenido_guion.py`:

```python
import unittest
import yaml
from pydantic import ValidationError
from tpi_videos.guion import Guion, a_yaml
from tpi_videos.panel.editor import a_formulario, desde_formulario
from pruebas.datos_didacticos import datos_base, datos_concepto


class ContenidoGuionTest(unittest.TestCase):
    def test_conclusion_textual_sin_formula_round_trip(self):
        g = Guion.model_validate(datos_concepto())
        texto = a_yaml(g.model_dump(exclude_none=True), ["Comentario del dueño"])
        leido = Guion.model_validate(yaml.safe_load(texto))
        self.assertEqual(g, leido)
        self.assertIn("# Comentario del dueño", texto)
        self.assertFalse(leido.recursos.panel)
        self.assertIsNone(leido.recursos.micro)
        self.assertNotIn("micro:", texto)
        self.assertEqual(leido.resultado.tex, "")

    def test_ejercicio_heredado_sigue_exigiendo_formula(self):
        datos = datos_base()
        datos["resultado"].pop("tex")
        with self.assertRaises(ValidationError):
            Guion.model_validate(datos)

    def test_formulario_conserva_false_y_conclusion(self):
        g = Guion.model_validate(datos_concepto())
        vuelto = Guion.model_validate(desde_formulario(a_formulario(g)))
        self.assertEqual(g, vuelto)
```

- [ ] Ejecutar `.venv/bin/python -m unittest pruebas.test_contenido_guion -v`. La primera/tercera deben fallar por campos no admitidos o fórmula obligatoria; no por imports o sintaxis.

### Paso 2: implementación mínima

- [ ] Añadir modelos con este contrato exacto; incorporar imports al grupo existente:

```python
class Contenido(_Base):
    intenciones: list[Literal["dato", "mito", "error", "ejercicio"]] = Field(min_length=1, max_length=4)
    objetivo: str = Field(min_length=1, max_length=260)

    @field_validator("intenciones")
    @classmethod
    def _sin_repetir(cls, valor):
        if len(valor) != len(set(valor)):
            raise ValueError("No repitas intenciones del contenido.")
        return valor

    @field_validator("objetivo")
    @classmethod
    def _objetivo_con_texto(cls, valor):
        if not valor.strip():
            raise ValueError("El objetivo necesita texto.")
        return valor


class RecursosDidacticos(_Base):
    tabs: StrictBool | None = None
    panel: StrictBool | None = None
    mapa_color: StrictBool | None = None
    micro: StrictBool | None = None
```

- [ ] Añadir los dos campos opcionales a Guion y `texto` opcional a Resultado. `tex` usa `str = ""`: no reemplazar un vacío por None mediante su validador; validar el LaTeX cuando está presente. Conservar voz, pausa, emoji y destello actuales.
- [ ] Añadir un validador after de Guion con esta decisión, sin duplicarlo en el writer:

```python
intenciones = self.contenido.intenciones if self.contenido else ["ejercicio"]
if "ejercicio" in intenciones and not self.resultado.tex.strip():
    raise ValueError("Un ejercicio necesita la fórmula final en resultado.tex.")
if not (self.resultado.tex.strip() or (self.resultado.texto or "").strip()):
    raise ValueError("El resultado necesita una fórmula o una conclusión visible.")
```

- [ ] En a_yaml, escribir contenido/recursos solo cuando existen; serializar sus diccionarios con `yaml.safe_dump(..., allow_unicode=True, sort_keys=False)` y sangría de dos espacios. Filtrar únicamente None, no valores falsos. Escribir `resultado.texto` cuando exista y `resultado.tex` solo si no está vacío; mantener el orden/formato de guiones antiguos y preservar `llamado` (`guion.py:1227`) en el round-trip.
- [ ] Extender VACIO/formulario para texto de resultado y contenido/recursos; no limpiar False. La función `_limpio` actual no debe sustituirse por un filtro de truthiness. Un editor antiguo abre/guarda los campos nuevos aunque no haya nuevos controles todavía.
- [ ] No crear un camino nuevo para pasos sin fórmula: `escena.py:1410` (`if paso.tex is None:`) ya dibuja el paso solo hablado. El contrato de contenido solo habilita la conclusión textual y la intención; la escena de pasos sin tex ya existe.

### Paso 3: verde y límites

- [ ] Añadir y observar fallar antes de corregir: intención desconocida, lista vacía/duplicada, objetivo en blanco, `panel: "false"`, ejercicio combinado sin fórmula y conclusión solo espacios. Verificar que los modelos antiguos siguen cargando.
- [ ] Ejecutar `.venv/bin/python -m unittest pruebas.test_contenido_guion pruebas.test_ganchos pruebas.test_editor_visual pruebas.test_guion_moldes pruebas.test_mapa_guion -v`.
- [ ] Revisar diff, documentar comandos/resultados. Commit específico solo si está autorizado; no declarar todavía render conceptual completo.

## Tarea 2 — Herramientas por guion, con razones y sin mutación

**Files:** crear `src/tpi_videos/didactica.py`, `pruebas/test_recursos_didacticos.py`. No editar los YAML de temas.

**Consumes:** Contenido, RecursosDidacticos, Guion, Tema/Gramatica/Layout.
**Produces:** dataclass `RecursoDidactico(clave, activo, sugerido, razon, origen)`; `recursos_del_guion(guion: Guion, tema: Tema) -> list[RecursoDidactico]`; `componer_tema(tema: Tema, guion: Guion) -> Tema`.

### Paso 1: roja

- [ ] Escribir pruebas de los nuevos imports y ejecutarlas; después de resolver imports, comprobar fallos de conducta, no aceptar solo ImportError como ciclo terminado:

```python
import unittest
from tpi_videos.guion import Guion
from tpi_videos.temas import Tema
from tpi_videos.didactica import componer_tema, recursos_del_guion
from pruebas.datos_didacticos import datos_base, datos_concepto


class RecursosTest(unittest.TestCase):
    def test_heredado_conserva_tema_entero(self):
        tema = Tema(nombre="Original", gramatica={"panel": True, "micro": True})
        antes = tema.model_dump()
        copia = componer_tema(tema, Guion.model_validate(datos_base()))
        self.assertEqual(copia.model_dump(), antes)
        self.assertEqual(tema.model_dump(), antes)
        self.assertIsNot(copia, tema)

    def test_false_manda_sobre_sugerencia_y_no_contamina_otro_video(self):
        tema = Tema(nombre="Hoja", marco="hoja")
        g = Guion.model_validate(datos_concepto())
        decisiones = {d.clave: d for d in recursos_del_guion(g, tema)}
        self.assertTrue(decisiones["panel"].sugerido)
        self.assertFalse(decisiones["panel"].activo)
        self.assertEqual(decisiones["panel"].origen, "guion")
        self.assertIn("fórmulas", decisiones["panel"].razon)
        self.assertFalse(componer_tema(tema, g).gramatica.panel)
        self.assertEqual(tema, Tema(nombre="Hoja", marco="hoja"))
```

- [ ] Ejecutar `.venv/bin/python -m unittest pruebas.test_recursos_didacticos -v`.

### Paso 2: decisión y composición

- [ ] Implementar sin Manim ni NiceGUI. Orden fijo `("tabs", "panel", "mapa_color", "micro")`; dataclass frozen. Reglas de sugerencia exactamente como en la sección 5 del diseño: nacen de la estructura real del guion, NO de la variante de Consola (un `mito + ejercicio` con fórmulas recibe panel aunque su variante sea `consola_mito`). Contar únicamente pasos correctos con tex para el panel.
- [ ] Resolver cada bandera así:

```python
base = getattr(tema.gramatica, clave)
sugerido = recomendaciones[clave][0] if guion.contenido else base
manual = getattr(guion.recursos, clave) if guion.recursos else None
activo = sugerido if manual is None else manual
origen = "guion" if manual is not None else ("contenido" if guion.contenido else "tema")
```

- [ ] Componer con `tema.model_copy(deep=True)`, aplicar las cuatro banderas; ninguna escritura. Si no hay contenido ni override no-null, retornar copia idéntica con layout intacto. Tampoco recalcular geometry si banderas finales y base coinciden.
- [ ] Para panel recién activado, banda `copia.layout.banda_panel or 1.6`; límite inferior inicial `max(y_actual, -2.2)`, donde y_actual viene del layout o -3.55 para hoja/-2.4 para pizarra (pisos reales en `componentes._ZONAS`, `componentes.py:139`). No importar componentes para estos valores ni modificar `_ZONAS`; validar su suficiencia en tarea 3/8.
- [ ] Si panel se apaga, no desplazar subtítulos por una banda de panel solo porque el tema base la tenía. `subtitulos_de` comprueba la bandera efectiva.

### Paso 3: verde y combinaciones

- [ ] Agregar ciclos roja-verde: tres pasos activan tabs; dos fórmulas y un error resumen solo correctas; paso.mapa verdadero sugiere color; micro no altera camara; null hereda; recursos explícitos sin contenido heredan el tema excepto override; tema propio conserva paleta/imagen/fuentes; composición repetida no acumula offsets.
- [ ] Ejecutar `.venv/bin/python -m unittest pruebas.test_recursos_didacticos pruebas.test_gramatica_tema pruebas.test_estilo_sugerido pruebas.test_layout_del_tema -v`.
- [ ] Revisión de diff y commit autorizado específico.

## Tarea 3 — Conclusión textual y una sola composición efectiva

**Files:** modificar `src/tpi_videos/escena.py`, `render.py`, `redactor.py` (solo errores_latex), `revision.py`; crear `pruebas/test_render_didactico.py`; extender `pruebas/test_escena_gramatica.py`.

**Consumes:** componer_tema, Resultado.texto; gramatica_de, _resultado y subtitulos_de existentes.
**Produces:** render conceptual sin fórmula falsa, video/gancho/subtítulos con mismo Tema; metadatos de decisiones verificables.

### Paso 1: prueba roja real de componente

- [ ] Usar el patrón de `PersistenciaEnEscenaTest` (tempconfig, TemporaryDirectory, ContextVar). Añadir helper de producción pequeño `componente_resultado(guion: Guion, tema: Tema) -> Mobject` en escena.py, consumido solo por la nueva rama de resultado. Crear la prueba antes del helper:

```python
import unittest
from manim import tempconfig
from tpi_videos.guion import Guion
from tpi_videos.temas import Tema
from tpi_videos.escena import componente_resultado
from pruebas.datos_didacticos import datos_concepto


class ResultadoTextualTest(unittest.TestCase):
    def test_conclusion_es_texto_visible_y_cabe(self):
        g = Guion.model_validate(datos_concepto())
        tema = Tema(nombre="Concepto")
        with tempconfig({"frame_width": 9, "frame_height": 16}):
            objeto = componente_resultado(g, tema)
        self.assertGreater(objeto.width, 0)
        self.assertLessEqual(objeto.width, 7.6)
        textos = [getattr(m, "text", "") for m in objeto.get_family()]
        self.assertIn(g.resultado.texto, textos)
        self.assertFalse(any(getattr(m, "tex_string", "") for m in objeto.get_family()))
```

- [ ] Ejecutar `.venv/bin/python -m unittest pruebas.test_render_didactico -v`; después de imports, comprobar texto ausente/dimensión incorrecta antes de terminar el ciclo rojo.

### Paso 2: implementación

- [ ] En crear_video y crear_clip_gancho conservar `resolver_tema` y `cargar_tema`, y componer inmediatamente:

```python
tema_usado = resolver_tema(tema, guion, marca)
estilo_video = componer_tema(cargar_tema(tema_usado, marca), guion)
```

En clip, argumento manual sigue None y nombre local `estilo`; no cambiar voz/velocidad/tono ni piso=0. Usar el objeto compuesto también en subtítulos, recodificación/resplandor, fondo y resultado. No componer de nuevo dentro de escena.

- [ ] Con `resultado.texto` nuevo, construir título «CONCLUSIÓN», párrafo mediante c.parrafo, tarjeta/emoji y grupo que quede en `self.bloque_resultado`. Si también hay tex, mostrar fórmula y texto separado como interpretación. Mantener voz registrada con sección `resultado`, pendientes, cámara y piso de lectura; no transformar Text con TransformMatchingTex. Sacar pila/resaltes de manera equivalente a la rama vieja.
- [ ] Si no hay texto de resultado, mantener `_resultado` antiguo idéntico; no refactorizar animaciones antiguas. El helper configura/restaura ContextVar por try/finally y devuelve cuerpo visible, no solo etiqueta.
- [ ] En errores_latex (`redactor.py:1337`) compilar resultado solo si tex no vacío. En revisión de unidades (`revision.py:303-308`, hoy lee `guion.resultado.tex` sin condición), exigir fórmula antes del aviso; no preguntar por unidades de una oración conceptual. Incluir resultado.texto en revisión de legibilidad/emoji sin modificar avisos de ejercicios antiguos.
- [ ] En `_guardar_linea_de_tiempo`, solo para contenido/override explícito, agregar `contenido` y `recursos_didacticos` (lista de dataclass serializadas, activo/origen/motivo). El mismo contrato en gancho. `tema_clave` conserva la clave base; no guardar una clave inventada para cada combinación.

### Paso 3: geometría y rutas

- [ ] Añadir prueba de render de un paso solo hablado (`tex` ausente) que confirme que la rama existente `escena.py:1410` lo dibuja sin fórmula y sin romper la secuencia de voz; no crear un camino nuevo.
- [ ] Añadir pruebas de escena hoja+panel: ancho útil, resumen <= banda_panel, tabs fuera del desarrollo, resultado textual completo, relación fija con cámara. Proyectar objetos a coordenadas de pantalla con `(p-centro_camera)/ancho_camera*9`; separación >=0.3 frente a las bandas de subtítulos/resumen. Incluir dos líneas de subtítulos y 30 pasos. No asumir que una prueba de pizarra garantiza la hoja.
- [ ] Si el límite inicial -2.2 no basta, escribir primero prueba con el solapamiento medido; ajustar solo el layout de composición explícita, no globales ni YAML incluidos. Mantener además una prueba exacta de layout heredado.
- [ ] Test de crear_video con mocks únicamente para FFmpeg/render externo devuelve un archivo de timeline temporal; comprobar el Tema recibido por render y por subtítulos (banderas/layout), y que el Tema base cargado no se mutó. Repetir en crear_clip_gancho y verificar voz/tono/velocidad reales que llegan a renderizar_manim.
- [ ] Ejecutar `.venv/bin/python -m unittest pruebas.test_render_didactico pruebas.test_escena_gramatica pruebas.test_render_gancho pruebas.test_cli_ganchos pruebas.test_revision_movimiento -v`.
- [ ] Render silencioso conceptual completo bajo TPI_RAIZ temporal y comprobar resultado/registro; su reproducción final forma parte de tarea 8. Revisión y commit autorizado específico.

## Tarea 4 — IA educativa: clasificar, explicar y revisar

**Files:** modificar `src/tpi_videos/redactor.py`, `src/tpi_videos/plantillas/ia/sistema.md`, `revisor.md`, `pruebas/ia_falsa.py`; localizar y actualizar todas las instancias `es_ejercicio` y el servidor `scripts/gemini_falso.py`; crear `pruebas/test_redactor_contenido.py`.

**Consumes:** Contenido, MapaColor, Guion completo; redactor.pedir_json y rondas existentes; `PasoIA.mapa` que YA existe (`redactor.py:126`).
**Produces:** GuionIA.es_contenido_educativo, GuionIA.contenido opcional, resultado_texto opcional, resultado_tex con default `""`; `redactar(..., contenido: Contenido | None = None)` añadido al final. No se añade un segundo formato de mapas.

### Paso 1: prueba roja offline

- [ ] Crear una respuesta conceptual usando `EJEMPLO.model_dump()`: eliminar `es_ejercicio`, añadir `es_contenido_educativo=True`, contenido dato/objetivo, `resultado_tex=""`, `resultado_texto` con conclusión, voz en palabras. Mantener campos restantes válidos. No utilizar model_copy para saltarse validación del esquema.
- [ ] Test sobre el YAML real, no sobre el número de llamadas de un mock:

```python
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from tpi_videos import redactor
from tpi_videos.guion import cargar_guion


class RedactorContenidoTest(unittest.TestCase):
    def test_dato_educativo_se_escribe_y_se_relee(self):
        d = redactor.EJEMPLO.model_dump()
        d.pop("es_ejercicio", None)
        d["es_contenido_educativo"] = True
        d["contenido"] = {"intenciones": ["dato"], "objetivo": "Explicar la gravedad sin pedir un cálculo."}
        d["resultado_tex"] = ""
        d["resultado_texto"] = "La gravedad acelera la caída."
        respuesta = redactor.GuionIA.model_validate(d)
        revision = redactor.RevisionIA(aprobado=True, problemas=[])
        with TemporaryDirectory() as carpeta, patch.dict(os.environ, {"TPI_RAIZ": carpeta}):
            (Path(carpeta) / "guiones").mkdir()
            with patch("tpi_videos.ia.cliente", return_value=object()), \
                 patch.object(redactor, "pedir_json", side_effect=[respuesta, revision]), \
                 patch.object(redactor, "errores_latex", return_value=[]):
                resultado = redactor.redactar("Explica qué hace la gravedad durante una caída.")
            g = cargar_guion(resultado.ruta)
            self.assertEqual(g.contenido.intenciones, ["dato"])
            self.assertEqual(g.resultado.texto, "La gravedad acelera la caída.")
            self.assertEqual(g.resultado.tex, "")
```

- [ ] Ejecutar `.venv/bin/python -m unittest pruebas.test_redactor_contenido -v`. Primero observar rechazo del campo/clasificación; después, con esquema definido, observar el rechazo no-ejercicio si persiste.

### Paso 2: esquema y redacción

- [ ] Reemplazar `es_ejercicio` por `es_contenido_educativo` en esquema, fixtures, ejemplos, clasificación y todas sus referencias: `redactor.py` (427, 428, 477, 555, 635, 711, 1618), `pruebas/ia_falsa.py` (16, 89) y `scripts/gemini_falso.py` (reutiliza `respuesta` de ia_falsa); no añadir alias. El campo clasifica relevancia STEM y suficiencia, no si hay incógnita.
- [ ] Añadir resultado_texto vacío por defecto y resultado_tex vacío por defecto (`redactor.py:454`) en GuionIA; Contenido opcional compartido. `PasoIA.mapa` YA existe como `list[MapaIA]` (`redactor.py:126`) con el validador `_mapa` (`redactor.py:927`): reutilizarlo, a_guion lo serializa y deja al validador real de Paso comprobar términos presentes. No inventar mapas desde cualquier palabra de la voz ni crear un segundo formato.
- [ ] En a_guion (`redactor.py:1197`) conservar contenido y conclusión: omitir el `tex` de paso cuando quede vacío (hoy lo escribe siempre, línea 1203) y serializar `resultado.texto` cuando exista (hoy solo `tex`/`voz`, línea 1237). En redactar aplicar el contenido manual después de a_guion y antes de Guion.model_validate, en cada ronda. Continuar rechazando `es_contenido_educativo=False` con ErrorMotor en español («No hay contenido educativo suficiente para redactar…»). Un override no debe saltarse esa clasificación.
- [ ] Actualizar las instrucciones de sistema y revisión como sigue; conservar las reglas existentes de voz, unidades, dibujos y seguridad:

```text
La intención educativa puede ser dato, mito, error, ejercicio o una combinación.
Primero declara qué aprenderá la persona. Usa el enunciado como premisa/contexto.
Dato: observación concreta, evidencia visual e interpretación.
Mito: afirmación identificable, contraste honesto y explicación del porqué.
Error: forma equivocada real, por qué falla, corrección y comprobación.
Ejercicio: datos suficientes, pasos deducibles y respuesta matemática completa.
Los pasos pueden ser demostraciones visuales con tex vacío cuando no calculan.
Para contenido sin ejercicio, resultado_texto puede cerrar sin resultado_tex.
No inventes números, historia, fuentes ni experimentos. Explicita los supuestos.
Cada dibujo o cambio debe demostrar la frase que se dice, no adornar el fondo.
El tiempo sigue la explicación y el movimiento físico; no rellenes con pausas.
```

- [ ] Sustituir restricciones contradictorias sobre el texto actual de `sistema.md`: el rechazo «si no es ejercicio, rechaza» (línea 14), «cada paso es UNA ecuación completa… Entre 2 y 6 pasos» (línea 21), «Máximo UN dibujo» (líneas 32 y 80, hoy solo prompt sin validador en código), «siempre #ejerciciosresueltos» (línea 136) y la voz universal «de 150 a 260 palabras» (línea 104). Conservar la pedagogía XCris, `idea_central`/`confusion_tipica`, el dibujo `escala` (línea 50) y el `mapa` (línea 71). Para ejercicio conservar cálculo paso a paso y el límite de UN dibujo; para concepto permitir más de un ejemplo visual secuencial de tipos ya admitidos. Sin promesa explícita conservar sugerencia de duración, nunca un tope universal. No cambiar validadores físicos ni añadir bait a la voz.
- [ ] Revisor docente comprueba afirmación, evidencia, porqué y fidelidad del dibujo, además de matemática cuando exista. No desactivar revisión de no-ejercicios ni aprobar por tener etiqueta «dato». Si faltan fuentes externas, dejar observación para QC; no simular consulta web.

### Paso 3: verde y rechazo

- [ ] Añadir ciclos roja-verde para entrada fuera de STEM, insuficiente, manual mito que vence dato inferido, ejercicio sin resultado rechazado, mapa inventado rechazado, revisor que pide una corrección y contenido manual conservado en ronda 2. La red real y LaTeX son fronteras que pueden falsearse; Guion, a_yaml, formato y salida no.
- [ ] El fixture anterior puede generar avisos de formato reales según la base: corregir su contenido sin falsear problemas_de_formato; no añadir respuestas infinitas de IA para ocultar un fallo.
- [ ] Ejecutar `.venv/bin/python -m unittest pruebas.test_redactor_contenido pruebas.test_redactor_motor_vivo pruebas.test_redactor_variantes pruebas.test_rotacion_de_modelos pruebas.test_mapa_guion -v`.
- [ ] Ejecución con servidor Gemini falso existente y carga real del YAML desde CLI, sin clave. Registrar qué valida y qué NO (no prueba calidad factual de una IA real). Revisión y commit autorizado específico.

## Tarea 5 — Propagar intención sin perder elecciones ni reintentos

**Files:** modificar `src/tpi_videos/ideas.py`, `cli.py`, `lote.py`, `completar.py`, `ganchos.py`, `src/tpi_videos/plantillas/ia/ideas.md`, `publicar.py` y `plantillas/ia/publicar.md`; crear `pruebas/test_contenido_flujos.py`; extender `pruebas/ia_falsa.py` y tests existentes de ideas/lote/kit.

**Consumes:** Contenido, redactar(..., contenido=None), Idea y producir existentes.
**Produces:** `Idea.contenido: Contenido | None = None`; `producir(..., contenido: Contenido | None = None)` al final; `--contenido-json` en redactar/producir/ideas; contenido persistente en el JSON de Idea y su YAML.

### Paso 1: roja de persistencia

- [ ] Añadir prueba de Idea real sobre fixture existente, no un mock de Idea:

```python
import unittest
from tpi_videos.ideas import Idea
from tpi_videos.guion import Guion
from tpi_videos.cli import _idea_de_guion
from pruebas.test_ideas import idea
from pruebas.datos_didacticos import datos_concepto


class ContenidoFlujosTest(unittest.TestCase):
    def test_idea_json_retiene_intencion_y_objetivo(self):
        i = idea("Tangente", "pov", ["a", "b", "c"], contenido={
            "intenciones": ["dato"], "objetivo": "Interpretar la pendiente local."})
        self.assertEqual(Idea.model_validate_json(i.model_dump_json()).contenido, i.contenido)

    def test_guion_encolado_no_vuelve_a_paso_a_paso_por_etiqueta(self):
        g = Guion.model_validate(datos_concepto())
        i = _idea_de_guion(g)
        self.assertEqual(i.contenido, g.contenido)
```

- [ ] Ejecutar `.venv/bin/python -m unittest pruebas.test_contenido_flujos -v` y comprobar que falla por contenido perdido/no admitido.

### Paso 2: transporte exacto

- [ ] Idea añade contenido opcional (`ideas.py:94`); en generación nueva pedir siempre contenido y comprobarlo antes de aceptar PropuestaIA, sin invalidar JSON históricos. Su enunciado es premisa resoluble O afirmación explicable; reescribir la sección 2 de `plantillas/ia/ideas.md` (hoy «ejercicio COMPLETO y RESOLUBLE… 3 a 5 pasos… una sola fórmula protagónica») para admitir premisa/afirmación según el contenido. Mantener gancho/materia/dificultad/molde válidos y diversidad. No hacer que _limpiar rechace un concepto por no pedir cálculo.
- [ ] Propagar `contenido` en `ideas.producir -> redactar`, `cli._producir -> producir`, `cmd_ideas -> _producir`, `lote._producir_una -> producir` (`lote.py:591`), `completar._escribir -> redactar` (`completar.py:83`, `93`), `ganchos.idea_desde_guion` (`ganchos.py:51`), `guion_de_vista_previa` (`ganchos.py:78`) desde Idea y `cli._idea_de_guion` (`cli.py:989`, añadir `contenido=guion.contenido`). En la ruta con guion_base conservar model_copy y cambiar SOLO gancho como en la herencia ya presente en main. Convivir con `--molde`, `crear --kit` y `redibujar` ya existentes; no añadir un segundo proceso concurrente.
- [ ] CLI: usar `_json_de` existente para argumento literal o archivo y `Contenido.model_validate` en el borde. El contenido explícito del usuario gana; en su ausencia usar Idea.contenido; ausencia total conserva ejercicio heredado. No usar `or` para confundir un objeto inválido con «automático».
- [ ] Lote ya guarda Idea.model_dump: verificar antes de tocar cola.py; no introducir otra base de datos. Reanudar con hito YAML recarga su contenido y recursos y no vuelve a llamar a IA. Reanudar con hito video conserva metadatos del video ya hecho.
- [ ] Mantener título, ganchos elegidos, molde, materia, nivel, dificultad y segundos prometidos actuales. No agregar un selector de apariencia en crear.py o videos.py. La nueva Idea no elimina las selecciones existentes de voz.
- [ ] Publicar: respetar `Guion.llamado` (`guion.py:1227`) y `publicar.aplicar_llamado` (`publicar.py:158`); condicionar solo los nuevos contenidos a objetivo/premisa/conclusión. Conservar el fallback de ejercicios antiguos; evitar #ejerciciosresueltos/«lo resolviste» en un dato. No emitir certificación factual ni alta/publicación simulada. La invitación de pie no obliga a narrar CTA.

### Paso 3: regresión de recorridos

- [ ] Añadir pruebas reales de parser de `--contenido-json`, invalid JSON sin escritura, Idea a lote a archivo, reintento con IA fallando si se la invoca, manual sobre inferido, gancho con guion_base intacto, y kit de dato sin lenguaje de ejercicio. Usar TPI_RAIZ y límites falsos de IA/render externos; assert sobre YAML/JSON/kit producidos.
- [ ] Ejecutar `.venv/bin/python -m unittest pruebas.test_contenido_flujos pruebas.test_ideas pruebas.test_lote_cola pruebas.test_reintento_individual pruebas.test_completar pruebas.test_cli_ganchos pruebas.test_kit_resistente -v`.
- [ ] Revisión y commit autorizado específico.

## Tarea 6 — Ficha y guardado QC seguros, sin tocar la cola antigua

**Files:** modificar `src/tpi_videos/panel/qc.py`; crear `pruebas/test_qc_didactica.py`. Reutilizar el writer de guion y cabecera_de; no cambiar la política de cambiar_estilo.

**Consumes:** Contenido/RecursosDidacticos, recursos_del_guion/componer_tema, Guion/a_yaml/cabecera_de; qc.huella/estado.
**Produces:** `Ficha.contenido: Contenido | None`, `Ficha.recursos: list[RecursoDidactico]`; `cambiar_recursos(ruta: Path, recursos: RecursosDidacticos | None) -> Guion`. Campo lista con factory, no mutable compartido.

### Paso 1: roja de datos reales

- [ ] Usar ConRaiz de pruebas.test_tablero. Añadir este test; crear YAML conceptual con a_yaml al principio de la prueba:

```python
from pruebas.test_tablero import ConRaiz
from pruebas.datos_didacticos import datos_concepto
from tpi_videos.guion import RecursosDidacticos, a_yaml, cargar_guion
from tpi_videos.panel import qc


class QCDidacticaTest(ConRaiz):
    def test_cambio_real_invalida_aprobacion_y_no_borra_comentarios(self):
        self.guion.write_text(a_yaml(datos_concepto(), ["Decisión del dueño"]), encoding="utf-8")
        qc.aprobar(self.guion, "lote-antiguo")
        qc.cambiar_recursos(self.guion, RecursosDidacticos(panel=True, micro=False))
        g = cargar_guion(self.guion)
        self.assertTrue(g.recursos.panel)
        self.assertFalse(g.recursos.micro)
        self.assertEqual(qc.estado(self.guion), qc.POR_REVISAR)
        self.assertIn("# Decisión del dueño", self.guion.read_text(encoding="utf-8"))
        self.assertEqual(qc.decision(self.guion)["cola_id"], "lote-antiguo")
```

- [ ] Ejecutar `.venv/bin/python -m unittest pruebas.test_qc_didactica -v`; observar que no existe el setter o que cambia incorrectamente el estado, sin escribir originales.

### Paso 2: guardado transaccional acotado

- [ ] Validar guion_revisable primero; no aceptar ejemplos, fuera de guiones/, symlink externo ni un nombre proporcionado sin resolver. Modelo recursos validado en frontera. No exponer .env ni aplicar este cambio en bloque.
- [ ] Cargar original/Guion, generar dict nuevo con `model_dump(exclude_none=True)` y recursos normalizados. Si recursos no tiene ningún override no-null, tratarlo como None y quitar campo; comparar valores semánticos antes de escribir. No-op retorna Guion sin cambiar bytes/huella.
- [ ] Validar `Guion.model_validate` y generar a_yaml con cabecera_de ANTES de crear el reemplazo; preservar todos los campos, maps, ganchos, contenido, conclusión y comentarios de cabecera. Escribir NamedTemporaryFile en mismo directorio, flush y reemplazar con os.replace. Limpiar solo ese temporal propio si falla; dejar original intacto. No recalcular huella de qc.json: que estado detecte el cambio.
- [ ] Ficha obtiene tema base con resolver existente/cargar_tema, calcula decisiones y expone contenido. _tecnico incluye conclusión textual/recursos significativos sin falsos detalles. Un YAML inválido sigue rechazable/no aprobable.
- [ ] No modificar lote/hitos anteriores desde este setter. UI avisará «Afecta la próxima producción; el lote ya creado no cambia». Los recursos son parte de lo que se aprueba; cambiar_estilo conserva su comportamiento actual.

### Paso 3: verde y seguridad

- [ ] Probar no-op byte a byte mantiene APROBADO, revertir a sugerido elimina overrides, rutas externas no se escriben, fallo de os.replace deja original exacto, preserve voz/velocidad/tema/mapa/variantes y comentario, dos fichas no comparten lista. Comprobar razón y origen reales desde Ficha.
- [ ] Ejecutar `.venv/bin/python -m unittest pruebas.test_qc_didactica pruebas.test_tablero pruebas.test_cli_cola pruebas.test_reanudar_lote -v`.
- [ ] Revisión y commit autorizado específico.

## Tarea 7 — «Qué enseña» y «Herramientas» en Estudio y en la ficha QC

**Files:** modificar `src/tpi_videos/panel/paginas/estudio.py` (pantalla principal, PR #51), `panel/estudio.py` (`args_redactar:163`), `panel/paginas/tablero.py` (paridad en la ficha QC) y `panel/editor.py`; extender `pruebas/test_estudio.py` y tests de formato/sugerencia según el flujo usado. No crear pantalla, ruta, servidor ni selector de estilo nuevos.

**Consumes:** Ficha.contenido/recursos, cambiar_recursos, contenido-json y formulario de tarea 1; `estudio.args_redactar` y los chips de tipo existentes.
**Produces:** elecciones visibles/explicadas y transporte por TAREAS; estilo solo en QC. Los chips de tipo de Estudio siguen eligiendo MOLDE, no intención.

### Paso 1: mock y pruebas de interacción

- [ ] Mostrar mock IN CHAT de las tres tarjetas: Qué enseña, Herramientas de la explicación, Estilo del video, tal como aparecerán en «Revisa el guion» de Estudio y en la ficha QC. Un solo CTA principal «Aprobar y Enviar a Cola». Obtener aprobación antes de código UI. Si el dueño pide cambios, ajustar diseño y tests; no avanzar automáticamente.
- [ ] Escribir test de `estudio.args_redactar` (`panel/estudio.py:163`): añadir el parámetro `contenido` y comprobar que `--contenido-json` se pone ANTES de `--` y que la idea sigue después. La selección «sugerido» omite argumento manual; elecciones existentes de voz/nivel/molde/ganchos permanecen. Los chips `tpi-chip-tipo` (línea 149) NO se cablean a la intención: siguen eligiendo molde.
- [ ] Prueba de formulario: editar objetivo/intenciones/conclusión y abrir/guardar conserva recursos false y mapa; volver a cargar obtiene los valores cambiados, no otra inferencia. No añadir código de prueba a componentes de producción.

### Paso 2: composición NiceGUI

- [ ] En «Revisa el guion» de Estudio y en la lectura de QC presentar tipos con nombre humano y objetivo, con paridad. Para guiones antiguos mostrar «Ejercicio · estructura actual», no asegurar que la IA analizó una intención nueva. Mantener materia/público/dificultad disponibles y origen honesto.
- [ ] Cada herramienta muestra activo/sugerido, motivo y estado «elegido» cuando override existe. Abrir un diálogo único por tarjeta; usar ui.select de tres estados sugerido/activado/desactivado por bandera, guardar mediante qc.cambiar_recursos y refrescar lista/lectura. Cancelar no escribe.
- [ ] «Cambiar contenido» abre el editor/redacción existente con valores actuales. Nunca reetiquetar como mito sin revisar/reformular la explicación. Controles de intención y objetivo van junto al texto que se va a redactar; enviar Contenido validado a CLI mediante TAREAS, uno a la vez.
- [ ] Resultado del editor separa «Conclusión en texto» de «Fórmula final» y permite vacío matemático solo cuando el esquema de contenido lo admite. No obligar un dato a resolver una incógnita.
- [ ] Accesibilidad: botones nativos y labels en controles, teclado para abrir/cancelar/guardar, Escape en diálogo, foco al cerrar, estados no solo por color. Usar PIEL y NiceGUI actuales, no CSS/JS/HTML propios ni botones invisibles superpuestos.

### Paso 3: comprobar en navegador

- [ ] Iniciar el panel usando su entrada existente y TPI_RAIZ temporal; inspeccionar README/--help para el comando real, no inventar un servidor alternativo. Navegar en browser-use/Playwright disponible, no instalar npm.
- [ ] Camino principal en Estudio: nueva idea con contenido dato -> redacción falsa -> «Revisa el guion» -> cambiar panel a false -> cambiar apariencia en la ficha QC -> vista previa rápida -> aprobar -> producir. Verificar YAML/cola/timeline reales y MP4. Comprobar que los chips de tipo siguen eligiendo molde y que la intención viaja por `--contenido-json`.
- [ ] Bordes: cancelar no-op, YAML inválido, error de guardado real, proceso ocupado, recurso activado sin datos con explicación, reintento, guion antiguo, nivel/carrera, texto largo, teclado y viewport estrecho. No simular un notify exitoso si falla persistencia o proveedor.
- [ ] Ejecutar suite completa y conservar capturas locales; declarar cualquier plataforma o interacción sin comprobar. Revisión y commit autorizado específico.

## Tarea 8 — Cuatro videos que prueban la idea y comparación antigua

**Files:** crear fixtures en `pruebas/datos_didacticos.py` o en carpetas temporales de la prueba; extender pruebas de render según evidencia. Usar `guiones/ejemplos/` solo como lectura; no subir MP4/SRT ni crear nuevos guiones del dueño.

**Consumes:** todas las tareas anteriores.
**Produces:** evidencia medida de contenido, legibilidad, tiempo y compatibilidad; no un quinto sistema de QA.

### Paso 1: primero un solo ejemplo, luego los cuatro fixtures

- [ ] **Gate de validación (diseño de familia Consola):** producir SOLO el mito del cubo y revisarlo con el dueño antes de fabricar los otros tres. «Primero un solo ejemplo para validar la idea.» No avanzar a los cuatro renders sin ese visto bueno.
- [ ] **Mito del cubo:** reutilizar los datos reales de `guiones/caben_ocho_cubos.yaml` (arista 4 cm → 8 cm, materia matemática, nivel 1° medio). Intención mito; premisa «duplicar la arista duplica el volumen». Dibujo `escala` ya admitido (`lado: "4 cm"`, `factor: 2`, `dimension: 3`, `anotar: [contador, razon]`), no un campo inventado para escalar durante vuelo. Variante `consola_mito` con `recursos.panel: true` por override (la variante sola no lo activaría). Conclusión «Duplicar la arista multiplica el volumen por ocho»; fórmula `V_2 = 512 cm³ = 8 V_1` como pieza principal si se conserva el cierre del guion real.
- [ ] **Error de Pitágoras:** materia matemática, contenido error + ejercicio; lado 3/4, error c=3+4 antes de raíz de 3²+4², respuesta 5. Heredar fixture de `pruebas.test_ganchos.guion_datos`, sustituir solo lo pertinente al caso. Variante `consola_error`; hoja de desarrollo con tabs/panel y mapa que apunta a términos existentes.
- [ ] **Dato de tangente:** YAML de sección 4 del diseño (`tipo: grafico_funcion`, NO `grafico`); materia matemática, contenido dato; resultado.texto, ningún resultado.tex. Pendiente local de x² de -1 a 1 con ejes canónicos (`eje_x`/`eje_y`), no una abstracción flotante. Variante `consola_dato`, panel false.
- [ ] **Ejercicio de tolva:** ejemplo EJEMPLOS_DINAMICOS de redactor para ingeniería, balance de masa y despiece; conservar sus unidades/cálculos validados. Añadir contenido ejercicio y variante `consola_pasos` con micro false, sin cambiar simular tiempo real ni voz del dueño.
- [ ] **Regresión de capacidad archivada:** renderizar un ejemplo con `hoja_de_desarrollo` (archivada, carga por nombre) y comprobar que sigue dibujando con gramática; no se resucita como catálogo ni se modifica su YAML.
- [ ] Validar todos con Guion y revisar matemática antes de render; probar mito + ejercicio combinado aparte para exigir fórmula. Verificar que visual usa nombres/medidas admitidos por esquema actual.

### Paso 2: medición y revisión real

- [ ] Render silencioso primero, luego voz sintética real disponible con subtítulos y cama actual en una raíz temporal. Si el proveedor falla, no llamar completo al E2E audible ni usar audio falso como prueba de calidad.
- [ ] De cada MP4 medir con FFprobe/PyAV: ancho/alto/fps, duración, frames decodificables, duración de cada bloque, pausas y tramos repetidos. Un cuadro quieto intencional para leer no es automáticamente un fallo: contrastar timeline con imagen. No perseguir «cero frames repetidos» a costa de la claridad.
- [ ] Extraer cuadros completos de gancho, premisa, cada transición visual, fórmula terminada, error/corrección y conclusión. Revisar a tamaño completo y reproducir el MP4 final. Comprobar correspondencia frase-dibujo, geometría canónica, subtítulos legibles, separación >=0.3, ninguno cortado, sonido sin cortes ni clips vacíos.
- [ ] Comparar la razón de volumen 1/8 (arista 4 cm → 8 cm) y la ecuación 3/4/5 contra lo realmente dibujado. Probar panel fijo durante acercamiento y que las fórmulas erróneas no aparecen como conocimiento consolidado.
- [ ] Medir que movimiento físico dura su tiempo real. Si voz se alarga, mantener comportamiento de corte/aviso actual; no acelerar simulación ni estirar una imagen para ocupar 60 segundos. Más explicación implica más ejemplos pertinentes, no espera añadida.

### Paso 3: regresión exacta y cierre

- [ ] Renderizar los mismos ejemplos antiguos desde una base exacta de main y la rama nueva, misma fuente/config/voz silencio/cache aislado, `PYTHONHASHSEED=0`, `--tema pizarra_nocturna --voz silencio --borrador`. Mantener diferentes carpetas de salida, nunca sobrescribir render del dueño.
- [ ] Comparar frames RGB decodificados en orden y duraciones, no hash del contenedor MP4. Deben ser idénticos para guiones sin campos nuevos. Si no: hallar la primera diferencia y escribir prueba roja antes de ajustar; no flexibilizar umbrales para hacer verde la comparación.
- [ ] Repetir herencia de «Solo el gancho» con voz distinta a marca, velocidad propia y tema elegido; silenciar con petición explícita sin borrar YAML. Verificar origen/contenido/recursos en timeline.
- [ ] Ejecutar `.venv/bin/python -m unittest discover -s pruebas -t . -v` y registrar total/tiempo/fallos; no reciclar el total histórico 1031 como resultado nuevo.
- [ ] Registrar en reporte de entrega los cuatro casos, archivos locales, métricas, defectos corregidos y limitaciones. No decir «listo para usar» sin panel y reproducción final; código y experiencia tienen veredictos separados.

## Tarea 9 — Documentación y entrega de implementación

**Files:** actualizar solo secciones afectadas de `README.md`, `docs/GUIA_GUIONES.md`, `docs/PLAN.md`, `DESIGN.md`, `docs/ANALISIS_TECNICO.md`; regenerar `docs/ANALISIS_TECNICO.html` mediante script existente si cambian cifras. No editar estudios visuales históricos sin nueva observación.

**Consumes:** evidencia final de tareas 1–8.
**Produces:** instrucciones de uso reales y rama/PR autorizada, sin archivos privados.

- [ ] Documentar el YAML conceptual, los cuatro tipos y sus combinaciones, tres estados de recursos, conclusión texto/fórmula y dónde se cambia en el panel. Distinguir claramente funciones implementadas de aspiraciones.
- [ ] Actualizar plantilla de uso con comandos cuya ayuda fue probada; no inventar flags o rutas. Documentar diferencia materia/público/dificultad/molde/contenido/apariencia (variante de Consola) y origen de sugerencias. No reescribir los diseños históricos (`familia-consola`, `estudio-una-pantalla`, `auditoria-prioridades`): este encargo es su etapa siguiente, no su reemplazo.
- [ ] Actualizar DESIGN solo con la UI aprobada, y análisis técnico solo con cifras medidas. Si corresponde ejecutar `.venv/bin/python scripts/doc_a_html.py docs/ANALISIS_TECNICO.md docs/ANALISIS_TECNICO.html`.
- [ ] Revisar cobertura frente a este diseño, imports/callers nuevos, fixtures y `git diff --check`. Hacer revisión independiente solo lectura si disponible y resolver hallazgos reales con pruebas; declarar si no se realizó.
- [ ] Si la sesión autoriza commits/push/PR: revisar git status/diff/log, stage de archivos específicos, commit nuevo sin bypass, fetch y comprobar remoto antes de push normal. Mantener una rama nueva, no main. Crear PR solo cuando su autorización aplica. No incluir .env, mis_ajustes, salida, audio/video ni temporales.
- [ ] Entregar enlace al plan/diseño, commit/rama y PR si se creó, ruta de clics de panel, MP4/SRT locales como enlaces y resultados medidos. No prometer despliegue, fusión automática o viralidad.

## Revisión del plan antes de ejecutar

- [ ] Cada requisito de secciones 4–8 del diseño tiene tarea: esquema/round-trip (1), herramientas (2), renderer/timeline (3), IA/revisor (4), transporte/publicaciones (5), QC seguro (6), controles/aprobación visual (7), E2E/regresión (8), documentación/entrega (9).
- [ ] No hay referencias a fabrica.py, plantilla ia/redactor.md, grupos de estilos nuevos, pytest ni bloques opcionales universales.
- [ ] Las anclas corresponden a main `889f618`; la herencia de gancho se trata como ya presente (PR #42), `PasoIA.mapa` como ya existente, el dibujo de función como `grafico_funcion`, y la pantalla principal como Estudio (no tablero). La familia Consola no se reemplaza.
- [ ] Nombres públicos compartidos son Contenido, RecursosDidacticos, RecursoDidactico, recursos_del_guion, componer_tema, componente_resultado y cambiar_recursos; no introducir alias distintos entre tareas.
- [ ] La clasificación IA y fixtures cambian juntos; todas las llamadas a redactar/producir conservan contenido y los reintentos con YAML no lo regeneran.
- [ ] Ninguna aprobación de un mock, implementación, publicación o fusión está presupuesta por este plan.

## Prompt de arranque para Kiro

```text
Lee docs/superpowers/specs/2026-11-12-contenido-demostrativo-design.md y
 docs/superpowers/plans/2026-11-12-contenido-demostrativo-kiro.md.
Implementa «El dibujo demuestra, no decora» en el motor actual (main 889f618), tarea por tarea.
No ejecutes la agrupación de estilos del plan antiguo de auditoría.
Respeta .kiro/steering/reglas-del-repo.md, unittest y TPI_RAIZ temporal.
Respeta la familia Consola (cinco variantes) y Estudio como pantalla principal; no resucites los 20 estilos archivados.
Conserva los videos antiguos; la herencia de «Solo el gancho» ya está en main (5a10033, PR #42), no la reimplementes.
PasoIA.mapa ya existe: reutilízalo, no crees un segundo formato de mapas. El dibujo de función es grafico_funcion.
Escribe el código en tu sesión principal; no uses subagente implementador.
Antes del código UI muestra el mock y espera aprobación visual.
Verifica cada tarea con prueba roja-verde; produce primero el mito del cubo y revísalo conmigo antes de los otros tres MP4.
No borres estilos, no toques mis_ajustes ni guiones originales y no subas audio/video.
No fusiones con main ni publiques cambios sin mi autorización aplicable.
```
