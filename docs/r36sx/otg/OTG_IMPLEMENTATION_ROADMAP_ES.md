# Estructura lógica — OTG en R36SX para TreeFrogUI / LGPT

## Objetivo final

Usar el puerto USB-C/OTG de R36SX para tres funciones, en orden incremental:

1. diagnóstico y enumeración OTG,
2. transferencia de archivos hacia/desde la SD,
3. audio USB: salida y, si el kernel lo permite, entrada/captura.

## Restricción de diseño

No activar funciones OTG destructivas ni exponer la partición completa de la SD mientras la consola la tiene montada en escritura. Para transferencia de archivos, preferir un área controlada, una partición dedicada o un flujo MTP/archivo, no exportar a ciegas todo `/mnt/sdcard` como mass storage activo.

## Capas del proyecto

### Capa 0 — baseline estable

Congelar una versión estable TreeFrogUI R36SX V2.6 0712 antes de cada prueba OTG. El baseline actual debe arrancar TreeFrogUI sin pantalla negra.

### Capa 1 — probe read-only

Objetivo: saber qué existe realmente en el kernel/rootfs.

Revisar:

```text
/sys/class/udc
/sys/kernel/config/usb_gadget
/lib/modules
/proc/modules
/dev/snd
/proc/asound
/sys/devices/platform/*musb*/mode
/sys/class/udc/*/state
/sys/class/udc/*/current_speed
dmesg
```

Script asociado:

```text
scripts/r36sx/r36sx_otg_probe.sh
```

### Capa 2 — modo transferencia

Opciones en orden de seguridad:

1. MTP/PTP si el kernel trae funciones gadget compatibles.
2. Mass-storage solo contra imagen o partición dedicada, no contra la SD completa montada.
3. Sincronización por script al apagar/reiniciar si no hay gadget estable.

Criterio de avance:

```text
UDC visible + gadget configurable + el host PC/celular enumera el dispositivo de forma estable.
```

### Capa 3 — salida de audio USB

Hay dos rutas distintas:

- **Host USB audio**: R36SX controla una interfaz USB audio externa. Requiere que el kernel exponga ALSA/UAC host y `/dev/snd`.
- **USB gadget audio**: R36SX aparece como tarjeta de sonido ante PC/celular. Requiere UDC + ConfigFS + funciones UAC (`u_audio`, `usb_f_uac1` o `usb_f_uac2`) + ruta PCM en el kernel.

No asumir que una ruta implica la otra.

### Capa 4 — entrada de audio hacia LGPT

La entrada de audio no debe meterse directamente al core LGPT hasta confirmar ALSA/captura. Rutas posibles:

1. herramienta externa tipo `arecord` que grabe WAV en una carpeta de importación,
2. backend ALSA propio en el adapter TreeFrog/LGPT,
3. integración posterior con el flujo de importación de samples.

## Criterios de decisión

### Avanzar a transferencia de archivos si:

```text
CONFIGFS=YES
UDC_COUNT>0
GADGET_CONFIGURED=YES
HOST_ENUMERATION=YES
```

### Avanzar a audio USB si:

```text
/dev/snd existe
/proc/asound existe
módulos/símbolos snd_pcm disponibles
u_audio o usb_f_uac1/uac2 disponibles para gadget audio
```

### Detener y pasar a kernel/rootfs si:

```text
no hay /dev/snd
no hay /proc/asound
no existen módulos UAC
ConfigFS no puede enlazar con UDC
```

## Rama recomendada

```text
r36sx-otg-probe-structure
```

## Regla operativa

Un cambio por rama:

1. `r36sx-fn-probe`
2. `r36sx-otg-probe`
3. `r36sx-otg-transfer-prototype`
4. `r36sx-usb-audio-detection`
5. `lgpt-r36sx-audio-import-flow`
