# Mejoras de calidad: voz y explicación

Fecha: 12-11-2026 · Estado: el dueño eligió la voz A y pasó dos videos de @xcris222 como modelo; implementado en `feat/voz-gemini`

## El problema (lo que vio el dueño en el video del cubo)

1. **La voz suena robótica.**
2. **La explicación es mala: no se entiende.**

El motor ya produce videos completos y bien terminados en lo visual. Lo que falla es lo que
el estudiante escucha y la forma en que se razona. Esto es lo más importante del canal, así que
pasa a ser la prioridad.

## Por qué pasa

### La voz
- Se usa `edge-tts` con `es-CL-LorenzoNeural` a +5 % (`marca.yaml`). Es una voz neural gratuita
  pensada para leer, no para enseñar: entona igual una pregunta, un dato y una sorpresa.
- La voz no sabe qué está diciendo: no recibe ninguna indicación de tono («explica con calma»,
  «sorpréndete acá»).
- El guion se escribe para que dure poco (~15 caracteres por segundo y frases de una línea), así
  que la voz dice frases cortadas, que suenan a telegrama.

### La explicación
- El prompt del guionista (`plantillas/ia/sistema.md`) tiene ~4.300 palabras y cerca del 80 % habla
  de cómo pedir dibujos. Casi nada dice **cómo se enseña**: qué idea va primero, cómo se conecta un
  paso con el siguiente o qué confunde al estudiante.
- Las reglas empujan a recortar: el gancho tiene máximo 10 palabras, la nota del paso 5 y el video
  dura de 30 a 75 s. Para cumplirlas, la IA salta pasos del razonamiento.
- El revisor (`plantillas/ia/revisor.md`, ~360 palabras) revisa que la matemática esté bien, pero
  no que **se entienda**. Un guion correcto pero confuso pasa igual.
- No hay ejemplos de «así explica el profe». La IA no conoce la forma de enseñar del dueño.
- Caso concreto, `guiones/caben_ocho_cubos.yaml`, que escribió Kiro a mano:
  - El paso del área (2 · 2 = 4) desvía la pregunta, que era el volumen.
  - «Ese ocho es dos al cubo» no explica por qué.
  - La fórmula del paso 1 aparece antes de que se vean los cubos.

## El plan

### 1 · Voz natural
| Opción | Cómo suena | Costo | Qué hay que hacer |
|---|---|---|---|
| **A. Gemini TTS** (`gemini-3.8-flash-tts`) | Natural y se le puede pedir el tono («profesor chileno cercano, con calma») | Usa la misma clave de Gemini | Agregar un proveedor de voz nuevo |
| **B. Tu voz clonada** (Gemini voice replication o ElevenLabs) | Suena como tú | Gemini: misma clave; ElevenLabs: plan pago | Grabar unos minutos de tu voz |
| **C. Grabar tú** | Lo más auténtico | Tu tiempo | manim-voiceover ya permite grabar con micrófono |

Con A y B los subtítulos se sincronizan con Whisper, porque estas voces no entregan los tiempos
de cada palabra.

### 2 · Guiones que se entienden
1. **Planear antes de escribir.** La IA primero responde, sin escribir el guion:
   - ¿cuál es la UNA idea del video?
   - ¿qué confunde al estudiante?
   - ¿con qué se ve (dibujo, ejemplo cotidiano)?
   - ¿en qué orden se construye?
2. **Reglas de enseñanza en el prompt:**
   - de lo concreto a la fórmula;
   - cada paso responde «¿por qué?» y se engancha al anterior («Por eso…», «Ahora que vimos…»);
   - frases completas y naturales, sin telegrama;
   - una sola idea por video, sin desvíos.
3. **Un revisor de claridad**, aparte del de la matemática: lee como un estudiante del nivel y
   marca lo que no se entiende o salta.
4. **Ejemplos del profe.** De 2 a 3 guiones aprobados por el dueño (o transcripciones de sus
   videos reales) quedan como modelo de «así explico yo».
