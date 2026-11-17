"""Keep userspace and kernel AVP acceptance distinct and tied to a complete run."""


def avp_result(raw, run_id):
    lines = raw.splitlines()
    fresh = lines.count(b"run_id=" + run_id.encode("ascii")) == 1
    complete = (lines.count(b"R36 AVP TRANSPORT PROBE V1") == 1 and
                lines.count(b"R36 AVP PROBE END") == 1 and lines.count(b"probe_rc=0") == 1)
    user = b"transport=PASS" in lines
    kernel = b"kernel_transport=PASS" in lines
    valid = fresh and complete and user != kernel
    return {"fresh": fresh, "complete": complete, "ambiguous": user and kernel,
            "userspace_verified": valid and user, "kernel_verified": valid and kernel}


def display_result(raw, run_id, release, *, kms=False):
    """Accept one complete display report, never infer a visible panel from DMA."""
    import re
    lines = raw.splitlines()
    fresh = lines.count(b"run_id=" + run_id.encode("ascii")) == 1
    kernels = [line for line in lines if line.startswith(b"kernel=")]
    identity = len(kernels) == 1 and kernels[0].startswith(b"kernel=" + release.encode("ascii") + b" ")
    complete = (lines.count(b"R36 DISPLAY PROBE V1") == 1 and
                lines.count(b"R36 DISPLAY PROBE END") == 1 and
                lines[-1:] == [b"R36 DISPLAY PROBE END"] and
                len([line for line in lines if line.startswith(b"probe_rc=")]) == 1 and
                b"probe_rc=0 errno=0" in lines)
    passive = lines.count(b"display_inspection=PASS") == 1
    scanout = lines.count(b"display_scanout=PASS") == 1
    ambiguous = passive and scanout
    failed = any(line.startswith((b"activation_refused=", b"display_inspection=FAIL")) for line in lines)
    hashes = [re.fullmatch(rb"pixel_hash_cpu=([0-9a-f]{8}) pixel_hash_dma=([0-9a-f]{8}) irq_before=([0-9]+) irq_after=([0-9]+) raster_progress=1", line)
              for line in lines if line.startswith(b"pixel_hash_cpu=")]
    scanout_evidence = (len(hashes) == 1 and hashes[0] is not None and
                        hashes[0][1] == hashes[0][2] and int(hashes[0][4]) > int(hashes[0][3]) and
                        lines.count(b"display_module_load_rc=0 errno=0") == 1 and
                        lines.count(b"modeset_requested=1") == 1 and
                        lines.count(b"physical_panel_visual_confirmation=NOT_TESTED") == 1)
    valid = fresh and identity and complete and not ambiguous and not failed
    return {"fresh": fresh, "kernel_matches": identity, "complete": complete,
            "ambiguous": ambiguous, "passive_verified": bool(valid and passive and not kms),
            "scanout_verified": bool(valid and scanout and scanout_evidence and kms),
            "physical_panel_visual_verified": False}


def input_result(raw, run_id, release):
    """Inventory is not proof of physical key mapping or working navigation."""
    display = display_result(raw, run_id, release, kms=True)
    lines = raw.splitlines()
    inventory = (lines.count(b"R36 INPUT INVENTORY V1") == 1 and
                 lines.count(b"R36 INPUT INVENTORY END") == 1 and
                 lines.count(b"input_inventory=PASS") == 1 and
                 lines.count(b"input_probe_rc=0") == 1 and
                 any(line.startswith(b"input_device=r36-serial-keys path=/dev/input/event") for line in lines) and
                 any(line.startswith(b"input_device=r36-direct-keys path=/dev/input/event") for line in lines))
    return {"inventory_verified": bool(display["scanout_verified"] and inventory),
            "physical_mapping_verified": False, "legacy_ui_navigation_verified": False}


def audio_result(raw, run_id, release):
    """Silent PCM acceptance is not proof of audible output or amp ownership."""
    import re
    lines = raw.splitlines()
    fresh = lines.count(b"run_id=" + run_id.encode("ascii")) == 1
    kernel = [line for line in lines if line.startswith(b"kernel=")]
    identity = len(kernel) == 1 and kernel[0].startswith(b"kernel=" + release.encode("ascii") + b" ")
    complete = (lines.count(b"R36 AUDIO SILENT PROBE V1") == 1 and
                lines.count(b"R36 AUDIO SILENT PROBE END") == 1 and
                lines.count(b"audio_probe_rc=0 errno=0") == 1 and
                lines.count(b"probe_rc=0 errno=0") == 1 and
                lines[-1:] == [b"R36 DISPLAY PROBE END"])
    rows = [re.fullmatch(rb"audio_frames=24576 dma_moved=1 irq_before=([0-9]+) irq_after=([0-9]+) drop_rc=0 stopped=1", line)
            for line in lines if line.startswith(b"audio_frames=")]
    progress = len(rows) == 1 and rows[0] is not None and int(rows[0][2]) > int(rows[0][1])
    passed = fresh and identity and complete and progress and lines.count(b"audio_silent_dma=PASS") == 1 and lines.count(b"audio_module_load_rc=0 errno=0") == 1
    return {"fresh": fresh, "complete": complete, "silent_dma_verified": bool(passed),
            "audible_output_verified": False, "speaker_or_headphone_verified": False}


