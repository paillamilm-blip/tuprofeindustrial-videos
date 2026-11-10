# Diseño: Dos públicos · enseñanza media y universidad de ingeniería

Pedido del usuario el 10-11-2026 en esta conversación: «necesito a y b». El canal hace videos de
Matemáticas, Física e Ingeniería para **dos públicos a la vez**:

- **A · Enseñanza media**: 1° a 4° medio (lo que ya hacía).
- **B · Universidad de ingeniería**: la malla de **Ingeniería Civil Industrial**, **Ingeniería Civil
  Eléctrica** e **Ingeniería en Obras Civiles**, por año: 1° a 4° año.

Rama: `feat/dos-publicos`.

## Contexto

- El nivel hoy es texto libre (`nivel: "3° medio"`). Las instrucciones de la IA dicen que el canal es
  «para estudiantes de enseñanza media y técnico-profesional», y si no se indica un nivel se usa
  «enseñanza media (Chile)».
- «Para hoy» (PR #36) propone tres guiones del mismo nivel, uno por materia. Solo entiende «N° medio».
- De los 40 guiones, Ingeniería solo tiene 3° medio, así que solo ese nivel arma el trío completo.

## Qué hace esta fase

1. **Un catálogo de niveles** (`src/tpi_videos/niveles.py`, solo stdlib): los 8 niveles con su público,
   las 3 carreras y la lectura tolerante del texto («3 medio», «2º Medio», «2° año de ingeniería»,
   «segundo año ingeniería civil»).
2. **La malla** (`src/tpi_videos/plantillas/malla.yaml`): por año y por materia, los ramos y temas
   típicos de una malla chilena. Desde 3° año, Ingeniería trae ramos distintos por carrera. Es datos:
   se puede corregir sin tocar código, y una copia en `mis_ajustes/malla.yaml` le gana.
3. **Campo opcional `carrera`** en el guion (`industrial`, `electrica`, `obras_civiles`). Se escribe
   en el YAML y se muestra como insignia. Guiones antiguos: sin cambios.
4. **La IA conoce los dos públicos.** El texto de presentación de `sistema.md`, `ideas.md` y
   `publicar.md` nombra ambos. Cuando el nivel es universitario, `redactar` agrega una pista con los
   ramos de la malla para ese año, esa materia y esa carrera, para que el ejercicio sea de ese ramo y
   no de media. Hay `--carrera` en `redactar`.
5. **«Para hoy» con dos públicos.**
   - Los chips de nivel se separan en dos filas: «Enseñanza media» y «Universidad».
   - En un nivel universitario, la opción de Ingeniería muestra su carrera, y el orden prefiere una
     carrera distinta de la del último video que salió.
   - Una materia sin guion en ese nivel ofrece **«Pedírselo a la IA»**: escribe uno de ese nivel,
     materia y carrera con un tema de la malla, sin salir de la tarjeta.
6. **`tpi completar-niveles`**: escribe con la IA los guiones que faltan para que cada nivel tenga las
   tres materias (`--publico media|universidad|todos`, `--maximo N`, `--simular`). Hoy faltan 3 de
   Ingeniería en media y los 12 de universidad.
7. **Ajustes → Tu público**: el nivel pasa a ser una lista con los 8 niveles en dos grupos (más «que lo
   deduzca la IA»). Un nivel antiguo escrito a mano se conserva y se muestra.

## 1 · Niveles (`niveles.py`)

```python
PUBLICOS = {"media": "Enseñanza media", "universidad": "Universidad (ingeniería)"}
NIVELES = ("1° medio", "2° medio", "3° medio", "4° medio",
           "1° año ingeniería", "2° año ingeniería", "3° año ingeniería", "4° año ingeniería")
CARRERAS = {"industrial": "Ing. Civil Industrial", "electrica": "Ing. Civil Eléctrica",
            "obras_civiles": "Ing. en Obras Civiles"}

def normalizar(texto) -> str | None   # → una clave de NIVELES o None
def publico_de(nivel) -> str | None   # "media" | "universidad"
def es_universidad(nivel) -> bool
```

Lectura del texto (después de `sin_tildes`, en minúsculas):

- `N[°ºo]? (año)? (de)? medio` → «N° medio» (N de 1 a 4).
- `N[°ºo]? año … ingenieria`, `N[°ºo]? año de universidad`, o `primer|segundo|tercer|cuarto año`
  con «ingenieria» o «universidad» → «N° año ingeniería». También «quinto» y «5° año», que caen en
  4° año: la especialidad final se trata como un solo nivel.
- Todo lo demás (por ejemplo «técnico en electricidad» o «enseñanza media (Chile)») → `None`. Esos
  guiones no aparecen en «Para hoy», igual que hoy.

## 2 · La malla (`plantillas/malla.yaml`)

```yaml
"1° año ingeniería":
  matematica: [Cálculo I (límites, derivadas), Álgebra (matrices, números complejos), …]
  fisica: [Física I: cinemática y dinámica, trabajo y energía, …]
  ingenieria: [Introducción a la ingeniería, …]          # plan común: igual en las 3 carreras
"3° año ingeniería":
  matematica: [Probabilidad y estadística, Métodos numéricos]
  fisica: [Mecánica de fluidos, Electromagnetismo aplicado]
  ingenieria:
    industrial: [Investigación de operaciones (programación lineal), Costos, …]
    electrica: [Circuitos eléctricos (mallas, Thévenin), Máquinas eléctricas, …]
    obras_civiles: [Resistencia de materiales, Hormigón armado, …]
```

- La media también tiene su malla (los temas del currículum de 1° a 4° medio), para el mismo uso:
  elegir un tema cuando hay que escribir uno.
- `malla.ramos(nivel, materia, carrera=None) -> list[str]`. En un año con carreras, sin carrera se
  usan las tres.
- Una prueba exige que cada nivel × materia tenga al menos un ramo.

## 3 · `carrera` en el guion

- `Guion.carrera: Literal["industrial", "electrica", "obras_civiles"] | None = None`. Opcional: no se
  exige ni para Ingeniería ni para universidad.
- `a_yaml` la escribe después de `nivel`. El editor la conserva (viaja como un campo más).
- QC y «Para hoy» muestran su nombre corto junto a la insignia de la materia.

## 4 · La IA

- La primera línea de `sistema.md`, `ideas.md` y `publicar.md` dice «estudiantes de enseñanza media,
  técnico-profesional y de universidad (Ingeniería Civil Industrial, Civil Eléctrica y en Obras
  Civiles)». Se agrega una regla: «si el nivel es universitario, el ejercicio es de un ramo de ese año
  (ver la pista), con el rigor y el lenguaje de la carrera, nunca un problema de media».
- `redactar(..., carrera=None)`: si el nivel es universitario, agrega la pista «Ramos de este año en la
  malla: …» (los de la materia y la carrera) y «Carrera: …». Al guardar, `carrera` queda en el guion
  y el nivel se escribe con su forma normal («2° año ingeniería»).
- `cmd_redactar` recibe `--carrera`.

## 5 · «Para hoy»

- `para_hoy.nivel_de` usa `niveles.normalizar`. El orden de los niveles es el de `NIVELES`.
- `Propuesta.niveles` sigue igual. La pantalla agrupa los chips por `publico_de`.
- Orden dentro de una materia: se agrega, antes de todo, que no repita la carrera del último video que
  salió (solo cuando hay carrera).
- «Pedírselo a la IA» lanza por `TAREAS`
  `tpi completar-niveles --nivel "<nivel>" --materia <m> --maximo 1`, muestra el avance y refresca la
  tarjeta al terminar. Si el motor está ocupado, avisa.

## 6 · `tpi completar-niveles`

```
tpi completar-niveles [--publico media|universidad|todos] [--nivel N] [--materia M]
                      [--maximo 3] [--simular] [--progreso-json]
```

- Calcula los huecos con la misma lógica que «Para hoy»: un nivel × materia sin guion **por revisar**.
- Para cada hueco elige el ramo y la carrera de la malla: en Ingeniería universitaria, la carrera que
  menos guiones tiene en ese nivel. Después llama a `redactar` con un enunciado como «Crea un ejercicio
  típico de <ramo> para <nivel> (<carrera>)», más `materia`, `nivel` y `carrera`.
- `--simular` solo lista lo que escribiría, sin llamar a la IA.
- `--maximo` (3 por defecto) limita cuántos se escriben de una vez: cada uno cuesta una llamada a Gemini.
- Si la IA falla en uno, se informa y se sigue con el siguiente. Al final: «Escribí N; faltan M».

## 7 · Ajustes → Tu público

`ui.select` con `{"": "Que lo deduzca la IA", **{n: n for n in NIVELES}}`, más el valor actual si es un
texto antiguo. Se guarda igual que hoy (`marca.publico.nivel`).

## Qué no cambia

- Los 40 guiones de media siguen como están: el público A ya es lo que hacían.
- La regla del estilo (molde → dibujos → error → materia) es la misma para los dos públicos.
- Sin dependencias nuevas.

## Verificación

- Pruebas unitarias: niveles (lectura tolerante), malla completa, carrera en el guion y en `a_yaml`,
  pista de malla en `redactar` (con la IA falsa), huecos y elección de ramo y carrera en
  `completar-niveles --simular`, «Para hoy» con niveles universitarios y carrera.
- CI: `tpi completar-niveles --publico universidad --maximo 3` con el Gemini falso, para comprobar que
  quedan guiones válidos con su nivel y carrera. Después, Playwright sobre «Para hoy»: dos filas de
  chips, la insignia de carrera y «Pedírselo a la IA».
- Lo que no se puede probar acá: la calidad de lo que escribe el Gemini de verdad. Eso se mira en el Mac
  con `./tpi completar-niveles --simular` y luego sin `--simular`.
