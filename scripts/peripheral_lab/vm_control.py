"""Restart only the recorded, workspace-owned QEMU VM and expose its console."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import time
import sys

import psutil
from build_vm import WORK, overlay


def console(command, interrupt=False):
    with socket.create_connection(("127.0.0.1", 22223), timeout=5) as connection:
        connection.settimeout(1)
        connection.sendall((b"\x03" if interrupt else b"") + b"\nroot\n")
        time.sleep(1)
        connection.sendall(command.encode() + b"; echo R36_CONSOLE_COMMAND_END\n")
        output = bytearray()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                block = connection.recv(65536)
                if not block: break
                output.extend(block)
                if output.count(b"R36_CONSOLE_COMMAND_END") >= 2: break
            except socket.timeout:
                continue
        print(output.decode("utf-8", "replace"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restart-owned", action="store_true")
    parser.add_argument("--console")
    parser.add_argument("--interrupt", action="store_true", help="interrupt the owned VM serial foreground command")
    parser.add_argument("--restart-http-owned", action="store_true")
    args = parser.parse_args()
    if args.restart_http_owned:
        state_file = WORK / "state.json"
        state = json.loads(state_file.read_text())
        process = psutil.Process(state["http_pid"])
        assert "--serve" in process.cmdline() and any(arg.endswith("build_vm.py") for arg in process.cmdline())
        process.terminate()
        process.wait(timeout=10)
        log = (WORK / "http.log").open("ab")
        child = subprocess.Popen([sys.executable, str(Path(__file__).with_name("build_vm.py")), "--serve"], stdout=log, stderr=subprocess.STDOUT)
        state["http_pid"] = child.pid
        state_file.write_text(json.dumps(state, indent=2) + "\n")
        print("Owned boot HTTP restarted:", child.pid)
        return
    if args.console:
        console(args.console, args.interrupt)
        return
    if not args.restart_owned:
        parser.error("select --restart-owned or --console")
    state_file = WORK / "state.json"
    state = json.loads(state_file.read_text())
    process = psutil.Process(state["qemu_pid"])
    assert Path(process.exe()).resolve() == Path(state["command"][0]).resolve()
    assert str(WORK / "work.qcow2") in " ".join(process.cmdline())
    process.terminate()
    process.wait(timeout=15)
    overlay((WORK / "id_ed25519.pub").read_text())
    command = state["command"].copy()
    index = command.index("-serial")
    old_log = state.get("serial_log", command[index + 1])
    del command[index:index + 2]
    if "-chardev" in command:
        index = command.index("-chardev")
        assert "id=serial0," in command[index + 1]
        del command[index:index + 2]
    serial = WORK / ("serial_restart_" + str(int(time.time())) + ".log")
    command += ["-chardev", "socket,id=serial0,host=127.0.0.1,port=22223,server=on,wait=off,logfile=" + serial.as_posix(), "-serial", "chardev:serial0"]
    log = (WORK / "qemu.log").open("ab")
    for acceleration in ("whpx", "tcg"):
        command[command.index("-accel") + 1] = acceleration
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        time.sleep(4)
        if child.poll() is None:
            break
    else:
        raise RuntimeError("owned build VM did not start; inspect qemu.log")
    state.setdefault("restarts", []).append({"previous_pid": state["qemu_pid"], "previous_serial": old_log})
    state.update(qemu_pid=child.pid, command=command, accel=acceleration, serial_log=str(serial))
    state_file.write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps({"qemu_pid": child.pid, "accel": acceleration, "serial_log": str(serial)}, indent=2))


if __name__ == "__main__":
    main()
