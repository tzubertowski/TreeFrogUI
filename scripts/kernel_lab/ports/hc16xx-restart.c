// SPDX-License-Identifier: GPL-2.0
/* Restart sequence measured in stock board_restart; watchdog clock held on. */
#include <linux/clk.h>
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/reboot.h>

static int hc16xx_restart(struct sys_off_data *data)
{
    void __iomem *base = data->cb_data;
    writel(0xfffffffa, base);
    writel(0x26, base + 4);
    readl(base + 4);
    mdelay(100);
    return NOTIFY_DONE;
}

static int hc16xx_restart_probe(struct platform_device *pdev)
{
    void __iomem *base;
    struct clk *clk;
    base = devm_platform_ioremap_resource(pdev, 0);
    if (IS_ERR(base)) return PTR_ERR(base);
    clk = devm_clk_get_enabled(&pdev->dev, NULL);
    if (IS_ERR(clk)) return dev_err_probe(&pdev->dev, PTR_ERR(clk), "watchdog clock unavailable\n");
    return devm_register_restart_handler(&pdev->dev, hc16xx_restart, base);
}

static const struct of_device_id hc16xx_restart_match[] = {
    { .compatible = "r36lab,hc16xx-restart" }, { }
};
MODULE_DEVICE_TABLE(of, hc16xx_restart_match);
static struct platform_driver hc16xx_restart_driver = {
    .probe = hc16xx_restart_probe,
    .driver = { .name = "r36-hc16xx-restart", .of_match_table = hc16xx_restart_match },
};
module_platform_driver(hc16xx_restart_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("HC16xx stock-compatible restart handler");
