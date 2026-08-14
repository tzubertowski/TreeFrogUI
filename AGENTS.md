# TreeFrogUI agent instructions

## Releases

- Follow [`docs/RELEASING.md`](docs/RELEASING.md) as the canonical release procedure.
- Never choose another suffix build from the same numeric release line as the
  delta base. For example, `v1.0.13_b` is based on the newest `v1.0.12*`, not
  `v1.0.13_a`.
- Keep retained comparison ZIPs in `release/artifact/`. Keep current staging,
  the full ZIP, and `update.zip` in `release/latest/`.
- Do not hand-edit generated content under `release/` and do not commit it.
- Run both release tests and archive integrity checks before reporting a release
  ready.
- Creating or uploading a GitHub release changes external state. Only run
  `publish_release.sh` when the user explicitly asks to publish.
- Never put ROMs, BIOS files, saves, screenshots, or other personal SD-card data
  in an update package. Configuration files listed in
  `update-force-include.txt` are intentionally replaced and backed up on-device.
