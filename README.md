# OpenCode for Unraid

A small, terminal-only OpenCode plugin targeting **Unraid 7.1.4+ on x86_64**. No Unraid upgrade is required by this plugin. The upstream OpenCode binary must also run on your CPU and system libraries; the installer checks `--version` before replacing a working binary.

## Install

Start the array, then paste this URL into **Plugins → Install Plugin**:

```
https://raw.githubusercontent.com/tanushshukla/unraid-opencode/main/opencode.plg
```

Or run from the Unraid terminal:

```bash
plugin install https://raw.githubusercontent.com/tanushshukla/unraid-opencode/main/opencode.plg
```

Installation downloads OpenCode in the background. Check progress with:

```bash
tail -n 80 /var/log/opencode-plugin.log
```

Then run:

```bash
/usr/local/bin/opencode --version
/usr/local/bin/opencode
```

The full path selects this plugin if an older manual installation appears earlier in your PATH. Run `type -a opencode` to inspect that. Close old OpenCode sessions before first installation so their databases can be copied consistently.

## Persistence

The plugin wrapper supplies OpenCode's XDG directories without changing your HOME or Claude installation:

| Content | Persistent path |
| --- | --- |
| Executable | `/mnt/user/appdata/opencode/bin/opencode` |
| Configuration | `/mnt/user/appdata/opencode/config/opencode` |
| Authentication, sessions and data | `/mnt/user/appdata/opencode/data/opencode` |
| State | `/mnt/user/appdata/opencode/state/opencode` |
| Cache | `/mnt/user/appdata/opencode/cache/opencode` |

On first use, standard `/root/.config/opencode`, `/root/.local/share/opencode` and `/root/.local/state/opencode` contents are copied into these directories. Existing appdata files take precedence; original files are retained. A `.migrated` marker prevents copying stale originals again. Custom XDG locations are not automatically imported.

The appdata directory is private to root (mode 0700). Credentials stay on your server; this repository contains no credentials. Running the CLI as root gives it root's server access. Back up the appdata folder using your normal server backup process.

Unraid reprocesses the installed PLG at boot, recreating the wrapper and management script from the embedded content. Setup waits in the background for up to ten minutes for `/mnt/user`. If you start the array later, launching the wrapper performs setup on demand. Cached startup needs no network. Nothing is written to appdata unless `/mnt/user` is a mount point. Close OpenCode sessions before stopping the array.

This version requires user shares mounted at `/mnt/user`; custom pool-only paths and a Settings page are not included.

## Updates and rollback

Plugin updates appear through Unraid's plugin updater. Updating the plugin itself does not automatically replace an existing OpenCode binary.

Update the binary explicitly (close sessions first):

```bash
/usr/local/emhttp/plugins/opencode/scripts/opencode-manager update
```

For a particular upstream release, append its version, for example `update 1.0.180` (choose a release suitable for your configuration). Downloads come from the official `anomalyco/opencode` GitHub releases over HTTPS; this version does not independently verify upstream signatures or checksums. The installer selects the baseline x64 build if AVX2 is absent, extracts only the expected executable, and tests it before replacing the cached binary. Failed downloads leave the previous binary intact.

Restore the previous binary:

```bash
/usr/local/emhttp/plugins/opencode/scripts/opencode-manager rollback
```

Rollback restores the binary only, not session database schemas. Back up appdata before changing OpenCode versions. Prefer the management command over OpenCode's built-in upgrade command so a previous binary is retained.

## Uninstall

Remove OpenCode from Unraid's Plugins tab. The plugin removes its wrapper and management script, preserving all appdata and original configuration. It does not terminate running sessions. Remove `/mnt/user/appdata/opencode` manually only if you intend to delete stored credentials and session history.

## Verification status

Six sandbox tests cover missing mounts, non-destructive migration, one-time migration, cached/offline startup, failed updates and staging cleanup, rollback, and generated XML/shell validity. These are simulated filesystem tests, not an Unraid VM or real upstream binary installation test.

**Not yet verified on a live Unraid 7.1.4 server.** After installation, verify `--version`, sign in, create a disposable session, then close OpenCode and reboot at a convenient time. Start the array, reopen `/usr/local/bin/opencode`, and confirm the session and authentication remain. Report failures with the installation log, Unraid version and CPU model; remove credentials before sharing logs.

## Development

The PLG is self-contained, so restoration does not need to download helper scripts at boot. Edit the shell sources, regenerate the PLG, and run tests:

```bash
python3 build.py
python3 tests/test_plugin.py
```

Source references: [OpenCode installer](https://opencode.ai/install), [OpenCode configuration](https://opencode.ai/docs/config/), and [Unraid plugin boot behavior](https://forums.unraid.net/topic/72240-solved-is-there-a-way-to-installuninstall-plugins-from-script/). This is an independent implementation, not an official Unraid or OpenCode plugin.
