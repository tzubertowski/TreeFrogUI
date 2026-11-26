import pytest
from usb_windows_identity import INSTANCE, exact_pnp_ports


def test_only_present_exact_USB_instance_is_eligible():
    valid={'InstanceId':INSTANCE,'Status':'OK','FriendlyName':'USB serial device (COM12)'}
    assert exact_pnp_ports([valid])==['COM12']
    assert exact_pnp_ports(dict(valid,Status='Unknown'))==[]
    assert exact_pnp_ports(dict(valid,InstanceId=INSTANCE+'-OTHER'))==[]
    assert exact_pnp_ports(dict(valid,InstanceId='BTHENUM\\unrelated'))==[]
    assert exact_pnp_ports(dict(valid,FriendlyName='unknown port'))==[]
    with pytest.raises(ValueError):exact_pnp_ports([valid,valid])
