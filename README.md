# OpenCode for Unraid

A small, terminal-only OpenCode plugin targeting **Unraid 7.1.4+ on x86_64**. New installations get **OpenCode 2**; OpenCode 1 remains available by pinning a 1.x version. No Unraid upgrade is required by this plugin. The upstream OpenCode binary must also run on your CPU and system libraries; the installer checks `--version` before replacing a working binary.

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
| Backups made when switching between OpenCode 1 and 2 | `/mnt/user/appdata/opencode/backup` |

On first use, standard `/root/.config/opencode`, `/root/.local/share/opencode` and `/root/.local/state/opencode` contents are copied into these directories. Existing appdata files take precedence; original files are retained. A `.migrated` marker prevents copying stale originals again. Custom XDG locations are not automatically imported.

The appdata directory is private to root (mode 0700). Credentials stay on your server; this repository contains no credentials. Running the CLI as root gives it root's server access. Back up the appdata folder using your normal server backup process.

Unraid reprocesses the installed PLG at boot, recreating the wrapper and management script from the embedded content. Setup waits in the background for up to ten minutes for `/mnt/user`. If you start the array later, launching the wrapper performs setup on demand. Cached startup needs no network. Nothing is written to appdata unless `/mnt/user` is a mount point. Close OpenCode sessions before stopping the array.

This version requires user shares mounted at `/mnt/user`; custom pool-only paths and a Settings page are not included.

## OpenCode 2 background server

OpenCode 2 runs a detached background server (`opencode serve --service`) that the terminal client connects to, and it keeps running after you close the client. The plugin stops it when the array stops, so it cannot hold files open on `/mnt/user`. To stop it manually:

```bash
/usr/local/emhttp/plugins/opencode/scripts/opencode-manager stop
```

Use `opencode --standalone` if you prefer a private server that exits with the client.

## Updates and rollback

Plugin updates appear through Unraid's plugin updater. Updating the plugin itself does not automatically replace an existing OpenCode binary.

Update the binary explicitly (close sessions first):

```bash
/usr/local/emhttp/plugins/opencode/scripts/opencode-manager update
```

For a particular upstream release, append its version, for example `update 2.0.26` or `update 1.18.35`. OpenCode 2 is downloaded from the official `@opencode/cli-linux-x64` npm package, the same source as the [OpenCode 2 installer](https://opencode.ai/v2/install). It is checked against the registry's SHA-512 integrity hash. OpenCode 1.x releases still come from the `anomalyco/opencode` GitHub releases, which publish no checksums for this plugin to verify. The installer selects the baseline x64 build if AVX2 is absent, extracts only the expected executable, and tests it before replacing the cached binary. Failed downloads leave the previous binary intact.

### Upgrading from OpenCode 1

Existing installations stay on OpenCode 1 until you run `opencode-manager update`. When the update switches between OpenCode 1 and 2, in either direction, the manager stops the background server and refuses to continue while any `opencode` process is running. It then copies the session database (`opencode.db*`) and configuration into `appdata/opencode/backup/<old-version>-<timestamp>/`. OpenCode 2 reads the same configuration and session locations as 1.x. It moves terminal settings from `tui.json` into a new `cli.json` and leaves the old files in place. V1 plugins do not run in V2. See [Migrate from V1](https://opencode.ai/v2/docs/migrate-v1/).

Restore the previous binary:

```bash
/usr/local/emhttp/plugins/opencode/scripts/opencode-manager rollback
```

Rollback swaps the current and previous binaries. It does not restore the database: after returning from 2 to 1, copy the files from the matching `backup/1.x-*` folder back to `appdata/opencode/data/opencode/` if OpenCode 1 cannot read the database (sessions created in OpenCode 2 are then lost). Back up appdata before changing OpenCode versions. Prefer the management command over OpenCode's built-in upgrade command so a previous binary is retained.

## Uninstall

Remove OpenCode from Unraid's Plugins tab. The plugin stops the OpenCode 2 background server and removes its wrapper, management script and array-stop hook, preserving all appdata and original configuration. It does not terminate running terminal clients. Remove `/mnt/user/appdata/opencode` manually only if you intend to delete stored credentials and session history.

## Verification status

Fourteen sandbox tests cover missing mounts, non-destructive migration, one-time migration, cached/offline startup, failed updates and staging cleanup, OpenCode 2 installation from npm, checksum mismatches, 1→2 backups and the running-session guard, pinned 1.x downloads, rollback, background server shutdown, and generated XML/shell validity. They are simulated filesystem tests. Separately, the manager was run against the live npm registry and GitHub releases in a temporary directory (fresh 2.0.26 install, pinned 2.0.20, rollback, and 1.18.35 → 2.0.26 with a backup). None of this was on Unraid.

**Not yet verified on a live Unraid 7.1.4 server.** After installation, verify `--version`, sign in, create a disposable session, then close OpenCode and reboot at a convenient time. Start the array, reopen `/usr/local/bin/opencode`, and confirm the session and authentication remain. Report failures with the installation log, Unraid version and CPU model; remove credentials before sharing logs.

## Development

The PLG is self-contained, so restoration does not need to download helper scripts at boot. Edit the shell sources, regenerate the PLG, and run tests:

```bash
python3 build.py
python3 tests/test_plugin.py
```

Source references: [OpenCode 2 installer](https://opencode.ai/v2/install), [OpenCode 2 docs](https://opencode.ai/v2/docs), [OpenCode 1 installer](https://opencode.ai/install), [OpenCode configuration](https://opencode.ai/docs/config/), and [Unraid plugin boot behavior](https://forums.unraid.net/topic/72240-solved-is-there-a-way-to-installuninstall-plugins-from-script/). This is an independent implementation, not an official Unraid or OpenCode plugin.
