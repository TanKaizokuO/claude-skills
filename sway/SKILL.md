---
name: sway
description: Edit this machine's Sway/Wayland desktop config — keybindings, monitors, lockscreen, launchers, clipboard, theme colors. Use for any change to ~/.config/sway, waybar, fuzzel, mako, or swayidle/swaylock behavior.
---

Edit the live Sway setup on this laptop (IdeaPad Pro 5, Linux Mint 22.2, sway 1.9). The rule that makes everything else work: **never guess state — query it, back up, edit, reload, verify.**

Every shell command starts with `export _ZO_DOCTOR=0;` (silences a zoxide warning on this box).

## Layout

| Path | Holds |
|---|---|
| `~/.config/sway/config` | the only sway config that matters — one file, `####` banner sections |
| `~/.config/sway/config.bak-YYYY-MM-DD` | backups. **Never read these to answer a question** — grep hits here have burned a past session |
| `~/.config/sway/scripts/lock.sh` | swaylock wrapper: blurred wallpaper, cached per image+mtime |
| `~/.config/sway/scripts/screenshot.sh` | grim+slurp, `region` \| `full` |
| `~/.config/sway/themes/*.conf` | color palettes (Red Mountain is live, Catppuccin Mocha is the spare) |
| `~/.config/{waybar,fuzzel,mako,kitty,rofi}/` | the satellites — theme changes must land here too |

There is no `~/.config/sway/config.d/`. Only `/etc/sway/config.d/*` is included, at the last line.

## Procedure

1. **Read the live config**, never a `.bak`. Confirm the binding or setting isn't already taken:
   `export _ZO_DOCTOR=0; grep -n 'bindsym.*+f\b' ~/.config/sway/config`
2. **Query runtime state** before assuming anything about hardware:
   `swaymsg -t get_outputs` · `swaymsg -t get_inputs` · `swaymsg -t get_tree` (for `app_id`/`class`)
3. **Back up** only if today's backup doesn't exist yet:
   `cp -n ~/.config/sway/config ~/.config/sway/config.bak-$(date +%F)`
4. **Test live first** where the change is reversible — `swaymsg output DP-2 position 0 0` — then write it into the file. This proves the change before it is persisted.
5. **Edit in place**, keeping the `####` banner section it belongs under, and the comment style: say *why*, not *what*. Existing comments record hardware quirks and escape hatches; preserve them.
6. **Reload and verify:** `swaymsg reload` then re-query. A reload that errors prints to stderr — read it.
7. Report what changed, the backup path, and anything deliberately left alone.

## Hard-won gotchas

**Never run `lock.sh`, `swaylock`, or `swayidle` as a test.** The script `exec`s `swaylock -f` — running it locks the user's real screen with no warning. It once left them locked out and forced a power-button reboot. To test locking, tell the user to press `$mod+Shift+l` themselves. Never `pkill swaylock` on a lock you did not cause.

The lock script guards against stacked instances (`pgrep -x swaylock` → exit). **Keep that guard.** Two concurrent swaylocks each grab the keyboard, the password splits between them, and the red "wrong" indicator becomes permanent. That is what a red screen with a correct password means — not a bad password. Escape hatch, documented in the config: `Ctrl+Alt+F3` → TTY login → `pkill swaylock` → `Ctrl+Alt+F1`.

**Output connector names drift.** The external Samsung has enumerated as both `DP-1` and `DP-2` across boots. That is why the config lists three connectors (`DP-1`, `HDMI-A-1`, `DP-2`) with identical `output` lines, and why every odd `workspace N output …` line names all of them plus `eDP-1` as fallback. Sway silently ignores lines for absent outputs, so listing extras is free — **omitting one is what breaks the layout**: an unpositioned output gets auto-appended to the right. Always `swaymsg -t get_outputs` before diagnosing a monitor complaint, and add a new name to *both* the `output` block and every workspace list.

Geometry is: monitor at `position 0 0` (left), laptop `eDP-1 scale 1.5 position 1920 0` (right, logical 1920x1200). Scale 1.5 is fractional — anything sized in physical pixels renders differently per output, which is why `fuzzel.ini` sets `dpi-aware=no`.

**Reload, never restart.** `restart` is i3-only; `$mod+Shift+r` is bound to `reload` for muscle memory.

`$mod` is `Mod4` (Super). Taken: `t`/`Return` kitty, `c` code, `a` antigravity, `Shift+a` android-studio, `b` brave, `x` yazi, `Shift+x` nautilus, `n` nm-editor, `d` rofi, `q` kill, `f` fullscreen, `s`/`w`/`e` layouts, `h`/`v` split, `1-0` + Shift workspaces, arrows + Shift movement, `Shift+c`/`Shift+r` reload, `Shift+e` exit, `Shift+l` lock, `Print`/`$mod+Print` screenshots. Clipboard deliberately uses `Ctrl+Alt+v` (picker), `Ctrl+Alt+Shift+v` (delete), `Ctrl+Alt+Shift+Delete` (wipe) — **not** `$mod+v`, which is split-vertical. `$mod+space`, `$mod+Shift+space`, and `floating_modifier` were free as of the last audit — re-grep before claiming it.

Rofi runs under XWayland; fuzzel and mako are native. Prefer fuzzel for anything new.

**A theme change is never one file.** Window colors live in the `client.*` block in the sway config; the same palette is mirrored by hand into `~/.config/fuzzel/fuzzel.ini` (`[colors]`, plus `[border] width=4 radius=0` to match `default_border pixel 4`), `~/.config/waybar/style.css`, mako, and kitty. Changing one and not the others is the usual complaint. Current palette — Red Mountain: `#9E3046` focused border, `#0D1624` bg, `#D6DCE6` text, `#C44752` indicator, `#263344` inactive, `#070B14` background.

Clipboard history is cliphist, fed by two `wl-paste --watch` execs (text and image, separately — both are needed). It uses wlr-data-control, so nothing X11 is involved. CopyQ was removed deliberately; do not suggest it.

## Window rules

Get the identifier from `swaymsg -t get_tree | grep -E 'app_id|class'` with the window focused. Native Wayland apps have `app_id`, XWayland apps have `class` — rules need the right one, and existing config pairs them (`for_window [app_id=".*"]` + `for_window [class=".*"]`) when a rule must cover both.

## Scope

Stay inside the desktop config. Suspend/resume failures, Wi-Fi drops on wake, and audio dying after the Android emulator are separate known issues with their own fixes — not sway problems.
