"""Fetch an offline USB candidate; validate isolation, static init and exact build.

No console/COM access. Enumeration and PING/PONG require later hardware evidence.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tarfile

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/kernel_lab'))
from preflight import cpio_files, properties
from build_vm import WORK

FILES = {'manifest.json', 'vmlinux.bin', 'vmlinux.elf', 'kernel.config', 'System.map',
         'r36-lab.dtb', 'init.elf', 'initramfs.cpio.gz', 'r36hello.ko', 'r36_amprpc_poll.ko'}
CONFIG = ('CPU_LITTLE_ENDIAN', 'CEVT_R4K', 'CSRC_R4K', 'PAGE_SIZE_4KB', 'USB', 'USB_GADGET',
          'USB_MUSB_HDRC', 'USB_MUSB_HC16XX', 'USB_MUSB_GADGET', 'MUSB_PIO_ONLY',
          'PHY_HICHIP_USB', 'USB_CONFIGFS', 'USB_CONFIGFS_ACM', 'DEVTMPFS', 'MMC_BLOCK', 'VFAT_FS')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_archive(bundle):
    found = set()
    for item in bundle.getmembers():
        if item.name == '.' and item.isdir(): continue
        name = item.name.removeprefix('./')
        if name not in FILES or not item.isfile() or item.size > 32 * 1024 * 1024 or name in found:
            raise ValueError('invalid USB build archive member: ' + item.name)
        found.add(name)
    if found != FILES: raise ValueError('missing USB build artifacts')


def validate(out, probe):
    manifest = json.loads((out / 'manifest.json').read_text())
    required = FILES - {'manifest.json'}
    for name in required:
        if manifest['sha256'].get(name) != sha(out / name):
            raise ValueError('artifact digest mismatch: ' + name)
    if manifest['release'] != '7.2.0-rc5-r36usb' or manifest['profile'] != 'usb':
        raise ValueError('not the isolated USB profile')
    if sha(out / 'init.elf') != sha(probe): raise ValueError('stale USB init')
    image = (out / 'vmlinux.bin').read_bytes()
    with (out / 'vmlinux.elf').open('rb') as handle:
        elf = ELFFile(handle)
        loads = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        if len(loads) != 1: raise ValueError('wrong kernel load segments')
        s = loads[0]
        if s.data() != image or s['p_memsz'] != manifest['memsz'] or s['p_vaddr'] != int(manifest['load'],0) or elf['e_entry'] != int(manifest['entry'],0):
            raise ValueError('ELF/flat/manifest differ')
    with (out / 'init.elf').open('rb') as handle:
        elf = ELFFile(handle)
        if elf['e_machine'] != 'EM_MIPS' or elf.elfclass != 32 or not elf.little_endian or any(s['p_type'] in ('PT_INTERP','PT_DYNAMIC') for s in elf.iter_segments()):
            raise ValueError('USB PID1 must be static MIPS32LE')
    blob = (out / 'initramfs.cpio.gz').read_bytes()
    if blob not in image or cpio_files(gzip.decompress(blob)).get('init') != (out / 'init.elf').read_bytes():
        raise ValueError('embedded init mismatch')
    config = (out / 'kernel.config').read_text()
    for option in CONFIG:
        if f'CONFIG_{option}=y\n' not in config: raise ValueError('missing USB option: ' + option)
    for option in ('USB_MUSB_HOST','USB_MUSB_DUAL_ROLE','USB_CONFIGFS_MASS_STORAGE','SND','INPUT','GPIO_HC16XX'):
        if f'CONFIG_{option}=y\n' in config or f'CONFIG_{option}=m\n' in config:
            raise ValueError('unexpected subsystem in USB diagnostic: ' + option)
    nodes = properties((out / 'r36-lab.dtb').read_bytes())
    usb0 = nodes['/usb@18844000'] if '/usb@18844000' in nodes else next(p for n,p in nodes.items() if n.endswith('/usb@18844000'))
    usb1 = nodes['/usb@18850000'] if '/usb@18850000' in nodes else next(p for n,p in nodes.items() if n.endswith('/usb@18850000'))
    if usb0['status'] != b'okay\0' or usb0['dr_mode'] != b'peripheral\0' or usb1['status'] != b'disabled\0':
        raise ValueError('USB DT isolation failed')
    if nodes['/amprpc-poll@18800800']['status'] != b'disabled\0' or '/sound@1880a000' in nodes:
        raise ValueError('unexpected peer/audio client')
    if nodes['/memory@0']['reg'] != struct.pack('>II',0,0x02f91e50): raise ValueError('wrong RAM partition')
    args = nodes['/chosen']['bootargs']
    if b'rdinit=/init' not in args or b'clk_ignore_unused' not in args or b'earlycon' in args or b'ttyS' in args:
        raise ValueError('unsafe diagnostic bootargs')
    exports = {s.split()[-1][len('__ksymtab_'):] for s in (out / 'System.map').read_text().splitlines()
               if s.split() and s.split()[-1].startswith('__ksymtab_')}
    for name in ('r36hello.ko','r36_amprpc_poll.ko'):
        with (out/name).open('rb') as handle:
            elf = ELFFile(handle)
            info = elf.get_section_by_name('.modinfo').data()
            if ('vermagic=' + manifest['release'] + ' ').encode() not in info: raise ValueError('module release differs')
            imports = {s.name for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'}
            if imports - exports: raise ValueError('unexported module imports')
    return {'build_passed': True, 'profile':'usb-cdc-diagnostic', 'kernel_sha256':sha(out/'vmlinux.bin'),
            'init_sha256':sha(out/'init.elf'), 'hardware_verified':False, 'deployed':False,
            'Windows_enumeration_verified':False, 'bidirectional_verified':False,
            'scope':'static ABI/hashes/initramfs/USB isolation; no USB hardware test'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--probe',type=Path,default=ROOT/'analysis/driver_port/r36-usb-cdc-init-v1')
    args=parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir(): parser.error('output must be new')
    options=['-i',str(WORK/'id_ed25519'),'-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(WORK/'known_hosts')]
    ssh=['ssh','-p','22222',*options,'root@127.0.0.1']
    if subprocess.check_output(ssh+['cat /work/kernel-build.exit'],timeout=15).strip()!=b'0': raise RuntimeError('build not complete')
    # Also attest that the guest build actually contains the reviewed IRQ fix.
    source='/work/linux-hichip-da5f1a22ef2ff5c46aa3f750fa10825813970b09/drivers/usb/musb/hc16xx.c'
    code=subprocess.check_output(ssh+['cat '+source],timeout=15)
    if b'disable_irq(glue->irq)' in code or b'enable_irq(glue->irq)' in code: raise ValueError('USB IRQ-depth fix missing')
    expected=subprocess.check_output(ssh+['sha256sum /work/kernel-usb-build.tar.gz'],timeout=15).split()[0].decode()
    archive=WORK/(args.out.name+'.tar.gz')
    if archive.exists(): raise FileExistsError(archive)
    subprocess.run(['scp','-P','22222',*options,'root@127.0.0.1:/work/kernel-usb-build.tar.gz',str(archive)],check=True,timeout=60)
    if sha(archive)!=expected: raise ValueError('transfer digest mismatch')
    with tarfile.open(archive) as bundle:
        check_archive(bundle);args.out.mkdir();bundle.extractall(args.out,filter='data')
    (args.out/'build_usb_glue.c').write_bytes(code)
    try: report=validate(args.out,args.probe)
    except (ValueError,KeyError,OSError) as error:
        (args.out/'VALIDATION_FAILED.json').write_text(json.dumps({'passed':False,'error':str(error)},indent=2)+'\n');raise
    report.update(archive_sha256=expected,usb_glue_sha256=hashlib.sha256(code).hexdigest())
    (args.out/'build_receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