5. **Más tiempo si hace falta.** Mejor 60 a 80 s claros que 40 s confusos.

### 3 · Primera prueba
Reescribir el video del cubo con el plan 2, generarlo con la voz elegida en el plan 1 y
compararlo con el actual.

## Lo que enseñan los videos de @xcris222 (modelo elegido por el dueño)

Se analizaron dos videos: la transcripción completa, la velocidad de la voz y 8 cuadros de cada uno.
- [Tu primera animación con código](https://www.tiktok.com/@xcris222/video/7700722993890102549): 89 s, 145 palabras/min.
- [Navier-Stokes, forma diferencial](https://www.tiktok.com/@xcris222/video/7697732555067510036): 115 s, 166 palabras/min.

Esto se suma a los 3 videos que ya estaban medidos en `docs/superpowers/specs/2026-11-11-gramatica-visual-xcris-design.md`.

**Cómo explica**
1. **El porqué al inicio.** «La forma integral sirve para… pero si queremos saber qué pasa en cada punto necesitamos la diferencial.»
2. **Punto de partida e idea clave con nombre.** «Partimos de…», «El truco es el teorema de la divergencia…». Primero da la imagen física («lo que sale por las seis caras de un cubito; si sumas todos los cubitos, las caras interiores se cancelan») y después la fórmula.
3. **Pasos numerados en voz alta**, y en pantalla con su nombre: «② Teorema de la divergencia», «⑤ Presión en las caras del cubito».
4. **Qué hacer y para qué**, en la misma frase: «marca la casilla… para que tu computadora lo reconozca».
5. **Conectores que muestran el razonamiento:** «Con él…», «Ahora todo es…», «Como ese volumen puede ser cualquiera… tiene que ser cero en cada punto».
6. **Cada término con su significado:** etiquetas chicas sobre la fórmula («local», «convectiva», «presión», «fricción»).
7. **Cierre en palabras:** «Aceleración local más aceleración convectiva, igual a presión, peso y fricción».
8. **Frases completas y naturales** de ~12 palabras. Videos de 90 a 115 s: claro antes que corto.

**Cómo se ve:** arriba un panel con el dibujo del concepto y el chip numerado del paso; al medio, el subtítulo; abajo, un panel con las fórmulas. La fórmula anterior queda tenue sobre la nueva.

## Qué se implementó (rama `feat/voz-gemini`)
- **Voz A, Gemini TTS:** proveedor `gemini` con la voz `Charon` por defecto y un estilo «profe chileno cercano, con calma» que se puede cambiar en `marca.yaml` (`voz.estilo`).
  - `./tpi voces --gemini` muestra las 30 voces.
  - En el panel, Ajustes → Voz, las voces ✨ Gemini se escuchan y se guardan.
  - `./tpi doctor` avisa si falta la clave.
  - `--voz edge` vuelve a la voz gratis.
- **Reglas de enseñanza** en `plantillas/ia/sistema.md`: las 8 de arriba, frases completas y videos de 45 a 100 s.
- **Gemini piensa antes de escribir:** primero llena `idea_central` y `confusion_tipica`.
- **El revisor también revisa la claridad:** un guion correcto que no se entiende no se aprueba.
- **El dibujo que demuestra (`escala`) se traza antes que su fórmula.**
- **`guiones/caben_ocho_cubos.yaml` reescrito** con estas reglas, como primera prueba.

## Pendiente
- Probar la voz de Gemini en el Mac del dueño. Desde el sandbox no se puede: no tiene la clave.
- Si gusta, clonar la voz del dueño (Gemini voice replication) y usarla con `voz.nombre: voice_…`.
- Que el dueño compare el cubo nuevo con el anterior y diga qué falta.

## Lo que necesita decidir el dueño
- Qué voz probar: A, B o C.
- Si comparte 1 o 2 videos suyos (o cómo explicaría el cubo con sus palabras) para usarlos de modelo.
