"""Private MUSB IRQ-lifecycle and host/OTG glue fixes."""
import re


def patch_musb_irq_lifecycle(text):
    before = text
    for name in ('hc16xx_musb_enable', 'hc16xx_musb_disable'):
        # These wrappers only operate the Linux IRQ depth, not extra SoC gates.
        # Core start/stop already masks the controller and calls disable under
        # musb->lock. disable_irq() may wait for an ISR taking the same lock.
        pattern = (r'static void ' + name + r'\(struct musb \*musb\)\n\{\n'
                   r'.*?\n\}\n\n')
        matches = list(re.finditer(pattern, text, re.S))
        if matches:
            if len(matches) != 1:
                raise ValueError('duplicate USB IRQ callback')
            block = matches[0].group()
            call = 'enable_irq(glue->irq);' if name.endswith('_enable') else 'disable_irq(glue->irq);'
            if block.count(call) != 1 or 'writel' in block or 'writeb' in block:
                raise ValueError('USB IRQ callback has changed semantics')
            text = text[:matches[0].start()] + text[matches[0].end():]
        binding = '.enable\t\t= hc16xx_musb_enable,' if name.endswith('_enable') else '.disable\t= hc16xx_musb_disable,'
        if binding in text:
            text = text.replace('\t' + binding + '\n', '', 1)
        elif name in text:
            raise ValueError('unexpected USB callback binding')
    old = '\tdisable_irq(glue->irq);\n\treturn 0;\n\nerr_pdev:'
    new = '\t/* Core owns IRQ registration and controller interrupt masking. */\n\treturn 0;\n\nerr_pdev:'
    if text.count(old) == 1:
        text = text.replace(old, new, 1)
    elif text.count(new) != 1:
        raise ValueError('unexpected post-child USB IRQ disable')
    if 'enable_irq(glue->irq)' in text or 'disable_irq(glue->irq)' in text:
        raise ValueError('unbalanced IRQ-depth calls remain')
    if text == before and new not in text:
        raise ValueError('USB IRQ patch not applied')
    return text


_STRUCT_OLD = (
    '\tint\t\t\tirq;\n'
    '\tint\t\t\tdma_irq;\n'
    '};'
)
_STRUCT_NEW = (
    '\tint\t\t\tirq;\n'
    '\tint\t\t\tdma_irq;\n'
    '\tu8\t\t\trole_mode;\n'
    '};'
)

_PHY_POWER_OLD = (
    'static void hc16xx_set_phy_power(struct hc16xx_glue *glue, bool on)\n'
    '{\n'
    '\tu32 reg, mode = 0;\n\n'
    '\tif (!glue->musb->is_host)\n'
    '\t\tmode = UTMI_PERIPHERAL_MODE;\n\n'
    '\tif (on) {\n'
    '\t\treg = readl(glue->musb->mregs + USB_O_UTMI);\n'
    '\t\treg &= ~(UTMI_DISABLE_OTG | UTMI_PERIPHERAL_MODE);\n'
    '\t\twritel(reg, glue->musb->mregs + USB_O_UTMI);\n\n'
    '\t\treg = readl(glue->musb->mregs + USB_O_UTMI);\n'
    '\t\treg |= UTMI_DISABLE_PHY | UTMI_DISABLE_OTG_BITS;\n'
    '\t\twritel(reg, glue->musb->mregs + USB_O_UTMI);\n'
    '\t\tudelay(900);\n'
    '\t\treg = readl(glue->musb->mregs + USB_O_UTMI);\n'
    '\t\treg &= ~(UTMI_DISABLE_PHY | UTMI_PERIPHERAL_MODE);\n'
    '\t\treg |= mode;\n'
    '\t\twritel(reg, glue->musb->mregs + USB_O_UTMI);\n'
    '\t} else {\n'
    '\t\treg = readl(glue->musb->mregs + USB_O_UTMI);\n'
    '\t\treg |= UTMI_DISABLE_PHY | UTMI_DISABLE_OTG_BITS;\n'
    '\t\twritel(reg, glue->musb->mregs + USB_O_UTMI);\n\n'
    '\t\treg = readl(glue->musb->mregs + USB_O_UTMI);\n'
    '\t\treg &= ~(UTMI_DISABLE_OTG | UTMI_PERIPHERAL_MODE);\n'
    '\t\twritel(reg, glue->musb->mregs + USB_O_UTMI);\n'
    '\t}'
)
_PHY_POWER_NEW = (
    'static void hc16xx_set_phy_power(struct hc16xx_glue *glue, bool on)\n'
    '{\n'
    '\tu8 reg, mode = 0;\n\n'
    '\tif (glue->role_mode != MUSB_HOST)\n'
    '\t\tmode = UTMI_PERIPHERAL_MODE;\n\n'
    '\tif (on) {\n'
    '\t\treg = readb(glue->musb->mregs + USB_O_UTMI);\n'
    '\t\treg &= ~(UTMI_DISABLE_OTG | UTMI_PERIPHERAL_MODE);\n'
    '\t\twriteb(reg, glue->musb->mregs + USB_O_UTMI);\n\n'
    '\t\treg = readb(glue->musb->mregs + USB_O_UTMI);\n'
    '\t\treg |= UTMI_DISABLE_PHY | UTMI_DISABLE_OTG_BITS;\n'
    '\t\twriteb(reg, glue->musb->mregs + USB_O_UTMI);\n'
    '\t\tudelay(900);\n'
    '\t\treg = readb(glue->musb->mregs + USB_O_UTMI);\n'
    '\t\treg &= ~(UTMI_DISABLE_PHY | UTMI_PERIPHERAL_MODE);\n'
    '\t\treg |= mode;\n'
    '\t\twriteb(reg, glue->musb->mregs + USB_O_UTMI);\n'
    '\t} else {\n'
    '\t\treg = readb(glue->musb->mregs + USB_O_UTMI);\n'
    '\t\treg |= UTMI_DISABLE_PHY | UTMI_DISABLE_OTG_BITS;\n'
    '\t\twriteb(reg, glue->musb->mregs + USB_O_UTMI);\n\n'
    '\t\treg = readb(glue->musb->mregs + USB_O_UTMI);\n'
    '\t\treg &= ~(UTMI_DISABLE_OTG | UTMI_PERIPHERAL_MODE);\n'
    '\t\twriteb(reg, glue->musb->mregs + USB_O_UTMI);\n'
    '\t}'
)

