# TreeFrogUI video player

Small standalone frontend for the HCRTOS `libffplayer` hardware decoder already
shipped in the supported devices' stock firmware. It accepts an ordinary media
path as its sole argument and draws themed playback controls on `/dev/fb1`.

Controls: A/Start pauses, Left/Right seeks 10 seconds, L/R seeks 60 seconds,
and B/Select returns to TreeFrogUI. Colors come from `cubegm/skin/skin.txt`.
