# Guía para escribir guiones

Un guion es un archivo `.yaml` en `guiones/`. Cada bloque separa **lo que se ve** (`texto`, o `tex` en
LaTeX) de **lo que se escucha** (`voz`), porque la voz sintética no sabe leer fórmulas.

Plantilla comentada: `./tpi nuevo mi_ejercicio` · Ejemplos completos: `guiones/ejemplos/`.

> **Atajo:** `./tpi redactar "enunciado…"` (o una foto o PDF) hace que la IA escriba el guion siguiendo
> estas mismas reglas (sus instrucciones están en `src/tpi_videos/plantillas/ia/`). Esta guía te sirve
> para revisarlo y ajustarlo. En el panel (`./tpi panel` → Crear) haces lo mismo con tarjetas, sin tocar el YAML.

## 1. La estructura del video

| # | Bloque | Duración ideal | Para qué sirve |
|---|---|---|---|
| 1 | `gancho` | 0–3 s | Que no pasen de largo: una pregunta o un dato sorprendente |
| 2 | `enunciado` | 5–8 s | El problema concreto, antes de cualquier fórmula |
| 3 | `datos` (opcional) | 2–3 s c/u | Lo que sabemos; luego queda fijo arriba como referencia |
| 4 | `pasos` | 3–6 s c/u | Una idea por paso; la fórmula se transforma en la siguiente |
| 5 | `resultado` | 3–5 s | La respuesta destacada, **con unidades** |
| 6 | `verificacion` (opcional) | 4–6 s | "¿Tiene sentido?": interpretar, no solo calcular |
| 7 | `reto` (opcional, recomendado) | 5–8 s | Un ejercicio parecido para que practiquen y comenten |
| 8 | `cierre` (opcional) | 3–4 s | Un solo llamado a la acción (por defecto, el de `marca.yaml`) |

**Total ideal: 30–75 segundos** (~120–160 palabras de voz). `./tpi revisar` estima la duración.

## 2. Los campos

```yaml
titulo: "Caída libre: ¿cuánto tarda en caer?"   # corto: cabe en 1–2 líneas
materia: fisica                                  # matematica | fisica | ingenieria
nivel: "2° medio"                                # opcional
tema: pizarra_nocturna                           # opcional: otro estilo solo para este video (./tpi temas)
voz: "es-CL-CatalinaNeural"                      # opcional: otra voz solo para este video
velocidad: "+10%"                                # opcional

gancho:
  texto: "¿Cuánto tarda una piedra en caer 20 metros?"   # en pantalla (los números se destacan solos)
  voz: "¿Cuánto tarda una piedra en caer veinte metros? Menos de lo que crees."
  emoji: "🪨"                       # opcional: emoji 3D que aparece con un salto (./tpi emojis)
  tex: 'h = 20\ \text{m}'           # opcional: una fórmula bajo la pregunta

enunciado:
  texto: "Se deja caer una piedra desde 20 metros de altura. Usa g = 9,8 m/s²."
  voz: "Soltamos una piedra desde veinte metros de altura."
  destacar: ["20 metros", "g = 9,8 m/s²"]   # se subrayan justo cuando la voz las dice

datos:
  - tex: 'h = 20\ \text{m}'
    voz: "La altura es de veinte metros."

pasos:
  - nota: "Despejamos t"            # texto pequeño sobre la fórmula (opcional)
    tex: 't = \sqrt{\frac{2h}{g}}'  # sin tex = paso solo hablado
    voz: "Despejamos el tiempo."
    destacar: ['t']                 # parte de la fórmula que se enmarca (opcional)
    transformar: true               # false = escribirla de cero en vez de transformar la anterior
    emoji: "💡"                     # opcional: junto a la fórmula
  - nota: "Error típico"
    tex: 't = \frac{2h}{g}'          # la forma EQUIVOCADA
    voz: "Mucha gente olvida la raíz. Así el tiempo sale mal."
    error: true                     # se tacha con una ✗ roja (ver sección 5)

resultado:
  tex: 't \approx 2,02\ \text{s}'
  voz: "La piedra tarda unos dos segundos."
  emoji: "⏱️"                       # opcional: como sticker en la esquina del recuadro

verificacion: "Con el doble de altura no tarda el doble."   # forma corta: mismo texto para ver y oír
reto:
  texto: "¿Y desde 45 metros?"
  voz: "Ahora tú: ¿y desde cuarenta y cinco metros? Déjalo en los comentarios."
```

**Forma corta:** `gancho`, `enunciado`, `verificacion`, `reto` y `cierre` aceptan un solo texto
(`reto: "…"`); en ese caso se muestra y se dice lo mismo.

`verificacion`, `reto` y `cierre` también aceptan `emoji:`. En el `cierre`, el emoji o tu sticker
reemplaza al engranaje de la marca.

## 3. Reglas para la voz (lo que se escucha)

