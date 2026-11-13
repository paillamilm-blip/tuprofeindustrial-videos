# Los dibujos acompañan la explicación

Fecha: 13-11-2026 · Rama: `feat/dibujos-acompanan-pasos`

## Por qué

El profe vio videos donde la animación (2D o 3D) aparecía en UN solo paso y el resto eran fórmulas solas:
«no va acorde a la explicación». La causa no era el motor (no tiene límite de dibujos) sino la instrucción
de la IA: «en un ejercicio, máximo UN dibujo en todo el guion» (`sistema.md`, el esquema de `redactor.py`,
la guía y el editor del panel). Medido en `guiones/`: 41 guiones, 26 con un solo dibujo, 10 sin ninguno;
solo 42 de 144 pasos (29 %) llevaban dibujo.

## La regla nueva (fase 1: solo instrucciones y guiones, sin tocar la animación)

En un ejercicio, el **mismo dibujo** (mismo tipo y mismos números) va en **cada paso que se puede ver**, y en
cada uno cambia solo lo que muestra (`anotar`, `vista`, `corte`, `despiece`). Modelo: `el_cubo_partido.yaml`,
`el_vector_en_el_espacio.yaml`. No se mezclan tipos en un ejercicio; un paso de puro álgebra puede ir sin
dibujo; un error tachado no lo necesita; un dato o mito puede usar ejemplos distintos.

- IA: `sistema.md` (regla y «qué dibujo elegir»), esquema de `redactor.py`, `revisor.md` (lo revisa).
- `./tpi revisar`: `acompanar.py` sugiere el dibujo en los pasos con fórmula que no lo tienen, y advierte
  si se mezclan tipos o si el dibujo cambia de números. `scripts/dibujos_que_faltan.py` lista los guiones.
- Lazo de control: nueva marca `malla` (escribe GH), opcional; sin ella el lazo sale igual que antes.

## Guiones corregidos

- `el_lazo_que_se_calma`: el lazo en los 3 pasos (malla → malla y T → T).
- `cuanta_agua_cabe_en_la_lata`: de lámina plana en 1 paso a **cilindro 3D** en los 3 (base desde arriba →
  volumen → despiece de tapas y manto para el área).

## Fase 2: el dibujo se queda entre pasos

Antes: al empezar cada paso el dibujo anterior se desvanecía (`FadeOut`) y el nuevo se trazaba desde cero
(`Create`): «aparece, se borra y se vuelve a dibujar». Ahora, si el paso siguiente usa **el mismo dibujo**
(`continuidad.sigue`: mismo tipo, números y tamaño; cambia lo que muestra) en la misma franja:

1. El dibujo **no sale** al empezar el paso: sigue a la vista mientras se escribe la fórmula nueva.
2. El nuevo se construye y se **alinea por su estructura** (`trazo`: cajas, ejes, cuerpo), no por el centro del
   grupo: un rótulo nuevo abajo correría el centro y el lazo entero «saltaría».
3. Se **empareja pieza por pieza** (`escena.clave_de_pieza`: forma, sitio y color redondeados; también imágenes):
   lo idéntico queda quieto, lo que sobra se desvanece y lo nuevo aparece (`continuidad.emparejar`).
4. Al final se cambia el grupo viejo por el nuevo entre dos cuadros, sacando **toda la familia** del viejo
   (al desvanecer una pieza Manim parte el grupo en la escena y quedarían pedazos pegados).
5. **Cuerpos 3D** (sólido, tolva, tubería, eje): la órbita parte de la vista donde quedó el anterior
   (`dibujos.desde_vista`, un ContextVar como `_relleno`) en vez de girar 75° otra vez; con la misma vista
   el cuerpo no gira (solo se separan las piezas con `despiece`). Sin ese valor la fórmula es la de siempre.

No se activa con el tablero partido (`mitades`) ni cuando el dibujo cambia de tipo o de números.
**Estilo original:** ningún guion de `guiones/ejemplos/` repite el mismo dibujo en pasos seguidos (revisado),
así que esos videos siguen el camino de siempre y deben salir idénticos a `main`.

Límite conocido: entre vistas distintas el tamaño y la luz del cuerpo 3D se calculan para cada vista, así que
al pasar de una a otra hay un ajuste suave de tamaño y brillo (ya no un salto de 75°).

Pruebas: `test_continuidad.py` (sin Manim) y `test_continuidad_dibujos.py` (con Manim: el lazo conserva cajas y
flechas y cambia solo los rótulos; la lata no vuelve a girar si sigue en la misma vista).

## Pendiente

- Verlo renderizado (lazo, lata, `el_cubo_partido`, vectores) y comparar los ejemplos con `main`.
- Fase 3: más marcas por dibujo.
- `balance_de_masa_en_tolva_de_inyeccion`: el guion es de masa y la tolva solo anota volumen y chapa; repetirla
  sería adorno. Decide el profe.
- Los otros ~25 guiones con avisos: se corrigen de a poco o se regeneran con la IA.
