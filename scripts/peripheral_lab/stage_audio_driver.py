"""Stage native ALSA reference as an opt-in, silent board diagnostic source.

No hardware accessed. No foreign firmware or syscore is installed. The driver is
kept disabled in DT; actual takeover requires explicit module allow_takeover=1.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REV = "bff93e84fe79c9e67bde284dfe4d58054b62282b"


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("unexpected source anchor: " + old[:80])
    return text.replace(old, new, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error("output must be new with an existing parent")
    reference = ROOT / "analysis/gb350-linux-reference"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=reference).decode().strip() == REV
    source = reference / "kernel/sound/hichip/hc16xx-i2s.c"
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", "kernel/sound/hichip/hc16xx-i2s.c"], cwd=reference, check=True)
    text = source.read_text()
    text = once(text, '#include <linux/soc/hichip/gb350-syscore.h>', '''#include <linux/of.h>

static bool allow_takeover;
module_param(allow_takeover, bool, 0400);
MODULE_PARM_DESC(allow_takeover, "Explicit ownership takeover; keep false until board acceptance");''')
    text = once(text, '#define GAIN_DEFAULT\t\t32\t/* quiet; stock "volume 8" was 21 */',
                '#define GAIN_DEFAULT\t\t0\t/* silent initial bring-up */')
    begin = text.index('static const char * const hc16xx_speaker_modes[]')
    end = text.index('static const struct snd_kcontrol_new hc16xx_controls[]', begin)
    text = text[:begin] + '/* No speaker-policy mixer: stock AVP/syscore ownership is not yet ported. */\n\n' + text[end:]
    block = '''\t}, {
		.iface	= SNDRV_CTL_ELEM_IFACE_MIXER,
		.name	= "Speaker Mode",
		.info	= hc16xx_speaker_info,
		.get	= hc16xx_speaker_get,
		.put	= hc16xx_speaker_put,
'''
    text = once(text, block, '')
    # Keep the actual PCM operations; only board identity/policy/lifecycle change.
    text = once(text, '\tret = snd_devm_card_new(dev, SNDRV_DEFAULT_IDX1, "GB350", THIS_MODULE, sizeof(*a), &card);', '''\tif (!allow_takeover)
		return dev_err_probe(dev, -EPERM, "audio ownership not approved\\n");
	res = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!res || res->start != 0x1880a000 || resource_size(res) != 0x1000)
		return -EINVAL;
	res = platform_get_resource(pdev, IORESOURCE_MEM, 1);
	if (!res || res->start != 0x18800000 || resource_size(res) != 0x500)
		return -EINVAL;
	ret = snd_devm_card_new(dev, SNDRV_DEFAULT_IDX1, "R36LAB", THIS_MODULE, sizeof(*a), &card);''')
    text = once(text, '\ta->gain = GAIN_DEFAULT;', '\ta->gain = GAIN_DEFAULT;\n\ta->mute = true;')
    # No callback may race an uninitialised a->pcm. ISR is benign until card setup.
    text = once(text, 'struct snd_pcm_substream *ss = a->pcm->streams[SNDRV_PCM_STREAM_PLAYBACK].substream;',
                'struct snd_pcm_substream *ss = a->pcm ? a->pcm->streams[SNDRV_PCM_STREAM_PLAYBACK].substream : NULL;')
    text = text.replace('strscpy(card->shortname, "GB350");', 'strscpy(card->shortname, "R36 laboratory");')
    text = text.replace('"GB350 I2S (HiChip HC16xx) + CS4344"', '"R36 HC16E310 I2S + CS4344 (diagnostic)"')
    text = text.replace('"GB350 I2S"', '"R36 I2S"')
    text = text.replace('"hichip,hc16xx-i2so"', '"r36lab,hc16e310-i2so"')
    text = text.replace('.name\t\t= "hc16xx-i2s",', '.name\t\t= "r36-hc16xx-i2s",')
    text = once(text, '\thc16xx_i2s_hw_init(a);', '''\t/* Refuse takeover of a running DMA engine, even with module opt-in. */
	if (readl(a->regs + I2SO_CTRL) & I2SO_CTRL_RUN)
		return dev_err_probe(dev, -EBUSY, "old audio DMA is active\\n");
	hc16xx_i2s_hw_init(a);''')
    health = '''static ssize_t health_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct hc16xx_i2s *a = dev_get_drvdata(dev);
	return sysfs_emit(buf, "control=%08x dma=%08x config=%08x rd=%u wr=%u gain=%u mute=%u\\n",
		readl(a->regs + I2SO_CTRL), readl(a->regs + I2SO_BUF), readl(a->regs + I2SO_CFG),
		readw(a->regs + I2SO_RD), readw(a->regs + I2SO_WR),
		readb(a->regs + I2SO_GAIN), a->mute);
}
static DEVICE_ATTR_RO(health);
static struct attribute *r36_audio_attrs[] = { &dev_attr_health.attr, NULL };
ATTRIBUTE_GROUPS(r36_audio);

'''
    text = once(text, 'static const struct of_device_id hc16xx_i2s_of_match[] = {', health + 'static const struct of_device_id hc16xx_i2s_of_match[] = {')
    text = once(text, '.name\t\t= "r36-hc16xx-i2s",', '.name\t\t= "r36-hc16xx-i2s",\n\t\t.dev_groups = r36_audio_groups,')
    shutdown = '''static void r36_audio_quiesce(struct platform_device *pdev)
{
	struct hc16xx_i2s *a = platform_get_drvdata(pdev);
	if (!a) return;
	writeb(0, a->regs + I2SO_GAIN);
	writel(readl(a->regs + I2SO_CTRL) & ~I2SO_CTRL_RUN, a->regs + I2SO_CTRL);
	writel(I2SO_INT_STATUS, a->regs + I2SO_INT);
	writel(I2SO_INT2_STATUS, a->regs + I2SO_INT2);
	writew(0, a->regs + I2SO_WR);
}

'''
    text = once(text, 'static struct platform_driver hc16xx_i2s_driver = {', shutdown + 'static struct platform_driver hc16xx_i2s_driver = {\n\t.remove = r36_audio_quiesce,\n\t.shutdown = r36_audio_quiesce,')
    if 'gb350_syscore_send' in text or 'Speaker Mode' in text:
        raise ValueError("foreign syscore dependency remains")
    text += '''
/* Match direct userspace PCM ioctls to this exact kernel UAPI build. */
const u32 r36_audio_abi[] __used __section(".r36audio") = {
    0x52334142, 1, sizeof(struct snd_pcm_hw_params), sizeof(struct snd_pcm_sw_params),
    sizeof(struct snd_xferi), sizeof(struct snd_pcm_info),
    SNDRV_PCM_IOCTL_HW_PARAMS, SNDRV_PCM_IOCTL_SW_PARAMS,
    SNDRV_PCM_IOCTL_WRITEI_FRAMES, SNDRV_PCM_IOCTL_INFO,
    SNDRV_PCM_IOCTL_PREPARE, SNDRV_PCM_IOCTL_DROP
};
'''
    args.out.mkdir()
    (args.out / "r36_hc16xx_i2s.c").write_text(text, encoding="utf-8", newline="\n")
    (args.out / "Makefile").write_text("obj-m += r36_hc16xx_i2s.o\n")
    (args.out / "r36-audio.dts").write_text('''// SPDX-License-Identifier: GPL-2.0
/ {
    r36_audio: sound@1880a000 {
        compatible = "r36lab,hc16e310-i2so";
        reg = <0x1880a000 0x1000 0x18800000 0x500>;
        interrupt-parent = <&intc>;
        interrupts = <5>;
        status = "disabled";
    };
};
''')
    receipt = {"source_commit": REV, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "default_enabled": False, "explicit_takeover_required": True,
               "foreign_firmware_required": False, "speaker_gpio_owned": False,
               "initial_gain": 0, "initial_mute": True, "hardware_verified": False,
               "built": False, "deployed": False,
               "limitations": ["AVP audio ownership must be measured before enabling", "GPIO19 amplifier and GPIO15 headphone policy not implemented", "probe still resets audio and changes audio pad clocks after explicit opt-in", "PCM/IRQ/DMA require hardware acceptance"],
               "files_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.out.iterdir()}}
    (args.out / "port_source.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
