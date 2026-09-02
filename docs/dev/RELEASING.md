# TreeFrogUI release process

The release pipeline creates two GitHub assets:

- `TreeFrogUI_<version>.zip` - the complete clean-card installation.
- `update.zip` - an automatic offline update copied directly to the SD-card
  root by users.

The generated workspace is deliberately separated:

```text
release/
├── artifact/                 retained full ZIPs used for comparison
└── latest/
    ├── release/              current unpacked full-release tree
    ├── TreeFrogUI_<version>.zip
    └── update.zip
```

Everything under `release/` is generated and gitignored. Do not hand-edit or
commit it.

## Version and base rules

Versions must begin with `vMAJOR.MINOR.RELEASE`, optionally followed by a
suffix, such as `v1.0.14_a`.

Normal local builds select the newest archive from the preceding numeric line.
Published cumulative builds instead use two archives: the latest release seeds
the complete build tree, while the oldest update-capable release in the current
major line is passed to `pack_release.sh` with
`TREEFROG_CUMULATIVE_UPDATE=1`.

| New version | Selected base |
|---|---|
| `v1.0.13_b` | newest `v1.0.12*` |
| `v1.0.13_z` | newest `v1.0.12*` |
| `v1.0.14_a` | newest `v1.0.13*` |

This makes every suffix build in a line upgrade the same previous numeric
release. `select_release_base.sh` implements this rule; do not replace it with
"latest ZIP" selection.

Full releases contain `cubegm/version.txt`. Ordinary deltas require an exact
base version. Cumulative updates carry a major-version constraint; their
`base_version=unknown` compatibility marker also lets older updaters install
the package.

## Build without publishing

Place the preceding numeric-line full ZIP in `release/artifact/`, then run:

```sh
./build_release.sh
./pack_release.sh v1.0.14_a
```

To bootstrap the artifact cache from an archive elsewhere:

```sh
./build_release.sh
./pack_release.sh v1.0.14_a /path/to/TreeFrogUI_v1.0.13_c.zip
```

`build_release.sh` recreates only `release/latest/release/`; it preserves the
comparison cache. `pack_release.sh` stamps the version, creates the full ZIP,
compares it byte-for-byte with the selected base, and creates `update.zip`.

The delta contains added and changed universal files, supported per-device boot
overlays, and checksummed deletion lists for obsolete TreeFrogUI-owned files.
Files listed in `update-force-include.txt` are always included so required UI
and emulator configuration changes reach users even when a build comparison
would otherwise omit them. Stock `setting.xml` and personal content are barred
from automatic updates.

## Validate

Run all checks before publishing:

```sh
./tests/test_release_base_selection.sh
./tests/test_offline_update.sh \
  ./release/latest/update.zip \
  ./release/artifact/TreeFrogUI_v1.0.13_c.zip
7z t ./release/latest/TreeFrogUI_v1.0.14_a.zip
7z t ./release/latest/update.zip
sh -n build_release.sh pack_release.sh publish_release.sh \
  select_release_base.sh hijack/tfupdate.sh hijack/zhijack.tpl.sh
git diff --check
```

Replace archive names with the versions being released. The updater test
simulates a real SD-card upgrade, checks the resulting tree against the new full
release, verifies config backup/override behavior, and confirms personal ROMs
survive.

Inspect the manifest when diagnosing base selection:

```sh
7z e -so release/latest/update.zip treefrog-update/manifest.txt
```

## Publish to GitHub

Review `release-notes.md`, commit the source changes, and then run:

```sh
./publish_release.sh <github-tag> [artifact-version] [base-full.zip]
```

Example:

```sh
./publish_release.sh v1.0.14 v1.0.14_a
```

`publish_release.sh` requires `gh` and `7z`. When the appropriate comparison
ZIP is absent locally, the publisher finds the preceding numeric GitHub release
and downloads its full ZIP into
`release/artifact/`. It builds and validates the two output paths, then creates
the GitHub release or replaces both assets on an existing tag. After a
successful upload, it retains the new full ZIP in `release/artifact/` for a
future numeric line.

Passing `base-full.zip` explicitly seeds the artifact cache from that file. Use
this only when the automatic numeric-line selection cannot locate a historical
release.

Publishing mutates GitHub state. Automation agents must not run this command
without explicit authorization to publish.

## GitHub Actions automation

The `Build TreeFrogUI release` workflow in `.github/workflows/release.yml`
repeats the cross-build and packaging process on an Ubuntu runner. It downloads
the public SF3000 toolchain, checks out the FrogUI and picoarch `r36sx` sources,
seeds ignored staging files from an existing full release, builds both
frontends, and publishes the full ZIP plus `update.zip`.

It can be started in either of these ways:

- Push a `vMAJOR.MINOR.RELEASE` tag. The workflow uses that tag and creates a
  prerelease automatically.
- Run it from **Actions → Build TreeFrogUI release → Run workflow**. Enter a
  `tag` to publish a release, or leave it blank to produce downloadable
  build-only artifacts. Set `base_tag` to the latest full release used to seed
  the build and `update_base_tag` to the oldest compatible release in the
  current major line.

Manual runs without a tag never mutate GitHub releases; they upload the ZIPs as
workflow artifacts for testing.

## User update flow

Users download the release asset named exactly `update.zip`, copy it directly
to the SD-card root, safely eject, and boot. No extraction or device selection
is required.

At startup TreeFrogUI:

1. extracts into `.treefrog-update/` on the card;
2. verifies the manifest, device payload, and SHA-256 list;
3. backs up configuration files that will be replaced;
4. installs files atomically and applies safe TreeFrogUI-owned deletions;
5. records the installed version and restarts the launcher;
6. deletes `update.zip` only after success.

Failures leave `update.zip` in place and write `update.log`. ROMs, BIOS files,
saves, save states, screenshots, favourites, recents, play-time data, and
personal media are preserved.

Devices running a release from before the updater was introduced require one
normal full installation, including `install_first/<device>/`. Subsequent
updates use the root-level `update.zip` flow.
