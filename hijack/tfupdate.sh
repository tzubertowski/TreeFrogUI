#!/bin/sh
# TreeFrogUI offline updater. This file is copied to /tmp by zhijack.sh before
# execution, so the installed copy can safely replace itself during an update.
# Unified for v1.4.0 with custom safety and visual patches.

SDROOT=${TFUPDATE_ROOT:-/mnt/sdcard}
USBROOT=${TFUPDATE_USB_ROOT:-/media/hdd}
PACKAGE="$SDROOT/update.zip"

# [MEJORA USB - PRESERVADO]: Preferir almacenamiento externo si mdev lo montó
[ -f "$USBROOT/update.zip" ] && PACKAGE="$USBROOT/update.zip"

# Definición previa de la función de log para registrar el inicio del script de forma segura
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null) $*" >> "${LOG:-$SDROOT/update.log}"
}

# [MEJORA MULTIMEDIA - PRESERVADO]: Carga visual de fondo para evitar pantalla negra fija
Imagen_Log1() {
    if [ -f "$USBROOT/loading.png" ]; then
        IMG_CARGA="$USBROOT/loading.png"
    elif [ -f "$SDROOT/loading.png" ]; then
        IMG_CARGA="$SDROOT/loading.png"
    fi

    if [ -n "$IMG_CARGA" ] && [ -x "$SDROOT/cubegm/image_viewer" ]; then
        "$SDROOT/cubegm/image_viewer" "$IMG_CARGA" &
        PID_VISOR=$! 
    fi
}

# Ejecutar el visor de imágenes si el paquete está presente en alguna de las rutas
if [ -f "$PACKAGE" ]; then
    Imagen_Log1
    if [ "$PACKAGE" = "$USBROOT/update.zip" ]; then
        log "=== FASE 1: Detectado paquete de actualización en memoria USB ==="
    fi
else
    exit 0
fi

WORK_DIR="$SDROOT/.treefrog-update"
STAGE="$WORK_DIR/staging"
LOG="$SDROOT/update.log"
DEVICE=${1:-}

case "$DEVICE" in
    r36sx|r36hd|sf3000|sf3500|sf3000hd|sf3100|gb350) ;;
    *) 
        if [ -n "$PID_VISOR" ]; then kill "$PID_VISOR" 2>/dev/null; fi
        exit 0 
        ;;
esac

# [MEJORA ALERTA DE FALLOS - PRESERVADO]: Generación limpia de logs y errores en la raíz
fail() {
    log "ERROR: $*"
    
    if [ -n "$VERSION" ]; then
        find "$SDROOT" -maxdepth 1 -name "*.txt" 2>/dev/null | while IFS= read -r archivo_txt; do
            case "$(basename "$archivo_txt")" in v[0-9]*) rm -f "$archivo_txt" 2>/dev/null ;; esac
        done
        echo "ERROR: La actualizacion a la version $VERSION fallo debido a: $*" > "$SDROOT/${VERSION}_ERROR.txt"
    fi

    rm -rf "$STAGE"
    sync
    if [ -n "$PID_VISOR" ]; then kill "$PID_VISOR" 2>/dev/null; fi
    exit 1
}

extract_package() {
    if command -v unzip >/dev/null 2>&1; then
        unzip -o "$PACKAGE" -d "$STAGE"
    elif [ -x /bin/busybox ]; then
        /bin/busybox unzip -o "$PACKAGE" -d "$STAGE"
    else
        return 127
    fi
}

