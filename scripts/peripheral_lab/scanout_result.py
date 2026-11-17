"""Strict digital scanout observations; never infer physical panel visibility."""
import re


def scanout_result(text, late_phase='before_cleanup'):
    if late_phase not in ('before_cleanup', 'late_live'):
        raise ValueError('unsupported late checkpoint')
    required = {'first', late_phase}
    source = re.findall(r'^r36-scanout: callback_source=([0-9a-f]{8}) scaled_target=([0-9a-f]{8}) identity_geometry=1$', text, re.M)
    pattern = (r'^r36-scanout: phase=(first|before_cleanup|late_live) expected=([0-9a-f]{8}) '
               r'mapped=([0-9a-f]{8}) dma=([0-9a-f]{8}) raster_progress=1 digital_match=1 physical_visual=NOT_TESTED$')
    phases = re.findall(pattern, text, re.M)
    phases = [row for row in phases if row[0] in required]
    by_phase = {row[0]: row[1:] for row in phases}
    health = re.findall(r'^r36-scanout: phase=(first|before_cleanup|late_live) active=([0-9a-f]{8}) programmed=([0-9a-f]{8}) boot=([0-9a-f]{8}) pixel=([0-9a-f]{8}) format=6 size=640x480 pitch=(\d+) on=1 timing=1 timeouts=0$', text, re.M)
    health = [row for row in health if row[0] in required]

    def valid_health(row):
        return (row[1] == row[2] and row[1] != row[3]
                and 0x02f90400 <= int(row[1], 16) <= 0x02f90d80
                and int(row[1], 16) % 32 == 0
                and 1280 <= int(row[5]) <= 65536
                and int(row[4], 16) < 0x10000000
                and 0x1000 <= (int(row[4], 16) & 0x07ffffff)
                and (int(row[4], 16) & 0x07ffffff) + int(row[5]) * 480 <= 0x02f91000)

    healthy = (len(health) == 2 and {row[0] for row in health} == required
               and all(valid_health(row) for row in health)
               and health[0][1:] == health[1][1:])
    core = re.findall(r'^ui-core: video=(\d+) RGB565_hash=([0-9a-f]{8}) nonzero_bytes=(\d+)$', text, re.M)
    core_matches = (len(core) == 1 and core[0][0] == '1' and len(source) == 1
                    and core[0][1] == source[0][0] and 0 < int(core[0][2]) <= 640 * 480 * 2)
    markers = re.findall(r'^ui-live: checkpoint_elapsed_ms=(\d+) run=(\d+)$', text, re.M)
    live_timing = (late_phase != 'late_live' or
                   (len(markers) == 1 and 10000 <= int(markers[0][0]) <= 15000
                    and int(markers[0][1]) > 1
                    and re.findall(r'^r36-scanout: live_submitted_frames=(\d+)$', text, re.M) == ['1']))
    good = (live_timing and core_matches and healthy and len(source) == 1 and source[0][0] == source[0][1]
            and len(phases) == 2 and set(by_phase) == required
            and all(all(value == source[0][0] for value in row) for row in by_phase.values())
            and 'observation_failed=1' not in text and 'digital_match=0' not in text)
    first_health = [row for row in health if row[0] == 'first']
    first_hashes = [row for row in phases if row[0] == 'first']
    first_verified = (core_matches and len(first_health) == len(first_hashes) == 1
                      and valid_health(first_health[0]) and source[0][0] == source[0][1]
                      and all(value == source[0][0] for value in first_hashes[0][1:])
                      and 'phase=first observation_failed=1' not in text)
    return {'digital_chain_verified': bool(good), 'first_frame_verified': bool(first_verified),
            'physical_visual_verified': False,
            'source_hash': source[0][0] if len(source) == 1 else None,
            'phases': by_phase}
