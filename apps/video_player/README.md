# TreeFrogUI video player

Small standalone frontend for the HCRTOS `libffplayer` hardware decoder already
shipped in the supported devices' stock firmware. It accepts an ordinary media
path as its sole argument and draws themed playback controls on `/dev/fb1`.

For audio, the containing folder is treated as a simple alphabetical playlist:
the player advances automatically at end of track, X/Y select the previous or
next media file, and A/Start pauses. Select cycles sequential, loop, and random
playback modes (the choice is persisted); B returns to TreeFrogUI. Left/Right
seeks 10 seconds and L/R seeks 60 seconds. Videos use the same containing-folder
queue, including WMV files when supported by the device decoder.

The player reads ID3v1/ID3v2 title, artist, and album tags, falling back to the
filename when needed. It extracts standard ID3v2 APIC album-cover artwork for
the centred cover area. Colors come from
`cubegm/skin/skin.txt`. MP3 playback uses the active theme's main background
colour. An optional `frogui/music_player.txt` can set `background=on|off` and
`background_color=0xRRGGBB` for the audio screen.
