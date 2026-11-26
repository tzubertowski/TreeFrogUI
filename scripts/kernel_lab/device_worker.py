"""One MTP operation per process, so a stuck WPD call has a host-side deadline."""
import base64
import json
import os
from pathlib import Path
import sys

ROOT = Path(os.environ.get("R36_PROJECT_ROOT", Path(__file__).resolve().parents[2]))


def main():
    device = None
    try:
        request = json.loads(sys.argv[1])
        sys.path.insert(0, str(ROOT / "release/upstream-TreeFrogUI/apps/usb_mode/pc"))
        import r36
        action = request["action"]
        if action == "selfcheck":
            return {"ok": True, "client_imported": True}
        device = r36.R36()
        if action == "run":
            code, raw = device.run(request["command"])
            return {"ok": True, "code": code, "output": base64.b64encode(raw).decode("ascii")}
        if action == "put":
            count = device.put(request["local"], request["remote"])
            return {"ok": True, "bytes": count}
        raise ValueError(f"unknown operation: {action}")
    except BaseException as error:
        return {"ok": False, "error_type": type(error).__name__, "error": str(error)}
    finally:
        if device is not None:
            try:
                device.close()
            except Exception:
                pass


if __name__ == "__main__":
    print("R36_RESULT=" + json.dumps(main()), flush=True)
