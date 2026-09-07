#!/bin/sh
# Use the stock init/power-management route. The forced BusyBox poweroff
# leaves these consoles with a dead display while CubeVol's PMIC path is
# still running; reboot -p lets init run rcK and issue the normal power-off.
sync
exec /sbin/reboot -p
