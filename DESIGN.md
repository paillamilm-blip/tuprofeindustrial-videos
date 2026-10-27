# Piel del panel

Una sola pantalla de trabajo: se entra por un **muro** de portadas y se edita sobre una **hoja crema**.
Todos los colores viven en `src/tpi_videos/panel/comun.py` → `PIEL`. Las páginas leen de ahí; **ninguna
página escribe un hexadecimal suelto** (`pruebas/test_piel.py` lo revisa).

## La regla que manda

> Todo lo que decide la IA se muestra con su valor y un «cambiar»; ningún botón primario se deshabilita por
> no haber tocado una sugerencia.

Nada bloquea el paso. Una sugerencia sin tocar es una decisión válida.

## Tokens

| Clave            | Valor       | Para qué                                                       |
| ---------------- | ----------- | -------------------------------------------------------------- |
| `muro`           | `#080A0D`   | Fondo del muro de portadas (Mis videos y la elección de formato) |
| `tarjeta`        | `#11161C`   | Cada tarjeta del muro                                           |
| `borde_muro`     | `#223041`   | Filete de la tarjeta en reposo                                  |
| `texto_muro`     | `#EAF2FF`   | Texto sobre el muro                                             |
| `tenue_muro`     | `#8A97A8`   | Texto secundario sobre el muro                                  |
| `hoja`           | `#FBF7EC`   | El papel crema donde se escribe (`tpi-hoja`)                    |
| `borde_hoja`     | `#DCDCD7`   | Filete de la hoja                                               |
| `tinta`          | `#1B2430`   | Texto sobre la hoja                                             |
| `papel_panel`    | `#F3F3F0`   | Fondo de la página, con renglones                               |
| `renglon_panel`  | `#E4E4E0`   | Los renglones del fondo                                         |
| `marca`          | `#1C3D74`   | Azul de la marca: encabezado, títulos, paso activo              |
| `secundario`     | `#5B6B86`   | `secondary` de Quasar                                           |
| `error`          | `#D32F2F`   | Lo que falló, y el filete del paso marcado «error típico»       |
| `aviso`          | `#B26A00`   | Lo que conviene mirar sin ser error                             |
| `exito`          | `#2E7D32`   | Lo que ya está                                                  |
| `gris`           | `#6B6B6B`   | Texto tenue sobre claro (4,5:1)                                 |
| `blanco`         | `#FFFFFF`   | Texto sobre `marca`                                             |
| `costado_px`     | `392`       | Ancho del panel de detalle, aprobado en el mockup               |

## Rejilla: muro + costado

El detalle de la familia elegida va **al costado derecho**, no debajo de la tarjeta (decisión del autor,
27-10-2026). Es contrato, no preferencia.

```
.tpi-columnas  →  grid-template-columns: minmax(0, 1fr) 392px;  gap: 16px;  align-items: start
.tpi-costado   →  position: sticky; top: 12px
@media (max-width: 900px)  →  una sola columna: el costado pasa abajo, al ancho completo
```

En el costado, la miniatura 9:16 de la testera mide 78 px de ancho.

## Tipografías

Ya están embebidas y servidas en `/fuentes/` (`@font-face` en `comun.py`): **Comic Neue** (400 y 700, la
letra de la marca y los títulos), **Bangers** (`.tpi-bangers`, solo para lo que imita el rotulo del video) y
**Montserrat SemiBold**. El motor de video usa las mismas familias: si se agrega una letra acá, hay que
registrarla en `tipografia.py` para que el guion pueda pedirla.

## Modo

MODO **Operate** (impeccable): la expresión vive en el muro y en la hoja, no en los controles. Los controles
son azules/gris neutro y quedan en segundo plano; no se agregan degradados, sombras decorativas ni colores
nuevos para «animar» la pantalla.
