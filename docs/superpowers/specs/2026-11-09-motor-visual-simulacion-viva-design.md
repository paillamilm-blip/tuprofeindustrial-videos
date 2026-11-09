# Motor visual · Simulación viva (subproyecto A)

Fecha: 2026-11-09
Estado: diseño aprobado por secciones; pendiente la revisión de esta spec.

## 1. Contexto y alcance

El pedido original cubre cuatro frentes: 3D cinemático, simulación física viva, matemática
transformacional y cámara/estética. Son subsistemas independientes y se separaron en tres
subproyectos: **A) simulación viva**, B) matemática viva, C) 3D cinemático. Esta spec cubre
**solo A**.

Alcance acordado:

- Cinco dibujos se mueven: `proyectil`, `pendulo`, `resorte`, `oscilador`, `pendulo_doble`.
- Una sola pasada, sincronizada con la voz del paso.
- El movimiento corre siempre a **tiempo físico real**. Si la voz se alarga, la pose final se
  queda quieta. Si el movimiento físico dura más que la voz, se corta al final del paso y la
  revisión avisa. Nunca se comprime ni se estira.
- Los vectores reactivos aparecen solo cuando el guion los pide; se agrega la marca opcional
  `velocidad` al péndulo.

Fuera de alcance de esta spec: `ThreeDScene`, rotación orbital, iluminación volumétrica, despiece,
`TransformMatchingTex` nuevo, tangente/integral/halos, cambios de cámara, bloque resultado, CLI,
cola y persistencia.

## 2. Decisiones

| # | Decisión | Motivo |
|---|----------|--------|
| D1 | Núcleo de cinco dibujos | Cubren trayectoria, oscilación y deformación con datos ya calculados |
| D2 | Una pasada con la voz | Determinista y sin distraer; calza con la duración que promete la revisión |
| D3 | Tiempo físico real, cortar + aviso | Lo pidió explícitamente; la compresión mentiría sobre la física |
| D4 | Enfoque A: el movimiento vive en el dibujo | La geometría queda donde se construyó y se prueba sin renderizar |
| D5 | Solo cambios aditivos de contrato | Guiones, CLI y persistencia existentes siguen funcionando |
| D6 | Sin módulos nuevos de motor | Todo cabe en `dibujos.py`, `escena.py`, `visuales.py` y `revision.py` |

## 3. Contrato

`Dibujo` (en `src/tpi_videos/dibujos.py`) gana tres campos opcionales:

```python
@dataclass
class Dibujo:
    mobs: VGroup
    trazo: list[Mobject] = field(default_factory=list)
    aparece: list[Mobject] = field(default_factory=list)
    vivo: Callable[[float], None] | None = None   # pose pura: recibe avance 0..1
    duracion: float | None = None                 # segundos físicos del movimiento
    estela: Mobject | None = None                 # TracedPath, opcional
```

Invariantes:

- `vivo` es una función **pura**: recibe 0..1, deja la pose de las piezas móviles y no dibuja,
  no crea mobjects, no consulta la escena ni usa azar. Es idempotente y total en `[0, 1]`.
- `vivo(0)` deja la pose inicial y `vivo(1)` la final.
- `duracion > 0` siempre que haya `vivo`.
- `estela` se agrega a `mobs` para que se desvanezca con el dibujo, pero la escena la agrega
  explícitamente antes de mover.
- Los dibujos que no se mueven quedan con `vivo=None`; su comportamiento no cambia.
- La pose usa la misma escala y el mismo centro que el `_encajar` final, para que nada se salga
  de la franja.

## 4. Reloj

Función pura en `escena.py`:

```python
def avance_de_movimiento(duracion: float, ventana: float) -> tuple[float, bool]:
    """(avance 0..1, se_corta). Nunca comprime: la física manda."""
```

- `duracion <= 0` → `(1.0, False)`.
- `ventana >= duracion` → `(1.0, False)`: se mueve a ritmo real y luego se queda quieto.
- `ventana < duracion` → `(ventana / duracion, True)`: se corta al borde del paso.

En la escena:

1. La aparición (trazo + rótulos) usa como máximo 25 % de la ventana de voz.
2. El resto se anima con un `ValueTracker` y `rate_func=linear`.
3. Al terminar, el tracker se retira de la escena; la pose final queda fija.
4. Los dibujos sin `vivo` conservan los tiempos de hoy.

## 5. Coreografía por dibujo

| Dibujo | Movimiento | Estela | Vectores | Duración |
|--------|------------|--------|----------|----------|
| `proyectil` | Bola recorriendo las 49 muestras de la parábola; la curva queda como guía tenue | `TracedPath` de la bola | `componentes`: vx/vy pegados a la bola; vy se acorta en la cima; color por magnitud | `figura.tiempo` |
| `péndulo` | Masa e hilo siguiendo `θ(t) = θ₀·cos(2πt/T)`; el arco y el ángulo se actualizan | Traza del arco recorrido | Marca opcional `velocidad`: flecha tangencial, larga en el punto bajo y apagada en los extremos | `figura.periodo` |
| `resorte` | Espiral estirándose del reposo a la extensión del guion; bloque y cota acompañan | No | `fuerza`: la flecha `F = kx` crece con el estiramiento y cambia de color | 1,4 s cuasiestático |
| `oscilador` | Punto recorriendo la curva x(t) sobre la guía completa y tenue | `TracedPath` brillante | No; la curva es el dato | `figura.hasta` |
| `péndulo doble` | Brazos y masas siguiendo la serie integrada; escala fija tomada de la traza completa | Traza de la masa de abajo, naciendo en vivo | No | `duracion` (10 s por defecto) |

