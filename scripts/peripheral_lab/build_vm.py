"""Prepare a workspace-owned portable Linux build VM without touching WSL."""
import argparse
import functools
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "analysis/kernel_build_vm_v1"
QEMU_URL = "https://qemu.weilnetz.de/w64/2026/qemu-w64-setup-20260811.exe"
QEMU_SHA512 = "5bcf9eed634e8575a37b74f445af41a2fe4106da512d0c30c368301d4c105037fdfab40a5287367a28a957624cddebbc8c07e16c88ab6634f554cdf3d16bf543"
ALPINE = "https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/x86_64/netboot/"


class BootHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        resource = urlsplit(self.path).path.lstrip("/")
        if resource not in {"vmlinuz-virt", "initramfs-virt", "modloop-virt",
                            "r36-build.apkovl.tar.gz", "r36-bootstrap.sh"}:
            self.send_error(404)
            return
        super().do_GET()


def download(url, output, expected=None, algorithm="sha256"):
    if output.exists() and (not expected or hashlib.new(algorithm, output.read_bytes()).hexdigest() == expected):
        return
    print("download", url, flush=True)
    partial = output.with_suffix(output.suffix + ".partial")
    with urllib.request.urlopen(url, timeout=90) as response, partial.open("wb") as handle:
        while data := response.read(1024 * 1024):
            handle.write(data)
    if expected:
        assert hashlib.new(algorithm, partial.read_bytes()).hexdigest() == expected, "download digest mismatch"
    partial.replace(output)


