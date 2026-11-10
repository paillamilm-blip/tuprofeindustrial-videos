# Dos públicos (media y universidad de ingeniería) · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el canal haga Matemáticas, Física e Ingeniería para enseñanza media (1° a 4° medio) y para la universidad (1° a 4° año de Ingeniería Civil Industrial, Civil Eléctrica y en Obras Civiles), que «Para hoy» proponga tres del mismo nivel en ambos públicos y que los niveles vacíos se puedan completar con la IA.

**Architecture:** `niveles.py` (catálogo y lectura tolerante) y `malla.py` + `plantillas/malla.yaml` (ramos por nivel, materia y carrera) son la única fuente. `Guion` gana `carrera` opcional. `redactar` agrega la pista de la malla en niveles universitarios. `completar.py` encuentra huecos y redacta. `para_hoy` y Ajustes usan el catálogo.

**Tech Stack:** Python 3.12, PyYAML, pydantic v2, `unittest`, NiceGUI (solo panel).

**Spec:** `docs/superpowers/specs/2026-11-10-dos-publicos-design.md`

## Global Constraints

- Todo campo nuevo del guion es opcional. Ningún guion antiguo cambia.
- Sin dependencias nuevas. Los colores del panel solo en `PIEL`.
- Textos para el usuario en español de Chile, sin trazas técnicas.
- Las pruebas no llaman a Gemini: usan `pruebas/ia_falsa.py`.
- `ruff check` sin errores nuevos. `ruff format` solo en archivos que ya estaban formateados.

---

### Task 1: Catálogo de niveles

**Files:** Create `src/tpi_videos/niveles.py` · Test `pruebas/test_niveles.py`

**Produces:** `PUBLICOS`, `NIVELES`, `CARRERAS`, `normalizar(texto) -> str | None`, `publico_de(nivel) -> str | None`, `es_universidad(nivel) -> bool`, `nombre_carrera(clave) -> str`.

- [ ] Prueba: «3 medio», «2º Medio», «4° medio · PAES», «2° año de ingeniería», «segundo año ingeniería civil», «5° año» → 4° año, «técnico en electricidad» → None.
- [ ] Implementar. Correr la prueba.

### Task 2: La malla

**Files:** Create `src/tpi_videos/plantillas/malla.yaml`, `src/tpi_videos/malla.py` · Test `pruebas/test_malla.py`

**Produces:** `cargar_malla() -> dict`, `ramos(nivel, materia, carrera=None) -> list[str]`, `carreras_del_nivel(nivel) -> tuple[str, ...]`.

- [ ] Prueba: los 8 niveles × 3 materias tienen ramos. En 3° y 4° año, Ingeniería tiene las 3 carreras. `mis_ajustes/malla.yaml` le gana al incluido.
- [ ] Escribir la malla y el lector.

### Task 3: `carrera` en el guion

**Files:** Modify `src/tpi_videos/guion.py` · Test `pruebas/test_niveles.py`

- [ ] Prueba: `carrera: electrica` valida; `carrera: quimica` da un error claro; `a_yaml` la escribe y se vuelve a leer; un guion sin carrera queda igual.
- [ ] `Guion.carrera` opcional; `a_yaml` la escribe después de `nivel`.

### Task 4: La IA conoce los dos públicos

**Files:** Modify `plantillas/ia/sistema.md`, `ideas.md`, `publicar.md`, `src/tpi_videos/redactor.py`, `src/tpi_videos/cli.py` · Test `pruebas/test_niveles.py`

- [ ] Prueba con `ClienteFalso`: con `nivel="2° año ingeniería"` la pista enviada a la IA nombra los ramos de la malla. Con `carrera` el guion guardado la trae, y el nivel queda normalizado.
- [ ] `redactar(..., carrera=None)`, la pista de la malla, `--carrera` en `redactar`, y el texto de presentación de los prompts.

### Task 5: `tpi completar-niveles`

**Files:** Create `src/tpi_videos/completar.py` · Modify `cli.py` · Test `pruebas/test_completar.py`

**Produces:** `Hueco(nivel, materia, carrera, ramo)`, `huecos(publico="todos", nivel=None, materia=None) -> list[Hueco]`, `completar(huecos, redactar=..., avisar=...) -> (escritos, fallidos)`.

- [ ] Prueba: con guiones de prueba, los huecos son los esperados. La carrera elegida es la que menos guiones tiene. `--simular` no redacta. Un fallo no corta el resto.
- [ ] Implementar y conectar al CLI (con `--progreso-json`).

### Task 6: «Para hoy» con dos públicos

**Files:** Modify `src/tpi_videos/panel/para_hoy.py`, `panel/paginas/tablero.py` · Test `pruebas/test_para_hoy.py`

- [ ] Prueba: niveles universitarios entran, ordenados según `NIVELES`; la opción trae la carrera; se prefiere una carrera distinta de la del último video.
- [ ] Chips en dos filas, insignia de carrera, botón «Pedírselo a la IA».

### Task 7: Ajustes → Tu público

**Files:** Modify `src/tpi_videos/panel/paginas/ajustes.py`

- [ ] Lista con los 8 niveles en dos grupos; un nivel antiguo escrito a mano se conserva.

### Task 8: Verificación y documentación

- [ ] CI temporal: suite, `tpi completar-niveles --publico universidad --maximo 3` con el Gemini falso, y Playwright sobre «Para hoy».
- [ ] README, `GUIA_GUIONES.md` (campo `carrera`) y la regla del repo en `.kiro/steering`.
