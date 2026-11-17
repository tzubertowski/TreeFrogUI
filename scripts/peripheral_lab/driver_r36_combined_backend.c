/* SPDX-License-Identifier: MIT
 * Combined video (DRM page flip) + audio (ALSA PCM) PICOARCH_DRIVER translation
 * unit for unchanged picoarch / TreeFrogUI binaries on Linux 7.2.
 *
 * Keeps video_drm_backend.c strictly audio-free on disk while producing one
 * shared driver binary exporting:
 *   Video: video_drivers_init, video_driver_disp_frame, video_driver_deinit
 *   Audio: sound_driver_init, sound_driver_playframe, sound_driver_deinit,
 *          sound_driver_flush
 */
#include "video_drm_backend.c"
#include "audio_alsa_backend.c"
