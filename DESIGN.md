# Piel del panel

El panel es una **sala de producción**: una pantalla oscura de supervisión y un solo acento ámbar. «/cola» es **una
sola pantalla** (sin pestañas): una lista donde cada video muestra sus cuatro etapas (Guion, Animación, Video y Kit),
cada una con su porcentaje y su check (verde = lista, anillo ámbar con su % = trabajando, «!» rojo = falló). «/qc» (Aprobar guiones) es también una sola pantalla: un guion a la vez, con chequeos
(verde, ámbar, rojo) y la decisión fija abajo. Avanzado queda a un clic en «/avanzado». Lo manual (Crear a mano: Un video, Lote de 3, Paso a
paso) vive plegado dentro de Avanzado y conserva su piel clara de **muro + hoja crema**.

Todos los colores viven en `src/tpi_videos/panel/comun.py` → `PIEL`. Las páginas leen de ahí; **ninguna página
escribe un hexadecimal suelto** ni usa las constantes viejas `AZUL`/`ROJO`/`VERDE`/`GRIS` (`pruebas/test_piel.py`
lo revisa). Los colores de un estilo de video (las muestras del selector de estilo) se leen del tema en tiempo de
ejecución: no son de la piel.

## Las reglas que mandan

> Todo lo que decide el motor o la IA se muestra con su valor, su **por qué** y un «cambiar»; ningún botón primario
> se deshabilita por no haber tocado una sugerencia.

> **Todo es clicable.** Una cifra abre su lista, una ficha abre su detalle, un texto para redes se copia al tocarlo.
> Lo que responde al clic lleva `tpi-clic` (puntero, resalte al pasar y un tooltip que dice qué va a pasar).

> **El estilo de un video se elige en un solo lugar:** la ficha del guion en QC. Las demás pantallas lo muestran
> y mandan ahí; no agregan otro selector.

## Tokens de la sala (tablero)

| Clave | Valor | Para qué |
|---|---|---|
| `sala` | `#0D1117` | Fondo de toda la pantalla |
| `consola` | `#151B23` | Las tarjetas (`tpi-consola`) |
| `consola_alta` | `#1C2430` | Lo que va encima de una tarjeta: una ficha, el código |
| `linea_sala` | `#26303C` | Separadores y bordes, apenas visibles; también el resalte de `tpi-clic` |
| `texto_sala` | `#E6EDF3` | Texto principal |
| `tenue_sala` | `#8D99A6` | Texto secundario (4,8:1 sobre la consola) |
| `ambar` | `#F2A93B` | La acción principal, lo que está trabajando y la ficha elegida |
| `tinta_ambar` | `#1A1205` | Texto sobre el botón ámbar |
| `verde_sala` | `#3FB950` | Completado, aprobado, «★ sugerido» |
| `rojo_sala` | `#F85149` | Falló, rechazado |
| `celeste_sala` | `#58A6FF` | En espera, por revisar |
| `insignia_matematicas` | `#2F6FEB` | Insignia de Matemáticas |
| `insignia_fisica` | `#1ABC9C` | Insignia de Física |
| `insignia_ingenieria` | `#E8833A` | Insignia de Ingeniería |
| `tinta_insignia` | `#0D1117` | Texto sobre las insignias claras (turquesa y naranja) |

Clases de la sala: `tpi-tablero`, `tpi-pestanas`, `tpi-consola`, `tpi-ficha` (`-elegida`, `-activa`, `-fallo`),
`tpi-cifra`, `tpi-rotulo`, `tpi-insignia(-<categoria>)`, `tpi-hashtag`, `tpi-voz`, `tpi-pausa`, `tpi-codigo`,
`tpi-plegable`, `tpi-aprobar`, `tpi-rechazar`, `tpi-boton-principal`, `tpi-clic` y los colores de texto `tpi-ambar`,
`tpi-verde`, `tpi-rojo`, `tpi-celeste`, `tpi-sobrio`.

## Tokens del muro y la hoja (Crear a mano)

| Clave | Valor | Para qué |
|---|---|---|
| `muro` | `#080A0D` | Fondo del muro de portadas (la elección de familia) |
| `tarjeta` | `#11161C` | Cada tarjeta del muro |
| `borde_muro` | `#223041` | Filete de la tarjeta en reposo |
| `texto_muro` | `#EAF2FF` | Texto sobre el muro |
| `tenue_muro` | `#8A97A8` | Texto secundario sobre el muro |
| `aviso_muro` | `#F0B664` | El ámbar que se lee sobre la tarjeta oscura |
| `hoja` | `#FBF7EC` | El papel crema donde se escribe (`tpi-hoja`) |
| `borde_hoja` | `#DCDCD7` | Filete de la hoja |
| `tinta` | `#1B2430` | Texto sobre la hoja |
| `caja` | `#FAFAF8` | Superficie clara dentro de la hoja: un bloque de texto, una fila |
| `papel_panel` | `#F3F3F0` | Fondo de la página, con renglones |
| `renglon_panel` | `#E4E4E0` | Los renglones del fondo |
| `marca` | `#1C3D74` | Azul de la marca: encabezado, títulos, paso activo |
| `secundario` | `#5B6B86` | `secondary` de Quasar |
| `error` / `error_fuerte` | `#D32F2F` / `#B71C1C` | Lo que falló; el fuerte, para títulos sobre `banda_error` |
| `aviso` / `aviso_fuerte` | `#B26A00` / `#8A5A00` | Lo que conviene mirar; el fuerte, para ayuda sobre blanco o crema |
| `banda_aviso` / `banda_error` | `#FFF4E5` / `#FDECEC` | Fondos de «falta la clave» y «falta completar» |
| `exito` | `#2E7D32` | Lo que ya está |
| `gris` | `#6B6B6B` | Texto tenue sobre claro (4,5:1) |
| `blanco` | `#FFFFFF` | Texto sobre `marca` |
| `costado_px` | `392` | Ancho del panel de detalle, aprobado en el mockup |

## Rejillas

**QC:** lista a la izquierda y lectura a la derecha.

```
grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);  align-items: start
```

**Para hoy y la cola:** tres columnas que se acomodan solas (`repeat(auto-fit, minmax(280px, 1fr))`), una por
materia o por estado. **Selector de estilo:** galería `repeat(auto-fill, minmax(250px, 1fr))`, con el sugerido
primero.

**Crear a mano (muro + costado):** el detalle de la familia elegida va **al costado derecho**, no debajo de la
tarjeta (decisión del autor, 27-10-2026). Es contrato, no preferencia.

```
.tpi-columnas  →  grid-template-columns: minmax(0, 1fr) 392px;  gap: 16px;  align-items: start
.tpi-costado   →  position: sticky; top: 12px
@media (max-width: 900px)  →  una sola columna: el costado pasa abajo, al ancho completo
```

## Tipografías

Embebidas y servidas en `/fuentes/` (`@font-face` en `comun.py`): **Comic Neue** (400 y 700, la letra de la marca y
los títulos), **Bangers** (`.tpi-bangers`, solo para lo que imita el rótulo del video) y **Montserrat SemiBold**
(las cifras del tablero, `.tpi-cifra`). El motor de video usa las mismas familias: si se agrega una letra acá, hay
que registrarla en `tipografia.py` para que el guion pueda pedirla.

## Modo

MODO **Operate** (impeccable): la expresión vive en los videos, no en los controles. En la sala, un solo acento
(ámbar) para lo que hay que hacer y los colores de estado solo para el estado; nada de degradados, sombras
decorativas ni colores nuevos para «animar» la pantalla. Las insignias de materia son la única nota de color fija.
