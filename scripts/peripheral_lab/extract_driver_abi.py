"""Read exact high-level driver signatures from the owned driver's DWARF."""
import json
from pathlib import Path

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
SELECTED = {"video_drivers_init", "video_driver_deinit", "video_driver_get_size", "video_driver_get_screen_size",
            "video_driver_setmode", "video_driver_disp_frame", "video_driver_update_screen", "video_driver_setting",
            "video_driver_mutex_lock", "video_driver_mutex_unlock", "sound_driver_init", "sound_driver_deinit",
            "sound_driver_playframe", "sound_driver_flush", "g_render", "hdl"}


def attr(die, name):
    if name in die.attributes: return die.attributes[name]
    for reference in ("DW_AT_abstract_origin", "DW_AT_specification"):
        if reference in die.attributes:
            return attr(die.get_DIE_from_attribute(reference), name)
    return None


def name(die):
    value = attr(die, "DW_AT_name")
    return value.value.decode("utf-8", "replace") if value else ""


def type_die(die):
    if "DW_AT_type" in die.attributes: return die.get_DIE_from_attribute("DW_AT_type")
    for reference in ("DW_AT_abstract_origin", "DW_AT_specification"):
        if reference in die.attributes: return type_die(die.get_DIE_from_attribute(reference))
    return None


def type_name(die, depth=0):
    if die is None: return "void"
    if depth > 16: return "recursive_type"
    if die.tag == "DW_TAG_pointer_type": return type_name(type_die(die), depth + 1) + " *"
    if die.tag == "DW_TAG_const_type": return "const " + type_name(type_die(die), depth + 1)
    if die.tag == "DW_TAG_volatile_type": return "volatile " + type_name(type_die(die), depth + 1)
    if die.tag == "DW_TAG_structure_type": return "struct " + (name(die) or "anonymous")
    if die.tag == "DW_TAG_union_type": return "union " + (name(die) or "anonymous")
    if die.tag == "DW_TAG_enumeration_type": return "enum " + (name(die) or "anonymous")
    if die.tag == "DW_TAG_array_type": return type_name(type_die(die), depth + 1) + "[]"
    return name(die) or die.tag


def main():
    source = ROOT / "treefrog/extracted/release/cubegm/driver_gb350.so"
    functions, objects = {}, {}
    with source.open("rb") as handle:
        elf = ELFFile(handle)
        assert elf.has_dwarf_info(strict=True)
        dwarf = elf.get_dwarf_info()
        for cu in dwarf.iter_CUs():
            for die in cu.iter_DIEs():
                symbol = name(die)
                if symbol not in SELECTED: continue
                if die.tag == "DW_TAG_subprogram":
                    params = [{"name": name(child), "type": type_name(type_die(child))}
                              for child in die.iter_children() if child.tag == "DW_TAG_formal_parameter"]
                    if not params and "DW_AT_abstract_origin" in die.attributes:
                        origin = die.get_DIE_from_attribute("DW_AT_abstract_origin")
                        params = [{"name": name(child), "type": type_name(type_die(child))}
                                  for child in origin.iter_children() if child.tag == "DW_TAG_formal_parameter"]
                    value = {"return_type": type_name(type_die(die)), "parameters": params}
                    previous = functions.get(symbol)
                    if previous is None or len(params) > len(previous["parameters"]): functions[symbol] = value
                elif die.tag == "DW_TAG_variable":
                    target = type_die(die)
                    while target and target.tag in ("DW_TAG_typedef", "DW_TAG_const_type"):
                        target = type_die(target)
                    size = attr(target, "DW_AT_byte_size") if target else None
                    members = []
                    if target and target.tag in ("DW_TAG_structure_type", "DW_TAG_union_type"):
                        for member in target.iter_children():
                            if member.tag != "DW_TAG_member": continue
                            location = attr(member, "DW_AT_data_member_location")
                            members.append({"name": name(member), "type": type_name(type_die(member)),
                                            "offset": location.value if location and isinstance(location.value, int) else None})
                    objects[symbol] = {"type": type_name(type_die(die)), "byte_size": size.value if size else None, "members": members}
    report = {"source": str(source), "source_modified": False, "selected_DWARF_types_found": bool(functions or objects),
              "evidence": "DWARF search; missing prototypes remain unknown and must not be guessed",
              "documented_wrapper_reference": "release/upstream-TreeFrogUI/apps/usb_mode/capture/tfshim.c:21",
              "documented_wrapper_signatures": ["int video_driver_disp_frame(void *src, int w, int h, int pitch_bytes)",
                                                 "int sound_driver_init(void *device_name, int sample_rate, int channels)",
                                                 "int sound_driver_playframe(const void *buf, int frames)"],
              "functions": functions, "objects": objects, "missing": sorted(SELECTED - functions.keys() - objects.keys())}
    (ROOT / "analysis/driver_port/DRIVER_UI_SIGNATURES.json").write_text(json.dumps(report, indent=2) + "\n")
    for function, value in sorted(functions.items()):
        arguments = ", ".join(parameter["type"] + " " + parameter["name"] for parameter in value["parameters"])
        print(f"{value['return_type']} {function}({arguments});")
    print("objects:", ", ".join(objects))
    print("missing:", report["missing"])


if __name__ == "__main__":
    main()
