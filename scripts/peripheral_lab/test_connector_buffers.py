"""Exercise the actual connector query block with DRM's count/data semantics."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_second_connector_query_has_all_buffers(tmp_path):
    source = (ROOT / "scripts/peripheral_lab/display_probe.c").read_text()
    begin = source.index("    connector.connector_id = connectors[0];")
    end = source.index("    for (i = 0; i < (int)connector.count_modes; i++)", begin)
    block = source[begin:end]
    program = tmp_path / "connector.c"
    program.write_text('''
#include <stdint.h>
#include <assert.h>
#define DRM_IOCTL_MODE_GETCONNECTOR 1
struct connector { uint32_t connector_id, count_modes, count_encoders, count_props, connection;
    uint64_t modes_ptr, encoders_ptr, props_ptr, prop_values_ptr; };
static int calls;
static int checked_ioctl(int op, struct connector *c, const char *phase) {
    (void)op; (void)phase;
    if (calls++) {
        assert(c->count_modes && c->modes_ptr);
        assert(c->count_encoders && c->encoders_ptr);
        assert(c->count_props && c->props_ptr && c->prop_values_ptr);
    }
    c->count_modes=1; c->count_encoders=1; c->count_props=6; c->connection=1;
    return 0;
}
static int check(void) {
    struct connector connector={0};
    uint32_t connectors[1]={42}, modes[64], encoders[64], properties[64];
    uint64_t property_values[64];
''' + block + '''
    return calls == 2 ? 0 : 1;
}
int main(void) { return check(); }
''')
    output = tmp_path / "connector.exe"
    subprocess.run(["gcc", "-Wall", "-Wextra", "-Werror", str(program), "-o", str(output)],
                   check=True, capture_output=True, timeout=20)
    subprocess.run([str(output)], check=True, timeout=5)


def test_drm_mapping_uses_64_bit_offsets():
    source = (ROOT / "scripts/peripheral_lab/display_probe.c").read_text()
    assert source.index("#define _FILE_OFFSET_BITS 64") < source.index("#include")
    assert 'checked_ioctl(DRM_IOCTL_MODE_SETCRTC, &crtc, "setcrtc")' in source
