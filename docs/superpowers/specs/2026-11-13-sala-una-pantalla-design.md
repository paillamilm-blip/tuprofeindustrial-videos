# Sala de producción: una sola pantalla, con % y check por etapa

Fecha: 13-11-2026 · Rama: `feat/sala-una-pantalla`

## Por qué

La sala (`/cola`) tenía tres pestañas, cuatro cifras, tres columnas y «Para hoy» arriba de todo. El profe pidió una
sola pantalla, minimalista y fácil de entender para su gente, y que **cada proceso tenga su porcentaje y su check**
para ver cómo avanza cada video.

## La pantalla (`/cola`)

1. Título + resumen («1 produciendo · 2 en espera · 5 listos») y un solo botón: **Producir videos**
   (Detener y el registro del motor solo aparecen mientras algo trabaja).
2. Aviso «N guiones esperan tu aprobación» (solo si hay) → `/qc`.
3. Lista por grupos: Produciendo ahora · En espera · Con problemas · Listos (4 a la vista, «Ver los N listos»).
4. Cada video: título, avance total y **cuatro etapas**: Guion → Animación → Video → Kit, cada una con su %.
   Check verde = lista; anillo ámbar con su % = trabajando; «!» rojo = falló ahí; anillo vacío = espera.
5. Abajo, plegado, «Idea para hoy»; y los enlaces a Aprobar guiones y Herramientas avanzadas.

## Cómo se calcula (`panel/etapas.py`, sin NiceGUI)

Los cortes del avance son los de `lote._traducir`: guion 0–0,25 · animación 0,25–0,90 · video 0,90–0,95 · kit 0,95–1.
Una etapa queda lista si su hito (`guion`, `video`, `kit`) está en la cola o si el avance ya pasó su corte. El 100 %
es solo del check (mientras trabaja, tope 99 %). Un fallo marca la etapa donde quedó. `Ficha.etapas` las trae.

## Reglas de diseño

Colores solo desde `PIEL`; sin animaciones en bucle; accesible (`role="img"` + `aria-label` por etapa, objetivos ≥ 44 px
en botones). `/qc`, `/avanzado` y las rutas antiguas siguen igual.

## Pruebas

`pruebas/test_etapas.py`: etapas por estado, fallo, hitos tras reiniciar, límites, redondeo y `columnas()`.
