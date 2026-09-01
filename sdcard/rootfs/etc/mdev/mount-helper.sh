#!/bin/sh

#define file lock that avoid script running at same time
LOCKFILE="/var/lock/mount-helper.lock"

#LOG='/etc/udev/mdev-mount.log'
LOG='/dev/console'
MNTOPT='-o iocharset=utf8'

if [ ! -e "$LOCKFILE" ]; then
	touch "$LOCKFILE"
	chmod 777 "$LOCKFILE"
fi

#set associated fd
exec 200>"$LOCKFILE"

#try to get file lock, until get it
while ! flock -n  200  ; do
	echo "Lock is currently held by another process, waiting..."
	sleep .100
done

# (e)udev compatibility
[[ -z $MDEV ]] && MDEV=$(basename $DEVNAME)

BLACKLISTED=""
FIRST_MEDIA="hdd"

## device information log
function print_device_info(){
    echo  >> $LOG
    echo  >> $LOG
    echo "**************************" >> $LOG
    echo  >> $LOG
    echo "Action= "$ACTION >> $LOG
    echo "Hotplug count ="$SEQNUM >> $LOG
    echo "Major= "$MAJOR >> $LOG
    echo "Mdev= "$MDEV >> $LOG
    echo "Devpath= "$DEVPATH >> $LOG
    echo "Devtype= "$DEVTYPE >> $LOG
    echo "Subsystem= "$SUBSYSTEM >> $LOG
    echo "Minor= "$MINOR >> $LOG
    echo "Physdevpath= "$PHYSDEVPATH >> $LOG
    echo "Physdevdriver= "$PHYSDEVDRIVER >> $LOG
    echo "Physdevbus= "$PHYSDEVBUS >> $LOG
    echo "Working directory= "$PWD >> $LOG
    echo  >> $LOG
}

notify() {
	if [ -x /usr/bin/hotplug_helper ] ; then
		/usr/bin/hotplug_helper $1 $2 >> $LOG
	fi
}

if [ -z ${DEVPATH} ]; then
    sleep .100
fi

# --- DEFINICIÓN DE RUTAS FIJAS ---
MOUNTPOINT="/media/hdd"
SD_RAIZ="/mnt/sdcard"

