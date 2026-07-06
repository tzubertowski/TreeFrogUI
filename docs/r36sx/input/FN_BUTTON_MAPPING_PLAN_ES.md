# Plan de implementación — botón FN en R36SX

## Objetivo

Mapear el botón `FN` de la consola R36SX dentro del flujo TreeFrogUI/LGPT sin reactivar duplicaciones antiguas de botones ni romper combinaciones validadas.

## Principio

Primero se debe identificar cómo aparece `FN` en hardware:

1. como bit adicional dentro del estado `joy_key` compartido,
2. como combinación sintetizada por firmware,
3. como evento de `/dev/input/event*`,
4. como GPIO/tecla expuesta fuera de SDL.

No se debe asignar una función definitiva a `FN` hasta conocer su señal real.

## Fase 1 — probe de entrada

Ejecutar `scripts/r36sx/r36sx_fn_input_probe.sh` en la consola. Durante la ventana de captura, presionar y soltar `FN`, luego probar `FN+A`, `FN+B`, `FN+START`.

Salida esperada:

```text
/mnt/sdcard/r36sx_fn_probe_YYYYMMDD_HHMMSS/
```

Archivos útiles:

```text
summary.txt
proc_bus_input_devices.txt
sys_class_input.txt
dev_input_listing.txt
ipcs_m.txt
input_event*_capture.hex
```

## Fase 2 — decisión de mapeo

Una vez identificado el evento/bit, crear una tabla estable:

```text
FN solo      = abrir menú rápido / modificador, según contexto
FN + A       = quicksave o función asignada por TreeFrogUI
FN + B       = quickload o cancelar extendido
FN + START   = menú sistema o diagnóstico
FN + SELECT  = reservado
```

La prioridad para LGPT será usar `FN` como modificador no destructivo, no como duplicado de `SELECT`, `A` o `B`.

## Fase 3 — implementación

Según dónde aparezca `FN`:

- Si aparece en `/dev/input/event*`: mapear en la capa de entrada de `picoarch` o adapter SDL.
- Si aparece en `joy_key`/shm: agregar bitmask específica R36SX y exponerlo como botón virtual.
- Si solo aparece como combinación ya procesada por firmware: documentar limitación y mapear combinaciones disponibles.

## Regresión obligatoria

Después de cualquier cambio, validar:

- D-pad sigue navegando.
- `A/B/X/Y` siguen dedicados.
- `L1/R1/L2/R2` no cambian semántica.
- `SELECT` conserva funciones actuales.
- No se rompe TreeFrogUI estable en R36SX V2.6 0712.
