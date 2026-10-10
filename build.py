#!/usr/bin/env python3
"""Generate a self-contained Unraid plugin from the reviewed shell sources."""
from pathlib import Path
import xml.etree.ElementTree as ET
root = Path(__file__).resolve().parent
parts = ['''<?xml version="1.0" standalone="yes"?>
<PLUGIN name="opencode" author="tanushshukla" version="2026.10.10b" min="7.1.4"
 pluginURL="https://raw.githubusercontent.com/tanushshukla/unraid-opencode/main/opencode.plg"
 supportURL="https://github.com/tanushshukla/unraid-opencode/issues">
<DESCRIPTION>OpenCode CLI with persistent appdata. Target: Unraid 7.1.4 and later.</DESCRIPTION>
<CHANGES>2026.10.10b: Fall back to the npm registry when the OpenCode update service is unavailable.
2026.10.10a: Fix plugin updates leaving the previous management script in place.
2026.10.10: OpenCode 2 support. Installs from the official npm packages with SHA-512 verification, backs up the database and configuration when switching between OpenCode 1 and 2, and stops the OpenCode 2 background server when the array stops.
2026.09.12: Initial release. Persistent storage, guarded migration, explicit updates and rollback.</CHANGES>
''']
def entry(body, attrs):
    assert ']]>' not in body
    parts.append(f'<FILE {attrs}><INLINE><![CDATA[{body}\n]]></INLINE></FILE>\n')
entry('''set -e
mkdir -p /usr/local/emhttp/plugins/opencode/scripts /usr/local/emhttp/plugins/opencode/event /usr/local/bin
if [ -e /usr/local/bin/opencode ] || [ -L /usr/local/bin/opencode ]; then
    if ! grep -q '/usr/local/emhttp/plugins/opencode/scripts/opencode-manager ensure' /usr/local/bin/opencode 2>/dev/null; then
        echo 'Existing /usr/local/bin/opencode found. Move it aside before installing this plugin.' >&2
        exit 1
    fi
fi
# Unraid does not overwrite existing files, so remove ours to let updates replace them.
rm -f /usr/local/bin/opencode /usr/local/emhttp/plugins/opencode/scripts/opencode-manager /usr/local/emhttp/plugins/opencode/event/stopping''', 'Run="/bin/bash"')
for src, dest in [
    ('scripts/opencode-manager', '/usr/local/emhttp/plugins/opencode/scripts/opencode-manager'),
    ('scripts/opencode', '/usr/local/bin/opencode'),
]:
    entry((root/src).read_text(), f'Name="{dest}" Mode="0700"')
# Unraid runs plugin event scripts on array state changes; release appdata before unmounting.
entry('''#!/bin/bash
/usr/local/emhttp/plugins/opencode/scripts/opencode-manager stop''', 'Name="/usr/local/emhttp/plugins/opencode/event/stopping" Mode="0755"')
entry('''nohup /bin/bash /usr/local/emhttp/plugins/opencode/scripts/opencode-manager boot > /var/log/opencode-plugin.log 2>&1 < /dev/null &
echo 'OpenCode plugin installed. Start the array, then run /usr/local/bin/opencode.'
echo 'Download/setup progress: /var/log/opencode-plugin.log' ''', 'Run="/bin/bash"')
entry('''set -e
# Coordinate with any installation; never delete appdata or user configuration.
exec 9>/var/lock/opencode-plugin.lock
flock -w 660 9
pkill -f '^/bin/bash /usr/local/emhttp/plugins/opencode/scripts/opencode-manager boot$' || true
# The OpenCode 2 background server is detached; stop it so it cannot block stopping the array.
/usr/local/emhttp/plugins/opencode/scripts/opencode-manager stop || true
if grep -q '/usr/local/emhttp/plugins/opencode/scripts/opencode-manager ensure' /usr/local/bin/opencode 2>/dev/null; then
    rm -f /usr/local/bin/opencode
fi
rm -f /usr/local/emhttp/plugins/opencode/scripts/opencode-manager /usr/local/emhttp/plugins/opencode/event/stopping
rmdir /usr/local/emhttp/plugins/opencode/scripts /usr/local/emhttp/plugins/opencode/event /usr/local/emhttp/plugins/opencode 2>/dev/null || true
echo 'Plugin removed. All appdata was preserved; the OpenCode 2 background server was stopped.' ''', 'Run="/bin/bash" Method="remove"')
parts.append('</PLUGIN>\n')
output = ''.join(parts)
ET.fromstring(output)
(root/'opencode.plg').write_text(output)
