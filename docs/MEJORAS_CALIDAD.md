# Mejoras de calidad: voz y explicación

Fecha: 12-11-2026 · Estado: diagnóstico listo, falta la decisión del dueño

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

## Lo que necesita decidir el dueño
- Qué voz probar: A, B o C.
- Si comparte 1 o 2 videos suyos (o cómo explicaría el cubo con sus palabras) para usarlos de modelo.
