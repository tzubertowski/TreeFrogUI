# Display scaling

TreeFrogUI keeps display scaling on the hardware path. R36SX exposes a
landscape framebuffer/HCGE configuration that supports the full aspect-ratio
menu: Integer, Native, 4:3, 16:9, 3:2, 5:4, 8:7, 16:10, and Fill.

SF3000 and SF3500 use a rotated 854×480 driver. Their stock driver exposes only
Native/Fit and Fill; it does not expose an arbitrary HCGE viewport/crop ratio.
The UI therefore offers Integer, Native, and Fill on those devices instead of
presenting ratios that cannot be applied reliably. This is a driver-interface
limitation, not a lack of HCGE scaling performance.

See [`TODO_RAW_HCGE_VIEWPORT.md`](../picoarch/TODO_RAW_HCGE_VIEWPORT.md) for
the remaining hardware-only work.