Detalles de honestidad física:

- El proyectil y el péndulo usan las ecuaciones y períodos que ya calcula `visuales.py`.
- El oscilador y el péndulo doble usan la serie de `scipy.integrate.solve_ivp` de `simulacion.py`.
- El resorte no tiene tiempo en el guion: la deformación es cuasiestática y se declara así; `F`
  sigue exactamente a `x`, no inventa dinámica.
- Los rótulos y las cotas no se mueven; solo las piezas que la física justifica.

## 6. Vectores reactivos

- Solo los que el guion pide. `componentes` del proyectil y `fuerza` del resorte ya existen.
- `MARCAS_PENDULO` suma `"velocidad"`; es aditivo y los guiones viejos no la usan.
- El largo de cada flecha sale de la magnitud real, con un mínimo visible cuando el valor se
  acerca a cero.
- El color interpola la paleta del tema (`tenue` → `acento` → `error`) según la magnitud.
- Nada de flechas automáticas en los otros dibujos ni en pasos que no las piden.

## 7. Aviso de corte en revisión

En `_avisos_de_visuales` (`revision.py`), para los cinco tipos:

- Se calcula la duración física con los analizadores ya existentes (o los valores por defecto).
- Se compara con `estimar_segundos(paso.voz)`.
- Si la física dura más, se agrega un `Aviso("advertencia", ...)` que nombra el tipo, los segundos
  y sugiere bajar `duracion` o alargar la voz.
- No bloquea el render ni cambia el esquema.

## 8. Compatibilidad

- No hay campos YAML obligatorios nuevos. `velocidad` es una marca opcional.
- El esquema Pydantic sigue validando los 27 tipos; los visuales estáticos no cambian.
- CLI, cola y archivos planos no se tocan.
- El 3D con PNG y sus cachés quedan intactos.
- Los guiones existentes con estos cinco tipos renderizan igual, salvo que ahora se mueven.

## 9. Pruebas

Se escriben primero y se ven fallar (TDD):

1. `pruebas/test_dibujos_vivos.py`
   - Los cinco tienen `vivo` y `duracion > 0`.
   - `vivo(0)`, `vivo(0.5)` y `vivo(1)` dejan coordenadas finitas y poses distintas.
   - Los tipos estáticos de muestra conservan `vivo=None`.
   - Casos físicos: la bola del proyectil avanza y termina en el alcance; el péndulo cambia de
     lado; el resorte crece de forma monótona; el oscilador avanza en t; el doble péndulo mueve
     ambas masas.
2. `pruebas/test_tiempo_de_movimiento.py`
   - `avance_de_movimiento(10, 7) == (0.7, True)`.
   - `avance_de_movimiento(2.5, 6) == (1.0, False)`.
   - Nunca devuelve un avance mayor que 1 ni menor que 0.
3. `pruebas/test_revision_movimiento.py`
   - Péndulo doble de 10 s con voz corta produce advertencia.
   - El mismo con `duracion: 4` no la produce.
   - Un visual estático no produce avisos nuevos.
4. Suite completa existente.

## 10. Verificación end-to-end

- `.venv/bin/python -m unittest discover -s pruebas -t .` → todo en verde.
- `./tpi crear guiones/ejemplos/visuales_tres_tipos.yaml --voz silencio` → final 1080×1920, sin
  advertencias ni caídas; sirve de control de regresión de los dibujos estáticos.
- `./tpi crear guiones/el_tiro_que_nunca_cae_donde_apuntas.yaml --voz silencio` → final; se miran
  fotogramas al 25 %, 50 % y 75 % para confirmar que la bola avanza, la estela crece y los
  vectores cambian.
- Si el tiempo alcanza, el mismo control con el péndulo doble para ver el corte y su aviso.
- Confirmar que no aparecen advertencias en la salida del render.

## 11. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| La pose se calcula antes del `_encajar` y queda fuera de la franja | La pose usa la escala y el centro finales; prueba de límites |
| El tracker o la estela quedan vivos y ensucian pasos siguientes | El tracker se retira al terminar; la estela vive en `mobs` y se desvanece con el dibujo |
| Rótulos que chocan con piezas móviles | Los rótulos no se mueven y se mantienen en las posiciones actuales |
| Péndulo doble de 10 s que se corta | Aviso de revisión y ejemplo verificado |
| Cambio de catálogo por `velocidad` | Marca opcional; prueba de que los guiones viejos validan igual |
| Regresión en dibujos estáticos | Suite completa y render de control |