_SET_MODE_OLD = (
    '\tswitch (mode) {\n'
    '\tcase MUSB_HOST:\n'
    '\t\twriteb(BIT(7), musb->mregs + USB_O_UTMI);\n'
    '\t\tudelay(1);\n\n'
    '\t\treg = readb(musb->mregs + USB_O_UTMI);\n'
    '\t\t/* disable OTG function */\n'
    '\t\treg |= UTMI_DISABLE_OTG_BITS;\n'
    '\t\t/* set as host mode */\n'
    '\t\treg &= ~UTMI_PERIPHERAL_MODE;\n'
    '\t\twriteb(reg, musb->mregs + USB_O_UTMI);\n'
    '\t\tphy_set_mode(musb->phy, PHY_MODE_USB_HOST);\n'
    '\t\tMUSB_HST_MODE(musb);\n'
    '\t\tbreak;\n\n'
    '\tcase MUSB_PERIPHERAL:\n'
    '\t\twriteb(BIT(7) | UTMI_PERIPHERAL_MODE, musb->mregs + USB_O_UTMI);\n'
    '\t\tudelay(1);\n\n'
    '\t\treg = readb(musb->mregs + USB_O_UTMI);\n'
    '\t\t/* disable OTG function */\n'
    '\t\treg |= UTMI_DISABLE_OTG_BITS;\n'
    '\t\t/* set as peripheral mode */\n'
    '\t\treg |= UTMI_PERIPHERAL_MODE;\n'
    '\t\twriteb(reg, musb->mregs + USB_O_UTMI);\n'
    '\t\tphy_set_mode(musb->phy, PHY_MODE_USB_DEVICE);\n'
    '\t\tMUSB_DEV_MODE(musb);\n'
    '\t\tbreak;\n\n'
    '\tcase MUSB_OTG:\n'
    '\t\tdev_warn(dev, "OTG mode does not supported\\n");\n'
    '\t\treturn -EOPNOTSUPP;\n\n'
    '\tdefault:\n'
    '\t\tdev_err(dev, "unknown USB mode %u\\n", mode);\n'
    '\t\treturn -EINVAL;\n'
    '\t}\n\n'
    '\thc16xx_set_phy_power(glue, true);\n'
    '\treturn 0;'
)
_SET_MODE_NEW = (
    '\tswitch (mode) {\n'
    '\tcase MUSB_OTG:\n'
    '\tcase MUSB_HOST:\n'
    '\t\tglue->role_mode = MUSB_HOST;\n'
    '\t\twriteb(BIT(7), musb->mregs + USB_O_UTMI);\n'
    '\t\tudelay(1);\n\n'
    '\t\treg = readb(musb->mregs + USB_O_UTMI);\n'
    '\t\t/* disable OTG function */\n'
    '\t\treg |= UTMI_DISABLE_OTG_BITS;\n'
    '\t\t/* set as host mode */\n'
    '\t\treg &= ~UTMI_PERIPHERAL_MODE;\n'
    '\t\twriteb(reg, musb->mregs + USB_O_UTMI);\n'
    '\t\tphy_set_mode(musb->phy, PHY_MODE_USB_HOST);\n'
    '\t\tMUSB_HST_MODE(musb);\n'
    '\t\tbreak;\n\n'
    '\tcase MUSB_PERIPHERAL:\n'
    '\t\tglue->role_mode = MUSB_PERIPHERAL;\n'
    '\t\twriteb(BIT(7) | UTMI_PERIPHERAL_MODE, musb->mregs + USB_O_UTMI);\n'
    '\t\tudelay(1);\n\n'
    '\t\treg = readb(musb->mregs + USB_O_UTMI);\n'
    '\t\t/* disable OTG function */\n'
    '\t\treg |= UTMI_DISABLE_OTG_BITS;\n'
    '\t\t/* set as peripheral mode */\n'
    '\t\treg |= UTMI_PERIPHERAL_MODE;\n'
    '\t\twriteb(reg, musb->mregs + USB_O_UTMI);\n'
    '\t\tphy_set_mode(musb->phy, PHY_MODE_USB_DEVICE);\n'
    '\t\tMUSB_DEV_MODE(musb);\n'
    '\t\tbreak;\n\n'
    '\tdefault:\n'
    '\t\tdev_err(dev, "unknown USB mode %u\\n", mode);\n'
    '\t\treturn -EINVAL;\n'
    '\t}\n\n'
    '\thc16xx_set_phy_power(glue, true);\n'
    '\tif (glue->role_mode == MUSB_HOST) {\n'
    '\t\tmusb_writeb(musb->mregs, MUSB_DEVCTL,\n'
    '\t\t\t    musb_readb(musb->mregs, MUSB_DEVCTL) & ~MUSB_DEVCTL_SESSION);\n'
    '\t\tmdelay(1);\n'
    '\t\tmusb_writeb(musb->mregs, MUSB_DEVCTL,\n'
    '\t\t\t    musb_readb(musb->mregs, MUSB_DEVCTL) | MUSB_DEVCTL_SESSION);\n'
    '\t} else {\n'
    '\t\tmusb_writeb(musb->mregs, MUSB_DEVCTL,\n'
    '\t\t\t    musb_readb(musb->mregs, MUSB_DEVCTL) & ~MUSB_DEVCTL_SESSION);\n'
    '\t}\n'
    '\treturn 0;'
)