case $ACTION in
	add|"")
		ACTION="add"
		FSTYPE=`blkid /dev/${MDEV} | grep -v 'TYPE="swap"' | grep ${MDEV} | sed -e "s/.*TYPE=//" -e 's/"//g'`
		if [ -z "$FSTYPE" ] ; then
			if [ -f /usr/bin/ntfs-3g.probe ] && ! ntfs-3g.probe --readonly /dev/${MDEV} ; then
				sleep .100
			fi
		fi
		# check if already mounted
		if grep -q "^/dev/${MDEV} " /proc/mounts ; then
			flock -u 200
			exit 0
		fi
		DEVCHECK=`expr substr $MDEV 1 7`
		DEVCHECK2=`expr substr $MDEV 1 3`
		for black in $BLACKLISTED; do
			if [ "$DEVCHECK" == "$black" ] || [ "$DEVCHECK2" == "$black" ] ; then
				flock -u 200
				exit 0
			fi
		done
		DEVCHECK=`expr substr $MDEV 1 6`
		if [ "${DEVCHECK}" == "mmcblk" ] ; then
			DEVBASE=`expr substr $MDEV 1 7`
			PARTNUM=`expr substr $MDEV 9 1`
		else
			DEVBASE=`expr substr $MDEV 1 3`
			PARTNUM=`expr substr $MDEV 4 1`
		fi
		if [ -f "/dev/nomount.${DEVBASE}" ] ; then
			flock -u 200
			exit 0
		fi
		if [ "${DEVBASE}" == "${MDEV}" ] ; then
			if [ -d /sys/block/${DEVBASE}/${DEVBASE}1 -o -d /sys/block/${DEVBASE}/${DEVBASE}p1 ] ; then
				flock -u 200
				exit 0
			fi
			if [ ! -f /sys/block/${DEVBASE}/size ] ; then
				flock -u 200
				exit 0
			fi
			if [ `cat /sys/block/${DEVBASE}/size` == 0 ] ; then
				flock -u 200
				exit 0
			fi
		fi
		
		# Limpiar el punto de montaje si quedó huérfano
		if [ -z "`grep $MOUNTPOINT /proc/mounts`" ] ; then
			[ -d $MOUNTPOINT ] && echo "[mdev-mount.sh] rmdir $MOUNTPOINT" >> $LOG
			find $MOUNTPOINT  -type d -maxdepth 0 -delete
			[ -d $MOUNTPOINT ] && rmdir $MOUNTPOINT
		fi

		if [ -z "`grep /dev/$MDEV /proc/mounts`" ]; then
			# Crear directorio base
			mkdir -p "$MOUNTPOINT"

			# Intentar montar el dispositivo físico en la ruta real obligatoria
			MOUNT_SUCCESS=0
			if mount -t auto ${MNTOPT} /dev/$MDEV "${MOUNTPOINT}" -o usefree; then
				MOUNT_SUCCESS=1
			elif mount.exfat ${MNTOPT} /dev/$MDEV "${MOUNTPOINT}" -o usefree; then
				MOUNT_SUCCESS=1
			elif [ -f /sbin/mount.ntfs-3g ] && mount.ntfs-3g /dev/$MDEV "${MOUNTPOINT}" -o usefree; then
				MOUNT_SUCCESS=1
			fi

			# Si el montaje físico funcionó, mapeamos todas las carpetas espejo para TreeFrogUI
			if [ $MOUNT_SUCCESS -eq 1 ]; then
				
				# 1. Espejo General: Raíz del USB completo visible en la raíz de la SD/memory_usb
				mkdir -p "$SD_RAIZ/memory_usb"
				mount --bind "$MOUNTPOINT" "$SD_RAIZ/memory_usb"

				# 2. Espejo de Multimedia y Documentos
				if [ -d "$MOUNTPOINT/videos" ]; then
					mkdir -p "$SD_RAIZ/roms/videos/memory_usb"
					mount --bind "$MOUNTPOINT/videos" "$SD_RAIZ/roms/videos/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/music" ]; then
					mkdir -p "$SD_RAIZ/roms/music/memory_usb"
					mount --bind "$MOUNTPOINT/music" "$SD_RAIZ/roms/music/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/images" ]; then
					mkdir -p "$SD_RAIZ/roms/images/memory_usb"
					mount --bind "$MOUNTPOINT/images" "$SD_RAIZ/roms/images/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/document" ]; then
					mkdir -p "$SD_RAIZ/roms/ebook/memory_usb"
					mount --bind "$MOUNTPOINT/document" "$SD_RAIZ/roms/ebook/memory_usb"
				fi

				# 3. Espejo de Consolas (Ubicadas dentro de /roms/ en el USB)
				if [ -d "$MOUNTPOINT/roms/ps1" ]; then
					mkdir -p "$SD_RAIZ/roms/ps1/memory_usb"
					mount --bind "$MOUNTPOINT/roms/ps1" "$SD_RAIZ/roms/ps1/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/roms/gba" ]; then
					mkdir -p "$SD_RAIZ/roms/gba/memory_usb"
					mount --bind "$MOUNTPOINT/roms/gba" "$SD_RAIZ/roms/gba/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/roms/m2k" ]; then
					mkdir -p "$SD_RAIZ/roms/m2k/memory_usb"
					mount --bind "$MOUNTPOINT/roms/m2k" "$SD_RAIZ/roms/m2k/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/roms/neogeo" ]; then
					mkdir -p "$SD_RAIZ/roms/neogeo/memory_usb"
					mount --bind "$MOUNTPOINT/roms/neogeo" "$SD_RAIZ/roms/neogeo/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/roms/nes" ]; then
					mkdir -p "$SD_RAIZ/roms/nes/memory_usb"
					mount --bind "$MOUNTPOINT/roms/nes" "$SD_RAIZ/roms/nes/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/roms/segacd" ]; then
					mkdir -p "$SD_RAIZ/roms/segacd/memory_usb"
					mount --bind "$MOUNTPOINT/roms/segacd" "$SD_RAIZ/roms/segacd/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/roms/sega" ]; then
					mkdir -p "$SD_RAIZ/roms/sega/memory_usb"
					mount --bind "$MOUNTPOINT/roms/sega" "$SD_RAIZ/roms/sega/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/roms/snes" ]; then
					mkdir -p "$SD_RAIZ/roms/snes/memory_usb"
					mount --bind "$MOUNTPOINT/roms/snes" "$SD_RAIZ/roms/snes/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/roms/geolith" ]; then
					mkdir -p "$SD_RAIZ/roms/geolith/memory_usb"
					mount --bind "$MOUNTPOINT/roms/geolith" "$SD_RAIZ/roms/geolith/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/roms/cps2" ]; then
					mkdir -p "$SD_RAIZ/roms/cps2/memory_usb"
					mount --bind "$MOUNTPOINT/roms/cps2" "$SD_RAIZ/roms/cps2/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/roms/cps3" ]; then
					mkdir -p "$SD_RAIZ/roms/cps3/memory_usb"
					mount --bind "$MOUNTPOINT/roms/cps3" "$SD_RAIZ/roms/cps3/memory_usb"
				fi

				if [ -d "$MOUNTPOINT/roms/gb" ]; then
					mkdir -p "$SD_RAIZ/roms/gb/memory_usb"
					mount --bind "$MOUNTPOINT/roms/gb" "$SD_RAIZ/roms/gb/memory_usb"
				fi
				
                                if [ -d "$MOUNTPOINT/roms/cps1" ]; then
					mkdir -p "$SD_RAIZ/roms/cps1/memory_usb"
					mount --bind "$MOUNTPOINT/roms/cps1" "$SD_RAIZ/roms/cps1/memory_usb"
				fi
                                
				notify "mount" $MOUNTPOINT
				echo "[mdev-mount.sh] mounted $MDEV on $MOUNTPOINT and all TreeFrogUI mirrors created successfully" >> $LOG
			else
				echo "[mdev-mount.sh] mount failed 1" >> $LOG
				find "${MOUNTPOINT}" -type d -maxdepth 0 -delete
				[ -d $MOUNTPOINT ] && rmdir "${MOUNTPOINT}"
			fi
		else
			echo "[mdev-mount.sh] device $MDEV already mounted, skipping" >> $LOG
		fi
		flock -u 200
		;;
	remove)
		# 1. Desmontar de manera forzada/perezosa todos los espejos para no trabar el USB
                umount -l "$SD_RAIZ/roms/cps1/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/gb/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/cps3/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/cps2/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/geolith/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/snes/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/sega/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/segacd/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/nes/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/neogeo/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/m2k/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/gba/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/ps1/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/ebook/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/images/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/music/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/roms/videos/memory_usb" 2>/dev/null
		umount -l "$SD_RAIZ/memory_usb" 2>/dev/null

		# 2. Desmontar el dispositivo físico real
		if grep -q "$MOUNTPOINT " /proc/mounts; then
			umount -l "$MOUNTPOINT"
			echo "[mdev-mount.sh] unmounted $MDEV and cleared all TreeFrogUI mirrors" >> $LOG
			notify "umount" $MOUNTPOINT
		fi
		flock -u 200
		;;
	*)
		flock -u 200
		exit 1
		;;
esac

flock -u 200