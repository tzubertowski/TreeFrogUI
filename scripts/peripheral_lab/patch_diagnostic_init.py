"""Create a NEW diagnostic profile by changing only its embedded RAM PID1.

Preserve all kernel code/module ABI/DT. Check initialized ELF/flat bytes, exact
old blob/size symbol, available slot bounds and a reversible whole-image digest.
A replacement exceeding the original compressed slot is refused: rebuild instead.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

from elftools.elf.elffile import ELFFile
from prepare_probe_profile import initramfs


def sha(data): return hashlib.sha256(data).hexdigest()


def patch(source, init, output):
    source,init,output=map(Path,(source,init,output))
    if output.exists() or not output.parent.is_dir(): raise ValueError('output must be new')
    manifest=json.loads((source/'manifest.json').read_text())
    for name,digest in manifest['sha256'].items():
        if Path(name).name!=name or sha((source/name).read_bytes())!=digest: raise ValueError('source artifact mismatch')
    raw=bytearray((source/'vmlinux.bin').read_bytes()); old=(source/'initramfs.cpio.gz').read_bytes()
    elf_data=bytearray((source/'vmlinux.elf').read_bytes()); binary=init.read_bytes()
    with init.open('rb') as handle:
        e=ELFFile(handle)
        if e.elfclass!=32 or not e.little_endian or e['e_machine']!='EM_MIPS' or any(s['p_type'] in ('PT_INTERP','PT_DYNAMIC') for s in e.iter_segments()):raise ValueError('PID1 must be static MIPS32LE')
    with (source/'vmlinux.elf').open('rb') as handle:
        e=ELFFile(handle);loads=[s for s in e.iter_segments() if s['p_type']=='PT_LOAD']
        if len(loads)!=1 or loads[0].data()!=raw:raise ValueError('ELF/flat mismatch')
        load=loads[0]['p_vaddr']; offset=loads[0]['p_offset']
        symbols={s.name:int(s['st_value']) for s in e.get_section_by_name('.symtab').iter_symbols() if s.name}
    begin=symbols['__initramfs_start']-load;size=symbols['__initramfs_size']-load
    if not 0<=begin<=len(raw)-len(old) or not 0<=size<=len(raw)-4:raise ValueError('initramfs symbol bounds')
    if raw[begin:begin+len(old)]!=old or struct.unpack_from('<I',raw,size)[0]!=len(old):raise ValueError('old initramfs bytes differ')
    if max(begin,size)<min(begin+len(old),size+4):raise ValueError('blob/size overlap')
    new=initramfs(binary)
    if len(new)>len(old):raise ValueError(f'new initramfs too large: {len(new)}>{len(old)}; source rebuild required')
    raw[begin:begin+len(old)]=new+bytes(len(old)-len(new));struct.pack_into('<I',raw,size,len(new))
    elf_data[offset:offset+len(raw)]=raw
    restored=raw.copy();restored[begin:begin+len(old)]=old;struct.pack_into('<I',restored,size,len(old))
    if sha(restored)!=manifest['sha256']['vmlinux.bin']:raise ValueError('patch changed code outside initramfs')
    output.mkdir()
    for name in manifest['sha256']:
        if name in ('vmlinuz.bin','vmlinux.bin','vmlinux.elf','init.elf','initramfs.cpio.gz'):continue
        shutil.copy2(source/name,output/name)
    for name,data in [('vmlinux.bin',raw),('vmlinux.elf',elf_data),('init.elf',binary),('initramfs.cpio.gz',new)]:
        (output/name).write_bytes(data)
    manifest['sha256']={p.name:sha(p.read_bytes()) for p in output.iterdir() if p.is_file()}
    manifest.update(hardware_boot_verified=False,ram_handoff_supported=False,
                    initramfs_patched_without_kernel_code_rebuild=True,elf_build_id_stale_after_initramfs_patch=True)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result={'passed':True,'source':str(source),'kernel_code_changed':False,'source_modified':False,
            'old_blob_bytes':len(old),'new_blob_bytes':len(new),'init_sha256':sha(binary),
            'kernel_sha256':sha(raw),'hardware_verified':False,'deployed':False}
    (output/'init_patch_receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--init',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(patch(a.source,a.init,a.out),indent=2))
