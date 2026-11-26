// SPDX-License-Identifier: GPL-2.0
/* Opt-in, one-shot polling transport bring-up. No callback/ioctl proxy ABI. */
#include <linux/delay.h>
#include <linux/dma-mapping.h>
#include <linux/io.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <asm/addrspace.h>
#include "../ports/amprpc-mailbox-plan.h"
#include "../ports/amprpc-open-wire.h"

struct r36_amp {
    void __iomem *tx, *rx;
    u32 *packet;
    dma_addr_t physical;
    struct mutex lock;
    bool published;
    char report[256];
};

static int wait_clear(void __iomem *reg, u32 mask)
{
    s64 deadline = ktime_get_ns() + 100 * NSEC_PER_MSEC;
    do {
        if (!(readl(reg) & mask)) return 0;
        usleep_range(1000, 2000);
    } while (ktime_get_ns() < deadline);
    return -ETIMEDOUT;
}

static int roundtrip(struct r36_amp *amp, s32 *remote)
{
    u32 pointer = (u32)CKSEG1ADDR(amp->physical);
    bool released = false, received = false;
    s64 deadline;
    unsigned int i;

    if (amp->published) return -EALREADY;
    for (i = 0; i < 8; i++) {
        void __iomem *tx = amp->tx + 32 * i;
        if ((readl(tx + 8) & R36_AMP_PENDING_MASK) ||
            readl(amp->rx + 32 * i + 12) || (readl(tx) & 1)) return -EBUSY;
    }
    memset(amp->packet, 0, PAGE_SIZE);
    if (r36_amp_open_packet(amp->packet, pointer + 0x100,
                           "/dev/r36_probe_no_such_device", 0, 0)) return -EINVAL;
    dma_wmb();
    for (i = 0; i < 8; i++)
        writel(i < 4 ? 0x10002 : 0x101, amp->tx + 32 * i + 8);
    for (i = 0; i < 8; i++)
        if (wait_clear(amp->tx + 32 * i + 8, R36_AMP_PENDING_MASK)) return -ETIMEDOUT;
    writel(pointer, amp->tx + 12);
    if (readl(amp->tx + 12) != pointer) return -EIO;
    amp->published = true;
    dma_wmb();
    writel(readl(amp->tx) | 1, amp->tx);
    deadline = ktime_get_ns() + 8LL * NSEC_PER_SEC;
    do {
        for (i = 0; i < 8; i++) {
            void __iomem *tx = amp->tx + 32 * i;
            void __iomem *rx = amp->rx + 32 * i;
            u32 status = readl(tx + 8), data = readl(rx + 12);
            struct r36_amp_irq_plan plan = r36_amp_plan_irq(i, status, data);
            if (plan.action == R36_AMP_UNEXPECTED_PENDING) return -EPROTO;
            if (plan.action == R36_AMP_RELEASE_TX) {
                if (i) return -EBUSY;
                writel(plan.acknowledge, tx + 8);
                if (wait_clear(tx + 8, R36_AMP_TX_RELEASE_PENDING)) return -ETIMEDOUT;
                released = true;
            } else if (plan.action == R36_AMP_RECEIVE_MESSAGE) {
                if ((data & 0x1fffffff) != amp->physical ||
                    (data >> 29) < 4 || (data >> 29) > 5) return -EBUSY;
                dma_rmb();
                if (READ_ONCE(amp->packet[0]) != 2 || READ_ONCE(amp->packet[1]) != 0x1000 ||
                    READ_ONCE(amp->packet[2]) != 3) return -EBADMSG;
                *remote = READ_ONCE(amp->packet[4]);
                writel(0, rx + 12);
                if (wait_clear(rx + 12, 0xffffffff)) return -ETIMEDOUT;
                writel(plan.acknowledge, tx + 8);
                if (wait_clear(tx + 8, R36_AMP_RX_MESSAGE_PENDING)) return -ETIMEDOUT;
                writel(1, tx + 4);
                WRITE_ONCE(amp->packet[2], 4);
                dma_wmb();
                received = true;
            }
        }
        if (received && released) return *remote < 0 ? 0 : -EPROTO;
        usleep_range(1000, 2000);
    } while (ktime_get_ns() < deadline);
    return -ETIMEDOUT;
}