def overlay(public_key):
    script = """#!/bin/sh
set -eu
exec >/dev/ttyS0 2>&1
echo R36_BUILD_BOOTSTRAP_STARTED
printf 'nameserver 10.0.2.3\n' >/etc/resolv.conf
relocate_usr() {
    if ! mountpoint -q /usr; then
        test -d /work/root_usr || cp -a /usr /work/root_usr
        mv /usr /usr.ram-old
        mkdir /usr
        mount -o bind /work/root_usr /usr
        /bin/busybox rm -rf /usr.ram-old
    fi
}
if mountpoint -q /work; then relocate_usr; fi
apk add --no-progress e2fsprogs openssh ca-certificates
rc-service modloop status >/dev/null 2>&1 || rc-service modloop start
modprobe ext4
test "$(cat /sys/block/vda/size)" = 16777216
kind="$(blkid -s TYPE -o value /dev/vda || true)"
case "$kind" in ext4) ;; "") mkfs.ext4 -q -F -L R36BUILD /dev/vda ;; *) exit 41 ;; esac
mkdir -p /work
mountpoint -q /work || mount -o noatime /dev/vda /work
mkdir -p /work/apk-cache
ln -snf /work/apk-cache /etc/apk/cache
relocate_usr
mkdir -p /work/ssh-host-keys
if test -f /work/ssh-host-keys/ssh_host_ecdsa_key; then cp -p /work/ssh-host-keys/ssh_host_* /etc/ssh/; fi
ssh-keygen -A
cp -p /etc/ssh/ssh_host_* /work/ssh-host-keys/
rc-service sshd start
apk add --no-progress bash build-base clang lld llvm bison flex bc openssl-dev elfutils-dev perl python3 rsync curl xz git findutils texinfo
apk fix --no-progress llvm20
echo R36_BUILD_READY > /work/READY
clang --print-targets > /work/clang-targets.txt
echo R36_BUILD_READY
"""
    files = {
        "etc/apk/repositories": "https://dl-cdn.alpinelinux.org/alpine/v3.22/main\nhttps://dl-cdn.alpinelinux.org/alpine/v3.22/community\n",
        "etc/network/interfaces": "auto lo\niface lo inet loopback\nauto eth0\niface eth0 inet dhcp\n",
        "etc/local.d/r36.start": script,
        "etc/ssh/sshd_config": "Port 22\nPermitRootLogin prohibit-password\nPubkeyAuthentication yes\nPasswordAuthentication no\nAuthorizedKeysFile .ssh/authorized_keys\nSubsystem sftp internal-sftp\n",
        "root/.ssh/authorized_keys": public_key,
    }
    (WORK / "r36-bootstrap.sh").write_bytes(script.encode())
    with tarfile.open(WORK / "r36-build.apkovl.tar.gz", "w:gz") as archive:
        directory = tarfile.TarInfo("root/.ssh")
        directory.type, directory.mode = tarfile.DIRTYPE, 0o700
        archive.addfile(directory)
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755 if name.endswith(".start") else 0o600 if name.endswith("authorized_keys") else 0o644
            archive.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("etc/runlevels/default/local")
        link.type, link.mode, link.linkname = tarfile.SYMTYPE, 0o777, "/etc/init.d/local"
        archive.addfile(link)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--accel", choices=["tcg", "whpx"], default="tcg")
    parser.add_argument("--refresh-overlay", action="store_true")
    args = parser.parse_args()
    if args.serve:
        handler = functools.partial(BootHandler, directory=str(WORK))
        http.server.ThreadingHTTPServer(("127.0.0.1", 18280), handler).serve_forever()
        return
    if args.refresh_overlay:
        assert (WORK / "ownership.json").exists() and (WORK / "id_ed25519.pub").exists()
        overlay((WORK / "id_ed25519.pub").read_text())
        print("Owned VM bootstrap and overlay refreshed")
        return
    assert WORK.parent.is_dir()
    marker = WORK / "ownership.json"
    if WORK.exists() and not marker.exists():
        raise RuntimeError("pre-existing unowned VM directory; refusing to modify it")
    WORK.mkdir(exist_ok=True)
    if not marker.exists():
        marker.write_text(json.dumps({"owner": "r36 peripheral build VM", "created": time.time()}))
    state_file = WORK / "state.json"
    if state_file.exists():
        raise RuntimeError("VM state already exists; inspect owned processes before another launch")
    installer = WORK / "qemu-installer.exe"
    download(QEMU_URL, installer, QEMU_SHA512, "sha512")
    qemu = WORK / "qemu/qemu-system-x86_64.exe"
    if not qemu.exists():
        subprocess.run([r"C:\Program Files\7-Zip\7z.exe", "x", "-bso0", "-bsp0", "-y", str(installer), "-o" + str(qemu.parent)], check=True)
    assert qemu.exists()
    for name in ("vmlinuz-virt", "initramfs-virt", "modloop-virt"):
        # Netboot files come directly from the official Alpine HTTPS mirror.
        download(ALPINE + name, WORK / name)
    key = WORK / "id_ed25519"
    if not key.exists():
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    overlay(key.with_suffix(".pub").read_text())
    disk = WORK / "work.qcow2"
    if not disk.exists():
        subprocess.run([str(qemu.parent / "qemu-img.exe"), "create", "-f", "qcow2", str(disk), "8G"], check=True)
    http_log = (WORK / "http.log").open("ab")
    server = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--serve"], stdout=http_log, stderr=subprocess.STDOUT)
    command = [str(qemu), "-accel", args.accel, "-m", "1536", "-smp", "2",
               "-display", "none", "-monitor", "none", "-serial", "file:" + str(WORK / "serial.log"),
               "-kernel", str(WORK / "vmlinuz-virt"), "-initrd", str(WORK / "initramfs-virt"),
               "-append", "console=ttyS0,115200 net.ifnames=0 ip=dhcp modules=loop,squashfs,virtio_blk,virtio_net,ext4 alpine_repo=https://dl-cdn.alpinelinux.org/alpine/v3.22/main modloop=http://10.0.2.2:18280/modloop-virt apkovl=http://10.0.2.2:18280/r36-build.apkovl.tar.gz",
               "-drive", "file=" + str(disk) + ",format=qcow2,if=virtio",
               "-netdev", "user,id=buildnet,hostfwd=tcp:127.0.0.1:22222-:22",
               "-device", "virtio-net-pci,netdev=buildnet", "-no-reboot"]
    log = (WORK / "qemu.log").open("ab")
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    state = {"qemu_pid": process.pid, "http_pid": server.pid, "accel": args.accel,
             "ssh_port": 22222, "private_key": str(key), "command": command,
             "disk_bytes": 8 * 1024**3, "qemu_sha512": QEMU_SHA512,
             "netboot_sha256": {name: hashlib.sha256((WORK / name).read_bytes()).hexdigest()
                                  for name in ("vmlinuz-virt", "initramfs-virt", "modloop-virt")}}
    state_file.write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
