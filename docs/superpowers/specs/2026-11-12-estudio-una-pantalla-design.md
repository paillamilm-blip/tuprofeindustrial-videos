# Estudio: el panel en una sola pantalla

Fecha: 12-11-2026 · Rama: `feat/estudio-una-pantalla`

## Por qué

El panel tenía tres pestañas y muchos plegables. Para hacer un video había que saber dónde estaba
cada cosa. El profe pidió «una pantalla simple donde me pida la idea, el nivel, el tipo de contenido
(mito, error u otro) y me deje editar los ganchos y los llamados a la acción muy fácil», sin olvidar
las animaciones.

## Decisiones (elegidas por el profe)

| Pregunta | Elección |
|---|---|
| Flujo | B: primero el guion para revisar, después el video |
| Animaciones | A: ver la miniatura de cada paso con «Cambiar» y «Quitar» |
| Llamado a la acción | C: el cierre del video **y** el texto de la publicación, con sugerencias por tipo |
| Distribución | D: muro (columna de trabajo + columna «Tus videos») |

## La pantalla (`/`)

1. **¿Qué video hacemos?** Cuadro de la idea, nivel (o «que lo decida la IA»), chips de tipo:
   Paso a paso, Error común, Mito, Dato curioso y Reto. Debajo, «Lo último que hiciste» (atajos).
2. **Revisa el guion.** El gancho y sus alternativas (un clic para cambiarlo) o uno escrito a mano.
   Cada paso con su dibujo: Cambiar (la IA arma el nuevo con los datos del ejercicio), Quitar, Editar
   (nota y voz). El cierre del video y el llamado de la publicación, con 3 sugerencias por tipo.
   Botones «Hacer video» (final + kit) y «Borrador rápido».
3. **Tus videos.** El que se está creando, con avance y botón Detener; los últimos 12 con Ver, Textos
   (copiar TikTok, Instagram, YouTube, hashtags) y Guion (lo abre arriba).

La sala de siempre sigue en `/cola`, `/qc` y `/avanzado`; la cabecera enlaza a ella y a Ajustes.

## Tipo → molde

| Tipo | Molde |
|---|---|
| Paso a paso | (libre) |
| Error común | `tres_errores` |
| Mito | `mito_realidad` |
| Dato curioso | `nadie_te_enseno` |
| Reto | `reto` |

## Motor (lo nuevo)

- `Guion.llamado` (máx. 150): el cierre del texto de la publicación. `publicar.aplicar_llamado` lo
  pone en TikTok, Instagram y YouTube en vez del de siempre (sin repetirlo si la IA ya lo escribió).
- `GuionIA.ganchos_alternativos`: la IA propone 2 ganchos más; quedan en `gancho_variantes`.
- `tpi redactar --molde`, `tpi crear --kit` (si el kit falla, el video no se pierde) y
  `tpi redibujar <guion> --paso N --tipo T` (la IA llena el dibujo; si no valida, reintenta una vez;
  solo cambia el `visual` de ese paso).

## Reglas de seguridad y estado

- La URL `/?guion=` solo abre `.yaml` dentro de `guiones/` (si no, el panel podría reescribir otro
  archivo del computador).
- Todo cambio se valida con `Guion` antes de escribir; si no vale, el archivo queda igual.
- Escribir un guion no ocupa la fila de trabajos; hacer el video sí (uno a la vez).
- Estados: vacío, cargando (esqueleto en miniaturas), error con «Reintentar».
- Colores solo desde `PIEL`; movimiento solo `opacity`/`transform` ≤ 220 ms, con `prefers-reduced-motion`.

## Pruebas

`pruebas/test_estudio.py`: tipos y moldes, comandos que entiende el CLI, atajos con archivo roto,
ruta fuera de `guiones/`, cambios al guion, redibujar con IA falsa, ganchos alternativos y llamado.
