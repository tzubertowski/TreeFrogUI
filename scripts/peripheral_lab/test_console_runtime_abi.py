"""Compare versioned imports against measured console runtime, no device access."""
from pathlib import Path

from elftools.elf.elffile import ELFFile

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/'analysis/driver_port/console_runtime_20261115_v1'


def test_diagnostic_harness_imports_exist_in_measured_console_runtime():
    for name in ('libretro-smoke-console-v2','frontend-backend-console-v1','driver_r36_drm_console_v2.so'):
        with (ROOT/'analysis/driver_port'/name).open('rb') as handle:
            elf=ELFFile(handle)
            versions={}
            for version,aux in elf.get_section_by_name('.gnu.version_r').iter_versions():
                for item in aux:versions[item['vna_other'] & 0x7fff]=(version.name,item.name)
            imports=[]
            symver=elf.get_section_by_name('.gnu.version')
            for index,symbol in enumerate(elf.get_section_by_name('.dynsym').iter_symbols()):
                if symbol['st_shndx']!='SHN_UNDEF' or not symbol.name:continue
                number=symver.get_symbol(index)['ndx']
                if isinstance(number,int) and number & 0x7fff in versions:
                    imports.append((symbol.name,*versions[number & 0x7fff]))
        for symbol,library,version in imports:
            with (RUNTIME/library).open('rb') as handle:
                runtime=ELFFile(handle)
                defs={v['vd_ndx'] & 0x7fff:next(iter(aux)).name for v,aux in runtime.get_section_by_name('.gnu.version_d').iter_versions()}
                ver=runtime.get_section_by_name('.gnu.version')
                available=set()
                for index,item in enumerate(runtime.get_section_by_name('.dynsym').iter_symbols()):
                    number=ver.get_symbol(index)['ndx']
                    if item['st_shndx']!='SHN_UNDEF' and isinstance(number,int):
                        available.add((item.name,defs[number & 0x7fff]))
                assert (symbol,version) in available,(name,library,symbol,version)