def usb_cdc_result(raw, run_id, release):
    """Device evidence only: enumeration/bidirectional acceptance also needs host proof."""
    import re
    lines = raw.splitlines()
    fresh = lines.count(b"run_id=" + run_id.encode("ascii")) == 1
    identity = lines.count(b"release=" + release.encode("ascii")) == 1
    complete = (lines.count(b"R36 USB CDC PROBE V1") == 1 and
                lines.count(b"R36 USB CDC PROBE END") == 1 and
                lines[-1:] == [b"R36 USB CDC PROBE END"])
    counters = [re.fullmatch(rb"received=([0-9]+) sent=([0-9]+) pings=([0-9]+)", line)
                for line in lines if line.startswith(b"received=")]
    pings = int(counters[0][3]) if len(counters) == 1 and counters[0] else 0
    bound = (fresh and identity and complete and lines.count(b"gadget_rc=0 errno=0") == 1 and
             lines.count(b"phase=bound") == 1 and lines.count(b"unbind_rc=0") == 1)
    return {"fresh": fresh, "complete": complete, "bind_unbind_verified": bool(bound),
            "device_ping_replies": pings, "host_enumeration_verified": False,
            "bidirectional_verified": False, "host_report_required": True}


def core_result(raw, run_id, release):
    """Headless core execution under the measured new kernel, not full UI/gameplay."""
    lines = raw.splitlines()
    fresh = lines.count(b"run_id=" + run_id.encode("ascii")) == 1
    kernels = [line for line in lines if line.startswith(b"kernel=")]
    identity = len(kernels) == 1 and kernels[0].startswith(b"kernel=" + release.encode("ascii") + b" ")
    complete = (lines.count(b"R36 CORE CONSOLE PROBE V1") == 1 and
                lines.count(b"R36 CORE CONSOLE PROBE END") == 1 and
                lines.count(b"console_core_execution=PASS") == 1 and
                lines.count(b"core_probe_rc=0") == 1 and
                lines.count(b"probe_rc=0 errno=0") == 1 and
                lines[-1:] == [b"R36 DISPLAY PROBE END"])
    passed = fresh and identity and complete and lines.count(b"LIBRETRO_SYNTHETIC_EXECUTION=PASS") == 2
    for name in (b"gambatte", b"fceumm"):
        passed = passed and lines.count(b"core_begin=" + name) == 1 and lines.count(b"core_end=" + name + b" exit=0 signalled=0") == 1
    return {"fresh": fresh, "complete": complete, "headless_core_execution_verified": bool(passed),
            "physical_video_audio_input_verified": False, "full_UI_verified": False, "real_games_verified": False}


def frontend_backend_result(raw, run_id, release):
    lines = raw.splitlines()
    fresh = lines.count(b"run_id=" + run_id.encode("ascii")) == 1
    identity = lines.count(b"release=" + release.encode("ascii")) == 1
    complete = (lines.count(b"R36 FRONTEND BACKEND PROBE V1") == 1 and
                lines.count(b"R36 FRONTEND BACKEND PROBE END") == 1 and
                lines[-1:] == [b"R36 FRONTEND BACKEND PROBE END"])
    passed = (fresh and identity and complete and
              lines.count(b"FRONTEND_ABI_DRM_HARNESS=PASS") == 1 and
              lines.count(b"frontend_module_load_rc=0") == 1 and
              lines.count(b"frontend_child_exit=0 signalled=0") == 1 and
              lines.count(b"frontend_probe_rc=0") == 1)
    return {"fresh": fresh, "complete": complete, "video_backend_verified": bool(passed),
            "full_UI_verified": False, "real_games_verified": False}


def ui_appearance_result(raw, child_raw, run_id, release):
    """A live process/frame log cannot prove the physical screen showed FrogUI."""
    import re
    lines = raw.splitlines()
    fresh = lines.count(b"run_id=" + run_id.encode("ascii")) == 1
    identity = lines.count(b"release=" + release.encode("ascii")) == 1
    complete = (lines.count(b"R36 UNCHANGED UI PROBE V1") == 1 and
                lines.count(b"R36 UNCHANGED UI PROBE END") == 1 and
                lines[-1:] == [b"R36 UNCHANGED UI PROBE END"])
    alive = lines.count(b"ui_alive_at_deadline=1") == 1
    counts = [int(m[1]) for line in child_raw.splitlines()
              if (m := re.fullmatch(rb"r36-drm: submitted_frames=([0-9]+) source=[0-9]+x[0-9]+ pitch=[0-9]+", line))]
    frames = max(counts, default=0)
    core_load_failed = b"core_open dlopen failed:" in child_raw
    observed = (fresh and identity and complete and alive and not core_load_failed and
                lines.count(b"ui_module_load_rc=0") == 1 and frames > 0)
    return {"fresh": fresh, "kernel_matches": identity, "complete": complete,
            "process_alive_at_deadline": alive, "frames_logged": frames,
            "UI_process_and_frame_evidence": bool(observed),
            "physical_visual_confirmation_required": True,
            "full_UI_verified": False, "navigation_verified": False, "audio_verified": False}