_PDATA_OLD = '\tglue->musb_pdev->dev.platform_data = &hc16xx_musb_data;'
_PDATA_NEW = (
    '\t{\n'
    '\t\tstruct musb_hdrc_platform_data pdata = hc16xx_musb_data;\n\n'
    '\t\tswitch (usb_get_dr_mode(dev)) {\n'
    '\t\tcase USB_DR_MODE_HOST:\n'
    '\t\t\tpdata.mode = MUSB_HOST;\n'
    '\t\t\tbreak;\n'
    '\t\tcase USB_DR_MODE_OTG:\n'
    '\t\t\tpdata.mode = MUSB_OTG;\n'
    '\t\t\tbreak;\n'
    '\t\tdefault:\n'
    '\t\t\tpdata.mode = MUSB_PERIPHERAL;\n'
    '\t\t\tbreak;\n'
    '\t\t}\n'
    '\t\tret = platform_device_add_data(glue->musb_pdev, &pdata,\n'
    '\t\t\t\t\t       sizeof(pdata));\n'
    '\t\tif (ret)\n'
    '\t\t\tgoto err_pdev;\n'
    '\t}'
)


def _replace_once_or_keep(text, old, new, label):
    if text.count(old) == 1:
        return text.replace(old, new, 1)
    if text.count(new) == 1:
        return text
    raise ValueError('unexpected HC16xx USB glue block: ' + label)


def patch_musb_host_otg_support(text):
    text = _replace_once_or_keep(text, _STRUCT_OLD, _STRUCT_NEW, 'glue struct')
    text = _replace_once_or_keep(text, _PHY_POWER_OLD, _PHY_POWER_NEW, 'hc16xx_set_phy_power')
    text = _replace_once_or_keep(text, _SET_MODE_OLD, _SET_MODE_NEW, 'hc16xx_musb_set_mode')
    text = _replace_once_or_keep(text, _PDATA_OLD, _PDATA_NEW, 'platform_data mode')
    return text