- **Gancho en los primeros 3 segundos.** Nunca empieces con "Hola" ni "En este video te mostraré…".
- **Frases cortas:** idealmente 15 palabras o menos. **Una idea por frase.** Voz activa.
- **Escribe como se dice:** "nueve coma ocho metros por segundo al cuadrado", no "9,8 m/s²".
  Evita en la voz: `= / ^ * \ ² √` y guiones largos (—).
- **Di el nombre de cada símbolo la primera vez:** "g, la aceleración de gravedad".
- **Un solo llamado a la acción**, al final.

## 4. Reglas para enseñar mejor

- **Lo concreto antes que lo abstracto:** primero la piedra que cae, después la fórmula.
- **Un paso = un cambio.** Si en un paso pasan dos cosas (despejar *y* reemplazar), divídelo en dos.
  Máximo ~6 pasos; si son más, haz "Parte 1" y "Parte 2".
- **Muestra el cambio, no lo narres:** escribe cada paso como fórmula completa; el motor mueve los términos
  que se repiten de una a otra.
- **Verifica:** una frase de "¿tiene sentido?" ayuda a pensar, no solo a calcular.
- **Termina con un reto parecido:** practicar recordando fija lo aprendido (y genera comentarios).

## 5. Emojis y «error típico» (para enganchar)

**Emojis 3D.** Van en su propio campo `emoji:`, nunca dentro de `texto` ni `voz` (en el texto no se
dibujan y la voz los leería en voz alta). Acepta el emoji (`"🤯"`) o su nombre (`explota`). Lista
completa: `./tpi emojis`.

- Usa 2 a 4 por video: el gancho casi siempre; en los pasos, solo donde aporten (💡 idea clave, ⚠️ cuidado).
- **Tus propias imágenes (stickers):** guarda un PNG con fondo transparente en `mis_ajustes/stickers/`
  (ej. `mis_ajustes/stickers/mascota.png`) y escribe `emoji: mascota`.

**Error típico** (`error: true` en un paso). Es el formato de tus posts que más enganchan («¿Resuelves
así?», «El 90 % se equivoca»):

1. La fórmula equivocada aparece con la nota «¡ERROR TÍPICO!» (o la tuya), se dibuja una ✗ roja encima,
   tiembla y salta un 🚨.
2. El paso siguiente **muestra la forma correcta** y parte de la última fórmula correcta (la tachada no
   se transforma).
3. Úsalo una vez por video y nunca como último paso. Truco: pon la misma fórmula equivocada en el
   gancho (`tex:`) con la pregunta «¿Resuelves así?».

Ejemplo completo: `guiones/ejemplos/matematica_error_binomio.yaml`.

## 6. LaTeX rápido

Escribe las fórmulas **siempre entre comillas simples** `'…'` (con comillas dobles se pierden las `\`).

| Quieres | Escribe |
|---|---|
| fracción ½ | `\frac{1}{2}` |
| raíz | `\sqrt{x}` · raíz cúbica `\sqrt[3]{x}` |
| potencia / subíndice | `t^2` · `x_1` · `v_{0}` |
| unidades | `20\ \text{m}` · `9,8\ \text{m/s}^2` · `12\ \text{V}` · `24\ \Omega` |
| multiplicar | `2 \cdot 20` |
| aproximado / distinto | `\approx` · `\neq` |
| letras griegas | `\alpha \beta \theta \pi \Delta \Omega \mu` |
| vector | `\vec{F}` |
| paréntesis que crecen | `\left( \frac{a}{b} \right)` |
| texto dentro de la fórmula | `x = 2 \quad \text{o} \quad x = 3` |

- **Coma decimal:** escribe `9,8` normal; el motor la deja sin el espacio que LaTeX pondría.
- **Para que los términos "viajen" entre pasos**, sepáralos con espacios: `h = \frac{1}{2} g t^2`.
  Los términos iguales en dos pasos seguidos se mueven de uno a otro.
- **`destacar` en un paso** debe escribirse igual que en `tex` (ej. `'0,5\ \text{A}'`).

## 7. Errores comunes

| Mensaje de `./tpi revisar` | Qué hacer |
|---|---|
| "parece que la fórmula está entre comillas dobles" | Cambia `"…"` por `'…'` en esa fórmula |
| "las llaves { } no están balanceadas" | Cada `{` necesita su `}` |
| "este campo no existe: ¿error de tipeo?" | Revisa el nombre (ej. `pasos`, no `paso`) |
| "la voz contiene el signo =" | Escríbelo en palabras: "igual a" |
| "frase de 24 palabras" | Divídela en dos frases |
| "¿faltan las unidades?" | Agrega la unidad al resultado: `'2,02\ \text{s}'` |
| "el emoji «…» no existe" | Elige uno de `./tpi emojis` o guarda tu imagen en `mis_ajustes/stickers/` |
| "la voz contiene un emoji" / "hay un emoji dentro del texto" | Sácalo de ahí y ponlo en el campo `emoji:` |
| "un paso con «error: true» necesita la fórmula equivocada" | Agrega `tex:` a ese paso |
| "el último paso es un error típico" | Agrega después un paso con la forma correcta |
