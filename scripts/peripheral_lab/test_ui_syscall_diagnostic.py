from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_syscall_inspection_is_readonly_and_same_child_only():
    text=(ROOT/'scripts/peripheral_lab/ui_console_init.c').read_text()
    assert '/task/%.32s/syscall' in text
    assert 'number==4166&&address' in text
    assert 'memory=open(path,O_RDONLY|O_CLOEXEC)' in text
    assert 'pread(memory,request,sizeof(request),(off_t)address)' in text
    assert 'pwrite(' not in text and 'ptrace(' not in text
    assert '#define _FILE_OFFSET_BITS 64' in text
    assert 'ui_sleep_request tid=' in text