install_tree() {
    SOURCE=$1
    [ -d "$SOURCE" ] || return 0

    find "$SOURCE" -type d > "$STAGE/directories.list" || return 1
    while IFS= read -r DIR; do
        REL=${DIR#"$SOURCE"/}
        [ "$DIR" = "$SOURCE" ] && continue
        mkdir -p "$SDROOT/$REL" || return 1
    done < "$STAGE/directories.list"

    find "$SOURCE" -type f > "$STAGE/files.list" || return 1
    while IFS= read -r SRC; do
        REL=${SRC#"$SOURCE"/}
        [ "$REL" = delete.txt ] && continue
        DST="$SDROOT/$REL"
        TMP="$DST.tfu-new.$$"
        mkdir -p "$(dirname "$DST")" || return 1
        rm -f "$TMP"
        cp "$SRC" "$TMP" || return 1
        mv -f "$TMP" "$DST" || return 1
    done < "$STAGE/files.list"
}

mkdir -p "$WORK_DIR" || exit 1
rm -rf "$STAGE"
mkdir -p "$STAGE" || fail "cannot create staging directory"
log "Applying $(basename "$PACKAGE") for $DEVICE from $(dirname "$PACKAGE")"

extract_package >> "$LOG" 2>&1 \
    || fail "archive extraction failed; package kept for retry"

BUNDLE="$STAGE/treefrog-update"
[ -f "$BUNDLE/manifest.txt" ] || fail "manifest.txt missing"
[ -f "$BUNDLE/SHA256SUMS" ] || fail "SHA256SUMS missing"
[ "$(sed -n 's/^format=//p' "$BUNDLE/manifest.txt")" = 1 ] \
    || fail "unsupported update format"
[ -d "$BUNDLE/payload" ] || fail "universal payload missing"
[ -d "$BUNDLE/device/$DEVICE" ] || fail "payload does not support $DEVICE"

(cd "$BUNDLE" && sha256sum -c SHA256SUMS) >> "$LOG" 2>&1 \
    || fail "checksum verification failed; package kept for retry"

VERSION=$(sed -n 's/^version=//p' "$BUNDLE/manifest.txt")
BASE_VERSION=$(sed -n 's/^base_version=//p' "$BUNDLE/manifest.txt")
BASE_MAJOR=$(sed -n 's/^base_major=//p' "$BUNDLE/manifest.txt")
case "$VERSION" in
    ''|*[!A-Za-z0-9._-]*) fail "invalid update version" ;;
esac
case "$BASE_VERSION" in
    *[!A-Za-z0-9._-]*) fail "invalid base version" ;;
esac
case "$BASE_MAJOR" in
    ''|*[!0-9]*) [ -z "$BASE_MAJOR" ] || fail "invalid base major" ;;
esac
# =========================================================================
# [ALGORITMO AVANZADO DE CONTROL DE VERSIONES] - TU REFUERZO PRESERVADO
# Permite reinstalaciones, parches acumulativos con letras y evita saltos críticos.
# =========================================================================
INSTALLED_VERSION=$(cat "$SDROOT/cubegm/version.txt" 2>/dev/null)

# Limpieza de prefijos 'v' para homologar las cadenas de comparación
INST_CLEAN=$(echo "$INSTALLED_VERSION" | sed 's/^v//')
TGT_CLEAN=$(echo "$VERSION" | sed 's/^v//')

if [ -n "$INST_CLEAN" ] && [ "$INST_CLEAN" != "unknown" ]; then
    # 1. PERMITIR RE-INSTALACIÓN: Si son exactamente iguales, se aprueba directo para reparaciones
    if [ "$INST_CLEAN" = "$TGT_CLEAN" ]; then
        log "Aviso: Reinstalacion forzada detectada para la misma version ($VERSION). Procediendo..."
    else
        # Separar la versión base de las letras acumulativas (ej: 1.4.0_b -> 1.4.0)
        INST_BASE=$(echo "$INST_CLEAN" | cut -d'_' -f1)
        TGT_BASE=$(echo "$TGT_CLEAN" | cut -d'_' -f1)

        # Extraer los componentes numéricos principales (Mayor y Menor)
        INST_MAJOR=$(echo "$INST_BASE" | cut -d'.' -f1)
        INST_MINOR=$(echo "$INST_BASE" | cut -d'.' -f2)
        TGT_MAJOR=$(echo "$TGT_BASE" | cut -d'.' -f1)
        TGT_MINOR=$(echo "$TGT_BASE" | cut -d'.' -f2)

        if [ "$INST_BASE" = "$TGT_BASE" ]; then
            # Misma base con diferente letra (ej: 1.4.0_b -> 1.4.0_d). Es una acumulativa permitida.
            log "Aviso: Actualizacion acumulativa de parches hermanos aprobada de forma segura."
        else
            # Comprobación de descenso de versión (Downgrade prohibido en caliente)
            if [ "$TGT_MINOR" -lt "$INST_MINOR" ] 2>/dev/null; then
                fail "Downgrade no permitido. No puedes instalar la version antigua $VERSION sobre la $INSTALLED_VERSION"
            fi
            
            # Comprobación de saltos ilegales (ej: de 1.3.0 a 1.5.0 ignorando la 1.4.0)
            DIFF_MINOR=$((TGT_MINOR - INST_MINOR))
            if [ "$DIFF_MINOR" -gt 1 ] 2>/dev/null; then
                fail "Salto de actualizacion ilegal. No puedes pasar de la $INSTALLED_VERSION a la $VERSION sin instalar la intermedia"
            fi
        fi
    fi
