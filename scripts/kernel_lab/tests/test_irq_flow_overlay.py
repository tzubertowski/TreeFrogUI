from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[1]


def apply_fragment(root):
    script = (LAB / "integrate_ports.py").read_text()
    begin = script.index('irq_file = src / "drivers/irqchip/irq-hc16xx-intc.c"')
    end = script.index("# A breadcrumb before", begin)
    exec(compile(script[begin:end], "irq-overlay-fragment", "exec"), {"src": root})


def test_irq_overlay_changes_only_flow_and_is_idempotent(tmp_path):
    path = tmp_path / "drivers/irqchip/irq-hc16xx-intc.c"
    path.parent.mkdir(parents=True)
    original = "before\nirq_set_chip_and_handler(irq, &hc16xx_irq_chip, handle_percpu_irq);\nafter\n"
    path.write_text(original)
    apply_fragment(tmp_path)
    expected = original.replace("handle_percpu_irq", "handle_simple_irq")
    assert path.read_text() == expected
    apply_fragment(tmp_path)
    assert path.read_text() == expected


def test_unrecognized_irq_flow_fails_closed(tmp_path):
    path = tmp_path / "drivers/irqchip/irq-hc16xx-intc.c"
    path.parent.mkdir(parents=True)
    path.write_text("different upstream driver\n")
    with pytest.raises(ValueError, match="IRQ flow handler"):
        apply_fragment(tmp_path)
    assert path.read_text() == "different upstream driver\n"
