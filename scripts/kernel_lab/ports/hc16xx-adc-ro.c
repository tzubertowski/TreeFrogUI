// SPDX-License-Identifier: GPL-2.0
/* Passive access to SAR result bytes plus legacy /dev/check_adc1 and
 * /dev/check_adc5 character nodes while stock AVP owns conversion setup. */
#include <linux/clk.h>
#include <linux/fs.h>
#include <linux/iio/iio.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/uaccess.h>

#define HC_ADC_REF_CHANNEL      0U
#define HC_ADC_BATTERY_CHANNEL  1U
#define HC_ADC_CHARGE_CHANNEL   5U

struct hc16xx_adc_ro;

struct hc16xx_adc_char_chan {
    struct hc16xx_adc_ro *adc;
    unsigned int channel;
    struct miscdevice misc;
};

struct hc16xx_adc_ro {
    void __iomem *results;
    struct hc16xx_adc_char_chan check_adc1;
    struct hc16xx_adc_char_chan check_adc5;
};

static unsigned int hc16xx_adc_channel_offset(unsigned int ch)
{
    return ch >= 4U ? ch + 2U : ch;
}

static u8 hc16xx_adc_calibrate_byte(u8 sample, u8 ref)
{
    unsigned int scaled;

    if (!ref)
        return sample;
    scaled = ((unsigned int)sample * 241U) / (unsigned int)ref;
    return (u8)(scaled > 255U ? 255U : scaled);
}

static u8 hc16xx_adc_read_calibrated(struct hc16xx_adc_ro *adc, unsigned int ch)
{
    u8 ref = readb(adc->results + hc16xx_adc_channel_offset(HC_ADC_REF_CHANNEL));
    u8 sample = readb(adc->results + hc16xx_adc_channel_offset(ch));

    return hc16xx_adc_calibrate_byte(sample, ref);
}

static int adc_read(struct iio_dev *indio, const struct iio_chan_spec *channel,
                    int *value, int *value2, long mask)
{
    struct hc16xx_adc_ro *adc = iio_priv(indio);
    (void)value2;
    if (mask != IIO_CHAN_INFO_RAW) return -EINVAL;
    *value = readb(adc->results + hc16xx_adc_channel_offset(channel->channel));
    return IIO_VAL_INT;
}

static ssize_t checkadc_char_read(struct file *file, char __user *buf,
                                  size_t count, loff_t *ppos)
{
    struct miscdevice *mdev = file->private_data;
    struct hc16xx_adc_char_chan *ch =
        container_of(mdev, struct hc16xx_adc_char_chan, misc);
    u8 val;

    if (!count)
        return 0;
    val = hc16xx_adc_read_calibrated(ch->adc, ch->channel);
    if (copy_to_user(buf, &val, 1))
        return -EFAULT;
    if (ppos)
        *ppos += 1;
    return 1;
}

static const struct file_operations checkadc_fops = {
    .owner  = THIS_MODULE,
    .read   = checkadc_char_read,
    .llseek = noop_llseek,
};

static void checkadc_deregister(void *data)
{
    struct hc16xx_adc_char_chan *ch = data;
    misc_deregister(&ch->misc);
}

static int checkadc_register(struct device *dev, struct hc16xx_adc_ro *adc,
                             struct hc16xx_adc_char_chan *ch,
                             unsigned int channel, const char *name)
{
    int ret;

    ch->adc = adc;
    ch->channel = channel;
    ch->misc.minor = MISC_DYNAMIC_MINOR;
    ch->misc.name = name;
    ch->misc.fops = &checkadc_fops;
    ch->misc.mode = 0644;
    ret = misc_register(&ch->misc);
    if (ret)
        return ret;
    return devm_add_action_or_reset(dev, checkadc_deregister, ch);
}

#define ADC_CHANNEL(n) { .type = IIO_VOLTAGE, .indexed = 1, .channel = (n), \
                        .info_mask_separate = BIT(IIO_CHAN_INFO_RAW) }
static const struct iio_chan_spec adc_channels[] = {
    ADC_CHANNEL(0), ADC_CHANNEL(1), ADC_CHANNEL(2),
    ADC_CHANNEL(3), ADC_CHANNEL(4), ADC_CHANNEL(5),
};
static const struct iio_info adc_info = { .read_raw = adc_read };

static int adc_probe(struct platform_device *pdev)
{
    struct iio_dev *indio;
    struct hc16xx_adc_ro *adc;
    struct clk *clk;
    int ret;

    indio = devm_iio_device_alloc(&pdev->dev, sizeof(*adc));
    if (!indio) return -ENOMEM;
    adc = iio_priv(indio);
    adc->results = devm_platform_ioremap_resource(pdev, 0);
    if (IS_ERR(adc->results)) return PTR_ERR(adc->results);
    clk = devm_clk_get_enabled(&pdev->dev, NULL);
    if (IS_ERR(clk)) return dev_err_probe(&pdev->dev, PTR_ERR(clk), "ADC clock unavailable\n");
    indio->name = "hc16xx-adc-ro";
    indio->info = &adc_info;
    indio->modes = INDIO_DIRECT_MODE;
    indio->channels = adc_channels;
    indio->num_channels = ARRAY_SIZE(adc_channels);
    ret = devm_iio_device_register(&pdev->dev, indio);
    if (ret)
        return ret;
    ret = checkadc_register(&pdev->dev, adc, &adc->check_adc1,
                            HC_ADC_BATTERY_CHANNEL, "check_adc1");
    if (ret)
        return ret;
    return checkadc_register(&pdev->dev, adc, &adc->check_adc5,
                             HC_ADC_CHARGE_CHANNEL, "check_adc5");
}

static const struct of_device_id adc_match[] = {
    { .compatible = "r36lab,hc16xx-adc-ro" }, { }
};
MODULE_DEVICE_TABLE(of, adc_match);
static struct platform_driver adc_driver = {
    .probe = adc_probe,
    .driver = { .name = "r36-hc16xx-adc-ro", .of_match_table = adc_match },
};
module_platform_driver(adc_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only HC16xx SAR results while stock AVP owns conversion setup");
