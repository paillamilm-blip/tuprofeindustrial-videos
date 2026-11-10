# Motor visual · 3D cinemático (subproyecto C)

Fecha: 2026-11-10
Estado: implementado en `feat/motor-visual-vivo` (PR #23), junto con B.

## 1. Alcance

- El `solido_3d` deja de ser un PNG quieto: es una malla real que se proyecta en cada cuadro.
- Órbita continua de cámara (75° de giro y 25° de cabeceo, con arranque y frenada suaves) que se
  asienta en la `vista` que pide el guion. La pose final es la lámina de siempre: la miniatura del
  panel y el último cuadro del paso coinciden.
- Luz de estudio fija en el mundo: Lambert más un brillo especular (acabado metálico satinado) en la
  paleta del tema. Al orbitar, el brillo resbala por el cuerpo y se lee el volumen.
- Despiece opcional (`despiece: true`): el cubo abre sus seis caras, el cilindro separa sus tapas del
  manto y el cono su base. Con `corte: mitad` la mitad de arriba del cubo se levanta y deja ver la
  cara del corte en acento.
- Fuera de alcance de esta entrega: el `vector_3d` (sigue en PNG) y figuras nuevas (tolvas, tuberías,
  piezas mecánicas). Las dos cosas caben en el mismo motor de malla: falta su modelo y su matemática.

## 2. Decisiones

| # | Decisión | Motivo |
|---|----------|--------|
| C1 | Malla proyectada dentro de la escena 2D, no `ThreeDScene` | El video entero es una `MovingCameraScene`: los golpes de cámara, la franja del dibujo, la cabecera y los subtítulos viven en coordenadas 2D. Cambiar de escena rompe todo eso y obliga a fijar cada texto con `add_fixed_in_frame_mobjects`. |
| C2 | Culling de caras de espalda + orden por profundidad (pintor) | Cairo no tiene z-buffer. En cuerpos convexos el culling deja la oclusión exacta; las piezas sueltas del despiece se ordenan entre sí por la profundidad de su centro. |
| C3 | El orden de pintado va en `z_index` (0,02–0,48) | Manim fija la lista de lo que pinta al empezar cada animación, pero la reordena por `z_index` en cada cuadro. Los rótulos van en 0,55 y las fórmulas siguen en 1. |
| C4 | Una sola escala para todo el recorrido | Se mide la caja de 17 poses (órbita y despiece): el cuerpo no crece ni se encoge al girar. |
| C5 | `fisico=False` | Una órbita no tiene velocidad «real»: se reparte en la voz del paso y siempre llega a la vista final. |
| C6 | Silueta exacta por adyacencia de caras | Una arista es contorno si separa una cara visible de una de espalda, o si es borde abierto. Es el trazo de lápiz que tenía la lámina. |
| C7 | Los rótulos se apoyan en el borde del cuerpo en cada pose | Siguen a su pieza en el despiece y nunca quedan encima del manto. |

## 3. Contrato

Sin cambios de contrato para quien llama: `dibujar_solido_3d(visual, col, ancho, alto, papel) -> Dibujo`.
El `Dibujo` ahora trae `vivo`, `duracion` y `fisico=False`. `despiece` es un campo opcional de `Visual`
(error claro si va en otro tipo o en una esfera). La lámina PNG queda en `dibujar_solido_3d_lamina` y
`_render`, que el vector 3D y las pruebas de vistas siguen usando.

## 4. Corrección de paso al motor de A

Con los cuadros del render se vio que los dibujos vivos quedaban congelados en `vivo(0)`. La pose
cambiaba, pero Manim pintaba el dibujo como imagen estática, porque el objeto animado era un
`ValueTracker` aparte. Ahora se anima el propio grupo del dibujo (`movimiento_de`). Arregla también
los cinco dibujos de física de A, que solo movían su estela.

## 5. Verificación

- `pruebas/test_solido_vivo.py`: sin PNG, la órbita cambia el encuadre y termina en la vista, la luz da
  varios tonos, el despiece aparta las piezas y ninguna pose se sale de la franja.
- `pruebas/test_tiempo_de_movimiento.py`: lo animado es el dibujo y no un reloj aparte; sin física, el
  recorrido llena la voz.
- Render final 1080×1920 de `guiones/ejemplos/motor_vivo.yaml`, revisado cuadro a cuadro.
