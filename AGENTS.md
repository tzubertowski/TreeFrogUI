# TreeFrogUI agent instructions

- Luna handles implementation; the main agent handles analysis/review when available.

## Markdown formatting

- Do not hard-wrap prose or list items in changelogs and release notes. Keep each paragraph and bullet on one source line and let GitHub wrap it; preserve explicit breaks only where the content requires them.

## Repository and branch workflow

- **TreeFrogUI:** `/home/tomaszz/sf3000-work/sf3000_treefrogui`; integration
  branch is `main`.
- **FrogUI source:** `/home/tomaszz/sf3000-work/FrogUI`; the device build's
  integration branch is `r36sx`. The nested `frogui/` path here is only a
  pinned submodule checkout: never do source work on its detached HEAD. Make
  FrogUI changes in the canonical checkout, preserve its tested aliases,
  artwork fallbacks, translations, and pill animation, then update this repo's
  submodule pin from the integrated FrogUI commit.
- **PicoArch:** `/home/tomaszz/sf3000-work/picoarch`; integration branch is
  `r36sx`. Its `main` is legacy and must not be used as an integration target.
- These branch names are repo-specific. Never infer that every repo uses a
  branch named `main`; check this map before switching or merging.

- The canonical checkout is `/home/tomaszz/sf3000-work/sf3000_treefrogui`. Keep
  active TreeFrogUI work in this folder on `main`.
- Do not create source clones, worktrees, or per-release repository copies under
  `/tmp` or elsewhere. Do not create per-release branches.
- If a task needs isolation, use at most one feature branch at a time. Keep
  `main` as the integration branch and ask the user for explicit confirmation
  before merging a feature branch into `main`.
- Before branch changes, inspect and preserve all modified, untracked, and
  submodule work. Never reset or overwrite existing work to make a checkout
  clean; record where any temporarily stashed changes were saved.
- Keep companion repositories such as FrogUI on their existing canonical
  checkout and branch. Update their pinned commit from the canonical TreeFrogUI
  checkout; do not make parallel copies of the same source.

## Releases

- Start a fresh `release-notes.md` for every minor or major release; do not inherit or carry forward the previous release's changelog.
- Before every prerelease, compare the selected base release with the current
  source and submodule history and document every user-facing change in
  `release-notes.md`; do not publish a one-line delta when the release includes
  accumulated changes.
- Before every CPG release, add a clearly labeled `Changes since the
  v<previous-build>` section to `release-notes.md`. Compare against the actual
  previous build, including companion repositories such as FrogUI, and update
  the GitHub release body if the workflow was started before the notes changed.
- Follow [`docs/RELEASING.md`](docs/RELEASING.md) as the canonical release procedure.
- Always build prereleases from the v1.0 stable line: use the newest v1.0.x
  stable archive as the full-build base, and use the appropriate v1.0.x archive
  as the cumulative-update base. Do not select a later minor line such as v1.4
  or v1.5 as the base.
- Before dispatching GHA, inspect both selected full-release archives/metadata and
  reject any archive whose `base_version` is `unknown`; old v1.0 archives may
  predate the cumulative updater. Use the newest valid v1.0.x archive for both
  `base_tag` and `update_base_tag` when no older update-capable archive exists.
- Reuse the current local core bundle for releases that do not change compiled
  components. If a release changes a core or FrogUI system mapping, rebuild only
  that binary, update the affected payload files and bundle checksums, and keep
  every other binary from the previous bundle. Run `build_local_bundle.sh` only
  when the full set of compiled components must change or no valid bundle exists.
- Keep retained comparison ZIPs in `release/artifact/`. Keep current staging,
  the full ZIP, and `update.zip` in `release/latest/`.
- Do not hand-edit generated content under `release/` and do not commit it.
- Run both release tests and archive integrity checks before reporting a release
  ready.
- Creating or uploading a GitHub release changes external state. Only run
  `publish_release.sh` when the user explicitly asks to publish.
- Do not trigger GitHub Actions release/prerelease workflows without explicit
  confirmation in the current conversation. Preparing a commit is fine; wait
  for confirmation before starting the remote build.
- Never put ROMs, BIOS files, saves, screenshots, or other personal SD-card data
  in an update package. Configuration files listed in
  `update-force-include.txt` are intentionally replaced and backed up on-device.

## Commit hygiene

- When merging external contributions, keep the README's Contributors and
  Credits sections current, and keep Ports Collection source-fork links current.
- Squash follow-up commits that correct the same change before pushing when practical; keep the final history focused instead of stacking incremental fix-ups.

## Privileged SD-card operations

- Use `/home/tomaszz/bin/mount-sd-rw` to mount the inserted card read-write;
  it performs the required filesystem check and caches the sudo authorization
  for the current session. Do not repeatedly invoke ad-hoc `sudo mount` or
  `sudo cp` commands and prompt the user for the password each time.
- Set `SUDO_ASKPASS=/home/tomaszz/bin/sudo-gui-askpass` and run one
  `sudo -A -v` before a batch. Use `sudo -A` consistently for copy, sync, and
  unmount; do not mix in `pkexec`, which creates separate authorization prompts.
- After copying, run `sync` and unmount the card safely before asking for a
  device test. Reuse the cached authorization for all commands in that session.
