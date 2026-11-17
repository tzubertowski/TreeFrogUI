"""Generate a local-only, binary-bound read-only FrogUI state profile.

No executable patches. Symbol-derived addresses go only to the caller-selected
ignored analysis directory, never to tracked project source.
"""
import argparse
import hashlib
import json
from pathlib import Path

from elftools.elf.elffile import ELFFile

FIELDS = (
    ('first', 'first.10751', 4),
    ('last_sig', 'last_sig.10750', 4),
    ('idle_ticks', 'fb1_idle_ticks.10765', 4),
    ('transition', 'view_transition_frame', 4),
    ('carousel', 'system_carousel_frame', 4),
    ('animation', 'settings_anim', 4),
    ('toast', 'ui_toast_frames', 4),
    ('screenshot', 'screenshot_pending', 1),
    ('usb_confirm', 'usb_mode_confirm_active', 1),
    ('usb_active', 'usb_mode_initiated_active', 1),
    ('migration', 'port_migration_active', 1),
    ('framebuffer', 'framebuffer', 4),
)


def profile(path, fields=FIELDS):
    if not fields:
        raise ValueError('state profile requires at least one field')
    with path.open('rb') as handle:
        elf = ELFFile(handle)
        if elf.elfclass != 32 or not elf.little_endian or elf['e_machine'] != 'EM_MIPS':
            raise ValueError('requires MIPS32LE ELF')
        table = elf.get_section_by_name('.symtab')
        if table is None:
            raise ValueError('exact local symbols required')
        symbols = {s.name: s for s in table.iter_symbols() if s.name}
        loads = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']

        def mapped(address, size, initialized=False):
            return any(s['p_vaddr'] <= address and address + size <= s['p_vaddr'] +
                       s['p_filesz' if initialized else 'p_memsz'] for s in loads)

        note_section = elf.get_section_by_name('.note.gnu.build-id')
        notes = list(note_section.iter_notes()) if note_section is not None else []
        if notes and (len(notes) != 1 or notes[0]['n_type'] != 'NT_GNU_BUILD_ID'):
            raise ValueError('ambiguous GNU build ID')
        run = symbols['retro_run']
        section = elf.get_section(run['st_shndx'])
        offset = int(run['st_value']) - int(section['sh_addr'])
        signature = section.data()[offset:offset + 32]
        if len(signature) != 32 or not mapped(int(run['st_value']), 32, True):
            raise ValueError('invalid function signature range')
        identity_section = note_section if notes else elf.get_section_by_name('.text')
        identity_bytes = identity_section.data() if notes else identity_section.data()[-64:]
        identity_offset = int(identity_section['sh_addr']) + (0 if notes else int(identity_section['sh_size']) - 64)
        if not mapped(identity_offset, len(identity_bytes), True):
            raise ValueError('identity sample not loaded')
        observed = []
        for label, name, size in fields:
            s = symbols[name]
            if s['st_info']['type'] != 'STT_OBJECT' or s['st_size'] != size or not mapped(int(s['st_value']), size):
                raise ValueError('invalid object: ' + name)
            observed.append({'label': label, 'symbol': name, 'offset': int(s['st_value']), 'size': size})
        raw = path.read_bytes()
        fingerprint = 14695981039346656037
        for byte in raw:
            fingerprint = ((fingerprint ^ byte) * 1099511628211) & 0xffffffffffffffff
        return {'sha256': hashlib.sha256(raw).hexdigest(), 'file_fnv64': fingerprint, 'file_bytes': len(raw),
                'build_id': notes[0]['n_desc'] if notes else 'absent-sha256-' + hashlib.sha256(path.read_bytes()).hexdigest(),
                'identity_scope': 'GNU build ID' if notes else 'two code samples, not whole-file identity',
                'run_offset': int(run['st_value']),
                'run_signature': signature.hex(), 'note_offset': identity_offset,
                'note_bytes': identity_bytes.hex(), 'fields': observed}


def header(data):
    def array(name, raw):
        return 'static const unsigned char ' + name + '[] = {' + ','.join(str(b) for b in bytes.fromhex(raw)) + '};\n'
    text = '/* Generated local-only exact ELF profile. Do not commit. */\n'
    text += '#define R36_STATE_FILE_FNV64 UINT64_C(' + str(data['file_fnv64']) + ')\n'
    text += '#define R36_STATE_FILE_BYTES ' + str(data['file_bytes']) + 'u\n'
    text += '#define R36_STATE_RUN_OFFSET ' + str(data['run_offset']) + 'u\n'
    text += '#define R36_STATE_NOTE_OFFSET ' + str(data['note_offset']) + 'u\n'
    text += '#define R36_STATE_BUILD_ID "' + data['build_id'] + '"\n'
    text += array('r36_state_run_signature', data['run_signature'])
    text += array('r36_state_note', data['note_bytes'])
    text += 'static const struct r36_state_field r36_state_fields[] = {\n'
    for field in data['fields']:
        text += '    {"%s", %du, %du},\n' % (field['label'], field['offset'], field['size'])
    return text + '};\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error('output must be new with existing parent')
    data = profile(args.binary)
    args.out.mkdir()
    (args.out / 'profile.json').write_text(json.dumps(data, indent=2) + '\n')
    (args.out / 'ui_state_profile.h').write_text(header(data))
    print('UI_STATE_PROFILE=PASS sha256=' + data['sha256'])


if __name__ == '__main__':
    main()
