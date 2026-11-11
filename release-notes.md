# TreeFrogUI v1.9.0_f prerelease

## FrogUI style profiles and ProMinimal

- **Per-style configuration:** FrogUI loads a JSON profile from
  `frogui/style-profiles/<Style>.json`. Each style can define its own defaults
  for `quick_resume`, `autosave_autoload`, `settings_layout`, `pillboxes`,
  `font`, `font_size`, `background_images`, `game_switcher`,
  `rounded_screenshots`, `stock_battery`, `battery_color`, `apps_in_settings`,
  and `start_in_recents`. Existing styles have explicit defaults; ProMinimal
  ships with its compact Alium-inspired settings and Apps-in-Settings layout.
- **User preference tracking:** Changes to profile-controlled settings are
  stored separately from the active style defaults. Normal styles apply the
  user's saved overrides when selected; `ignoreOverrides: true` lets a style
  such as ProMinimal always use its own profile. Existing settings are migrated
  so prior user choices are retained where they differ from the shipped style
  defaults.
- **Apps in Settings:** The Apps tab can be hidden and the existing Apps browser
  opened from Settings → Library. Back returns to Settings. The option can be
  enabled per style or changed in Settings.
- **Start in Recents:** ProMinimal starts in the Recents view when recent games
  exist. Other styles default to the previous setting, off. An existing saved
  opt-in is migrated as a user override.
- **Per-style font defaults:** Vertical, Horizontal, and System View retain
  their previous Alium Nunito font at size 23; ProMinimal uses the same font at
  size 18. Both values remain configurable per style.
- **Settings and recents polish:** Adds the folder-based Settings layout,
  decorative-pill control, rounded game-switcher screenshots, and ProMinimal's
  compact font, typography, and display defaults.

Style profiles are optional; a missing profile falls back to FrogUI's built-in
defaults. For a fresh installation, use the full archive and matching
`install_first/<device>/` files. To update an existing installation, copy
`update.zip` to the SD-card root and reboot.
