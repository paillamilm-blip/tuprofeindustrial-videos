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

## Pendiente

- Fase 2 (motor): que el dibujo se quede entre pasos y cambie solo sus marcas (hoy se borra y se vuelve a
  trazar en cada paso). Fase 3: más marcas por dibujo. Las dos tocan la animación: se prueban renderizando.
- `balance_de_masa_en_tolva_de_inyeccion`: el guion es de masa y la tolva solo anota volumen y chapa; repetirla
  sería adorno. Decide el profe.
- Los otros ~25 guiones con avisos: se corrigen de a poco o se regeneran con la IA.
