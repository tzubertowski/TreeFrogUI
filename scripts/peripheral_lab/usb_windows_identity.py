"""Resolve only the currently present exact R36 CDC PnP instance on Windows.

No serial port is opened by this helper. Presence is required: cached devnodes
must never be treated as live enumeration. Exact IDs prevent a VID/PID-only match
from attaching to a different Linux gadget or a Bluetooth serial port.
"""
import json
import re
import subprocess

INSTANCE = r'USB\VID_1D6B&PID_0104\R36LAB-CDC-DIAG'


def exact_pnp_ports(rows):
    ports = []
    if isinstance(rows, dict): rows = [rows]
    for row in rows or []:
        if row.get('InstanceId', '').upper() != INSTANCE.upper() or row.get('Status') != 'OK':
            continue
        match = re.search(r'\((COM[0-9]+)\)$', row.get('FriendlyName', ''))
        if match: ports.append(match.group(1))
    if len(ports) > 1: raise ValueError('ambiguous present diagnostic PnP device')
    return ports


def present_ports():
    import ctypes
    from ctypes import wintypes
    import winreg
    api = ctypes.WinDLL('cfgmgr32')
    locate = api.CM_Locate_DevNodeW
    locate.argtypes = [ctypes.POINTER(wintypes.ULONG), wintypes.LPWSTR, wintypes.ULONG]
    locate.restype = wintypes.ULONG
    status = api.CM_Get_DevNode_Status
    status.argtypes = [ctypes.POINTER(wintypes.ULONG), ctypes.POINTER(wintypes.ULONG), wintypes.ULONG, wintypes.ULONG]
    status.restype = wintypes.ULONG
    dev, flags, problem = wintypes.ULONG(), wintypes.ULONG(), wintypes.ULONG()
    # NORMAL (zero) only locates a present devnode, unlike PHANTOM lookup.
    result = locate(ctypes.byref(dev), ctypes.create_unicode_buffer(INSTANCE), 0)
    if result == 0x0d: return []  # CR_NO_SUCH_DEVNODE
    if result != 0: raise RuntimeError(f'cannot locate diagnostic PnP node: {result:#x}')
    result = status(ctypes.byref(flags), ctypes.byref(problem), dev, 0)
    if result != 0: raise RuntimeError(f'cannot inspect diagnostic PnP node: {result:#x}')
    if problem.value or not flags.value & 0x00000008: return []  # DN_STARTED
    key = 'SYSTEM\\CurrentControlSet\\Enum\\' + INSTANCE + r'\Device Parameters'
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
            port, kind = winreg.QueryValueEx(handle, 'PortName')
    except FileNotFoundError:
        return []
    if kind != winreg.REG_SZ or not re.fullmatch(r'COM[0-9]+', port):
        raise RuntimeError('diagnostic PnP PortName malformed')
    return [port]