fi

# [VALIDACIÓN DEL DESARROLLADOR V1.4.0]: Verificación estricta de Major por seguridad global
if [ -n "$BASE_MAJOR" ] && [ "$INST_CLEAN" != "$TGT_CLEAN" ]; then
    case "$INSTALLED_VERSION" in
        v"$BASE_MAJOR".*) ;;
        *) fail "requires major v$BASE_MAJOR, installed version is ${INSTALLED_VERSION:-unknown}" ;;
    esac
fi
# =========================================================================

# Configs are intentionally authoritative: releases may add options, migrate
# formats, or fix incompatible defaults. Keep one pre-update copy for recovery
# without preserving stale values over the new release.
BACKUP="$WORK_DIR/backup-$VERSION"
for REL in \
    frogui/settings.txt \
    frogui/keymap.txt \
    picoarch.cfg \
    cubegm/.pcsx4all/pcsx4all.cfg \
    cubegm/cores/.pcsx4all/pcsx4all.cfg
do
    if [ -f "$BUNDLE/payload/$REL" ] && \
       [ -f "$SDROOT/$REL" ] && [ ! -f "$BACKUP/$REL" ]; then
        mkdir -p "$BACKUP/$(dirname "$REL")" || fail "cannot create config backup"
        cp "$SDROOT/$REL" "$BACKUP/$REL" || fail "cannot back up $REL"
    fi
done

# ROMs, BIOS, saves, histories and media are never deleted. Release configs are
# authoritative and replace installed configs after the backup above. Device
# files are applied last so the launcher is the final boot-critical change.
install_tree "$BUNDLE/payload" || fail "installing universal payload failed"
install_tree "$BUNDLE/device/$DEVICE" || fail "installing device payload failed"

delete_list() {
    LIST=$1
    [ -f "$LIST" ] || return 0
    while IFS= read -r REL; do
        [ -n "$REL" ] || continue
        case "$REL" in
            /*|../*|*/../*|*/..|roms/*|PS/*|GB/*|GBA/*|GBC/*|FC/*|MD/*|SFC/*|\
            cubegm/bios/*|cubegm/saves/*|cubegm/Update/*|.treefrog-update/*|\
            screenshots/*|saves/*|bios/*|update.zip|update.log)
                return 1 ;;
        esac
        rm -f "$SDROOT/$REL" || return 1
    done < "$LIST"
}

delete_list "$BUNDLE/delete.txt" || fail "unsafe or failed common deletion"
delete_list "$BUNDLE/device/$DEVICE/delete.txt" || fail "unsafe or failed device deletion"

echo "$VERSION" > "$SDROOT/cubegm/version.txt.tfu-new.$$" \
    || fail "cannot write installed-version marker"
mv -f "$SDROOT/cubegm/version.txt.tfu-new.$$" \
      "$SDROOT/cubegm/version.txt" \
    || fail "cannot install version marker"
sync

# === ADICIÓN ADAPTADA: Éxito de versión directa en la raíz microSD ===
find "$SDROOT" -maxdepth 1 -name "*.txt" 2>/dev/null | while IFS= read -r archivo_txt; do
    case "$(basename "$archivo_txt")" in
        v[0-9]*) rm -f "$archivo_txt" 2>/dev/null ;;
    esac
done

echo "TreeFrogUI - Version instalada actualmente: $VERSION" > "$SDROOT/${VERSION}.txt"
sync
# ===============================================================

# Deletion is the commit point: failed/interrupted updates retain the package
# and converge by applying it again on the next successful boot.
rm -f "$PACKAGE" || fail "update installed but package deletion failed"
rm -rf "$STAGE"
sync
log "SUCCESS: TreeFrogUI $VERSION installed; package removed"

if [ -n "$PID_VISOR" ]; then
    kill "$PID_VISOR" 2>/dev/null
fi

exit 10
