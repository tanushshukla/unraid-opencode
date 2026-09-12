#!/usr/bin/env python3
"""Generate a self-contained Unraid plugin from the reviewed shell sources."""
from pathlib import Path
import xml.etree.ElementTree as ET
root = Path(__file__).resolve().parent
parts = ['''<?xml version="1.0" standalone="yes"?>
<PLUGIN name="opencode" author="tanushshukla" version="2026.09.12" min="7.1.4"
 pluginURL="https://raw.githubusercontent.com/tanushshukla/unraid-opencode/main/opencode.plg"
 supportURL="https://github.com/tanushshukla/unraid-opencode/issues">
<DESCRIPTION>OpenCode CLI with persistent appdata. Target: Unraid 7.1.4 and later.</DESCRIPTION>
<CHANGES>2026.09.12: Initial release. Persistent storage, guarded migration, explicit updates and rollback.</CHANGES>
''']
def entry(body, attrs):
    assert ']]>' not in body
    parts.append(f'<FILE {attrs}><INLINE><![CDATA[{body}\n]]></INLINE></FILE>\n')
entry('''set -e
mkdir -p /usr/local/emhttp/plugins/opencode/scripts /usr/local/bin
if [ -e /usr/local/bin/opencode ] || [ -L /usr/local/bin/opencode ]; then
    if ! grep -q '/usr/local/emhttp/plugins/opencode/scripts/opencode-manager ensure' /usr/local/bin/opencode 2>/dev/null; then
        echo 'Existing /usr/local/bin/opencode found. Move it aside before installing this plugin.' >&2
        exit 1
    fi
fi''', 'Run="/bin/bash"')
for src, dest in [
    ('scripts/opencode-manager', '/usr/local/emhttp/plugins/opencode/scripts/opencode-manager'),
    ('scripts/opencode', '/usr/local/bin/opencode'),
]:
    entry((root/src).read_text(), f'Name="{dest}" Mode="0700"')
entry('''nohup /bin/bash /usr/local/emhttp/plugins/opencode/scripts/opencode-manager boot > /var/log/opencode-plugin.log 2>&1 < /dev/null &
echo 'OpenCode plugin installed. Start the array, then run /usr/local/bin/opencode.'
echo 'Download/setup progress: /var/log/opencode-plugin.log' ''', 'Run="/bin/bash"')
entry('''set -e
# Coordinate with any installation; never delete appdata or user configuration.
exec 9>/var/lock/opencode-plugin.lock
flock -w 660 9
pkill -f '^/bin/bash /usr/local/emhttp/plugins/opencode/scripts/opencode-manager boot$' || true
if grep -q '/usr/local/emhttp/plugins/opencode/scripts/opencode-manager ensure' /usr/local/bin/opencode 2>/dev/null; then
    rm -f /usr/local/bin/opencode
fi
rm -f /usr/local/emhttp/plugins/opencode/scripts/opencode-manager
rmdir /usr/local/emhttp/plugins/opencode/scripts /usr/local/emhttp/plugins/opencode 2>/dev/null || true
echo 'Plugin removed. All appdata and existing running sessions were preserved.' ''', 'Run="/bin/bash" Method="remove"')
parts.append('</PLUGIN>\n')
output = ''.join(parts)
ET.fromstring(output)
(root/'opencode.plg').write_text(output)
