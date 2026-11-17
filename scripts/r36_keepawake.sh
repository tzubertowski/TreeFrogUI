#!/bin/sh
# Temporary development mode: pause stock cubevol, whose idle timer powers down.
PIDFILE=/tmp/r36_keepawake.pid
PAUSED=/tmp/r36_keepawake.paused
case "${1:-status}" in
    start)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            echo "keepawake already running"
            exit 0
        fi
        "$0" watch </dev/null >/tmp/r36_keepawake.log 2>&1 &
        echo "$!" > "$PIDFILE"
        echo "keepawake started: $!"
        ;;
    watch)
        : > "$PAUSED"
        while :; do
            for proc in /proc/[0-9]*; do
                [ "$(cat "$proc/comm" 2>/dev/null)" = cubevol ] || continue
                pid=${proc##*/}
                grep -qx "$pid" "$PAUSED" || echo "$pid" >> "$PAUSED"
                if ! grep -q '^State:.*T' "$proc/status"; then
                    if kill -STOP "$pid" 2>/dev/null; then
                        echo "paused cubevol pid=$pid"
                    fi
                fi
            done
            sleep 2
        done
        ;;
    stop)
        if [ -f "$PIDFILE" ]; then
            kill "$(cat "$PIDFILE")" 2>/dev/null
            rm -f "$PIDFILE"
        fi
        if [ -f "$PAUSED" ]; then
            while read -r pid; do
                [ "$(cat "/proc/$pid/comm" 2>/dev/null)" = cubevol ] && kill -CONT "$pid" 2>/dev/null
            done < "$PAUSED"
            rm -f "$PAUSED"
        fi
        echo "keepawake stopped"
        ;;
    status)
        cat "$PIDFILE" /tmp/r36_keepawake.log 2>/dev/null
        ;;
    *) echo "usage: $0 start|stop|status"; exit 2 ;;
esac