static ssize_t last_result_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    struct r36_amp *amp = dev_get_drvdata(dev);
    ssize_t size;
    mutex_lock(&amp->lock);
    size = sysfs_emit(buf, "%s", amp->report);
    mutex_unlock(&amp->lock);
    return size;
}
static DEVICE_ATTR_RO(last_result);

static ssize_t test_roundtrip_store(struct device *dev, struct device_attribute *attr,
                                   const char *buf, size_t count)
{
    struct r36_amp *amp = dev_get_drvdata(dev);
    s32 remote = 0;
    int rc;
    if (!sysfs_streq(buf, "1")) return -EINVAL;
    if (!mutex_trylock(&amp->lock)) return -EBUSY;
    rc = roundtrip(amp, &remote);
    snprintf(amp->report, sizeof(amp->report),
             "result=%s rc=%d remote=%d packet_phys=%pad retained_until_reset=%u\n",
             rc ? "FAIL" : "PASS", rc, remote, &amp->physical, amp->published);
    mutex_unlock(&amp->lock);
    return rc ? rc : count;
}
static DEVICE_ATTR_WO(test_roundtrip);

static struct attribute *r36_amp_attrs[] = {
    &dev_attr_last_result.attr, &dev_attr_test_roundtrip.attr, NULL,
};
ATTRIBUTE_GROUPS(r36_amp);

static int r36_amp_probe(struct platform_device *pdev)
{
    struct r36_amp *amp;
    struct resource *tx = platform_get_resource(pdev, IORESOURCE_MEM, 0);
    struct resource *rx = platform_get_resource(pdev, IORESOURCE_MEM, 1);
    int rc = dma_set_mask_and_coherent(&pdev->dev, DMA_BIT_MASK(32));
    if (rc) return rc;
    if (!tx || !rx || tx->start != 0x18800800 || rx->start != 0x18866800 ||
        resource_size(tx) != 0x100 || resource_size(rx) != 0x100) return -EINVAL;
    amp = devm_kzalloc(&pdev->dev, sizeof(*amp), GFP_KERNEL);
    if (!amp) return -ENOMEM;
    amp->tx = devm_platform_ioremap_resource(pdev, 0);
    if (IS_ERR(amp->tx)) return PTR_ERR(amp->tx);
    amp->rx = devm_platform_ioremap_resource(pdev, 1);
    if (IS_ERR(amp->rx)) return PTR_ERR(amp->rx);
    amp->packet = dma_alloc_coherent(&pdev->dev, PAGE_SIZE, &amp->physical, GFP_KERNEL);
    if (!amp->packet) return -ENOMEM;
    if (amp->physical < 0x100000 || amp->physical + PAGE_SIZE > 0x02f91000) {
        dma_free_coherent(&pdev->dev, PAGE_SIZE, amp->packet, amp->physical);
        return -ERANGE;
    }
    mutex_init(&amp->lock);
    strscpy(amp->report, "result=NOT_RUN hardware_validated=0\n", sizeof(amp->report));
    platform_set_drvdata(pdev, amp);
    return 0;
}

static void r36_amp_remove(struct platform_device *pdev)
{
    struct r36_amp *amp = platform_get_drvdata(pdev);
    /* A timed-out peer may still hold the address. Never recycle that page. */
    if (amp->published)
        dev_warn(&pdev->dev, "diagnostic DMA page retained until reset\n");
    else
        dma_free_coherent(&pdev->dev, PAGE_SIZE, amp->packet, amp->physical);
}

static const struct of_device_id r36_amp_match[] = {
    { .compatible = "r36lab,amprpc-poll" }, {},
};
MODULE_DEVICE_TABLE(of, r36_amp_match);
static struct platform_driver r36_amp_driver = {
    .probe = r36_amp_probe, .remove = r36_amp_remove,
    .driver = { .name = "r36-amprpc-poll", .of_match_table = r36_amp_match,
                .dev_groups = r36_amp_groups },
};
module_platform_driver(r36_amp_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("HC16E310 one-shot AVP mailbox polling transport diagnostic");
