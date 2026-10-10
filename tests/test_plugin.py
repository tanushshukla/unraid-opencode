#!/usr/bin/env python3
"""Exercise persistence paths in temporary directories; never modify the host."""
import base64
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

class Persistence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root/'appdata'
        self.home = self.root/'root'
        self.bin = self.root/'mock-bin'
        self.bin.mkdir()
        self.mock('mountpoint', 'exit "${MOUNT_EXIT:-0}"')
        self.mock('pgrep', 'exit 1')
        self.mock('pkill', 'exit 1')
        self.mock('uname', 'echo x86_64')
        # Serve fixtures by URL; unknown URLs fail like an unreachable server.
        self.fixtures = self.root/'fixtures'
        self.fixtures.mkdir()
        self.mock('curl', '''out=; url=
while (($#)); do case $1 in -o) out=$2; shift ;; https://*) url=$1 ;; esac; shift; done
echo "$url" >> "$FIXTURES/requests"
f="$FIXTURES/$(printf %s "$url" | tr '/:%' '___')"
[[ -f "$f" ]] || { echo download-failed >&2; exit 22; }
if [[ -n "$out" ]]; then cp "$f" "$out"; else cat "$f"; fi''')
        self.manager = self.root/'manager'
        src = (ROOT/'scripts/opencode-manager').read_text()
        src = src.replace('/mnt/user/appdata/opencode', str(self.base))
        src = src.replace('/root/', str(self.home)+'/')
        src = src.replace('/var/lock/opencode-plugin.lock', str(self.root/'lock'))
        self.manager.write_text(src)
        self.manager.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.bin)+':'+os.environ['PATH'], FIXTURES=str(self.fixtures))
    def fixture(self, url, data):
        (self.fixtures/url.replace('/','_').replace(':','_').replace('%','_')).write_bytes(data)
    def fake_binary(self, version):
        return ('#!/bin/bash\ncase $1 in --version) echo "opencode v%s" ;; service) echo "$*" >> "%s" ;; esac\n'
                % (version, self.root/'service-calls')).encode()
    def publish_v2(self, version='2.0.26', corrupt=False):
        buf=io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tar:
            data=self.fake_binary(version)
            info=tarfile.TarInfo('package/bin/opencode'); info.size=len(data); info.mode=0o755
            tar.addfile(info, io.BytesIO(data))
        package=buf.getvalue()
        integrity=base64.b64encode(hashlib.sha512(package+(b'x' if corrupt else b'')).digest()).decode()
        self.fixture('https://opencode.ai/update/api/latest/cli/npm',
                     ('{"channel":"latest","name":"cli","version":"%s","metadata":{"package":"@opencode/cli"}}' % version).encode())
        self.fixture('https://registry.npmjs.org/@opencode%%2fcli-linux-x64/%s' % version,
                     ('{"name":"@opencode/cli-linux-x64","dist":{"integrity":"sha512-%s"}}' % integrity).encode())
        self.fixture('https://registry.npmjs.org/@opencode/cli-linux-x64/-/cli-linux-x64-%s.tgz' % version, package)
    def requests(self):
        f=self.fixtures/'requests'
        return f.read_text().split() if f.exists() else []
    def mock(self, name, body):
        p=self.bin/name
        p.write_text('#!/bin/bash\n'+body+'\n')
        p.chmod(0o700)
    def cached(self, version='1.18.35'):
        (self.base/'bin').mkdir(parents=True, exist_ok=True)
        p=self.base/'bin/opencode'
        p.write_bytes(self.fake_binary(version))
        p.chmod(0o700)
        return p
    def run_manager(self, *args, ok=True):
        r=subprocess.run([str(self.manager),*args], env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode==0, ok, r.stdout+r.stderr)
        return r
    def test_unmounted_does_not_create_appdata(self):
        self.env['MOUNT_EXIT']='1'
        self.run_manager('ensure',ok=False)
        self.assertFalse(self.base.exists())
    def test_migration_preserves_both_copies_and_is_once_only(self):
        self.cached()
        old=self.home/'.config/opencode'
        old.mkdir(parents=True)
        (old/'config.json').write_text('old')
        dest=self.base/'config/opencode'
        dest.mkdir(parents=True)
        (dest/'config.json').write_text('persistent')
        (old/'extra.json').write_text('extra')
        self.run_manager('ensure')
        self.assertEqual((dest/'config.json').read_text(),'persistent')
        self.assertEqual((old/'config.json').read_text(),'old')
        self.assertEqual((dest/'extra.json').read_text(),'extra')
        (old/'later.json').write_text('later')
        self.run_manager('ensure')
        self.assertFalse((dest/'later.json').exists())
    def test_cached_start_works_without_network(self):
        p=self.cached()
        self.run_manager('ensure')
        self.run_manager('ensure')
        self.assertTrue(p.exists())
    def test_failed_update_preserves_binary_and_cleans_stage(self):
        p=self.cached()
        before=p.read_bytes()
        self.run_manager('update',ok=False)
        self.assertEqual(p.read_bytes(),before)
        self.assertEqual(list(self.base.glob('.install.*')),[])
    def test_rollback(self):
        self.cached()
        prev=self.base/'bin/opencode.previous'
        prev.write_bytes(self.fake_binary('1.18.34'))
        prev.chmod(0o700)
        expected=prev.read_bytes()
        self.run_manager('rollback')
        self.assertEqual((self.base/'bin/opencode').read_bytes(),expected)
    def test_latest_installs_verified_v2_from_npm(self):
        self.publish_v2()
        self.run_manager('ensure')
        r=subprocess.run([str(self.base/'bin/opencode'),'--version'],capture_output=True,text=True)
        self.assertEqual(r.stdout.strip(),'opencode v2.0.26')
        self.assertFalse(any('github.com' in u for u in self.requests()))
    def test_latest_falls_back_to_npm_when_update_service_fails(self):
        self.publish_v2()
        (self.fixtures/'https___opencode.ai_update_api_latest_cli_npm').unlink()
        self.fixture('https://registry.npmjs.org/@opencode%2fcli-linux-x64/latest',
                     (self.fixtures/'https___registry.npmjs.org_@opencode_2fcli-linux-x64_2.0.26').read_bytes()
                     .replace(b'{"name"',b'{"version":"2.0.26","name"'))
        r=self.run_manager('ensure')
        self.assertIn('asking the npm registry',r.stderr)
        self.assertIn('opencode v2.0.26',subprocess.run([str(self.base/'bin/opencode'),'--version'],capture_output=True,text=True).stdout)
    def test_checksum_mismatch_preserves_binary_and_cleans_stage(self):
        p=self.cached()
        before=p.read_bytes()
        self.publish_v2(corrupt=True)
        r=self.run_manager('update',ok=False)
        self.assertIn('Checksum mismatch',r.stderr)
        self.assertEqual(p.read_bytes(),before)
        self.assertEqual(list(self.base.glob('.install.*')),[])
    def test_upgrade_from_v1_backs_up_database_and_config(self):
        v1=self.cached('1.18.35').read_bytes()
        db=self.base/'data/opencode'
        db.mkdir(parents=True)
        (db/'opencode.db').write_text('v1-schema')
        (db/'opencode.db-wal').write_text('wal')
        (self.base/'config/opencode').mkdir(parents=True)
        (self.base/'config/opencode/tui.json').write_text('{}')
        self.publish_v2()
        self.run_manager('update')
        backups=list((self.base/'backup').glob('1.18.35-*'))
        self.assertEqual(len(backups),1)
        self.assertEqual((backups[0]/'data/opencode.db').read_text(),'v1-schema')
        self.assertEqual((backups[0]/'data/opencode.db-wal').read_text(),'wal')
        self.assertTrue((backups[0]/'config/tui.json').exists())
        self.assertEqual((self.base/'bin/opencode.previous').read_bytes(),v1)
    def test_upgrade_from_v1_refused_while_sessions_run(self):
        p=self.cached('1.18.35')
        before=p.read_bytes()
        self.mock('pgrep','exit 0')
        (self.base/'.migrated').touch()
        self.publish_v2()
        r=self.run_manager('update',ok=False)
        self.assertIn('Close all OpenCode sessions',r.stderr)
        self.assertEqual(p.read_bytes(),before)
        self.assertFalse((self.base/'backup').exists())
        self.assertEqual(list(self.base.glob('.install.*')),[])
    def test_same_series_update_skips_backup(self):
        self.cached('2.0.25')
        self.publish_v2('2.0.26')
        self.run_manager('update')
        self.assertFalse((self.base/'backup').exists())
    def test_pinned_v1_uses_github_release(self):
        self.cached('2.0.26')
        self.run_manager('update','1.18.35',ok=False)
        self.assertEqual(self.requests(),['https://github.com/anomalyco/opencode/releases/download/v1.18.35/opencode-linux-x64.tar.gz'])
    def test_rollback_to_v1_stops_service_and_backs_up(self):
        self.cached('2.0.26')
        prev=self.base/'bin/opencode.previous'
        prev.write_bytes(self.fake_binary('1.18.35'))
        prev.chmod(0o700)
        self.run_manager('rollback')
        self.assertIn('opencode v1.18.35',subprocess.run([str(self.base/'bin/opencode'),'--version'],capture_output=True,text=True).stdout)
        self.assertEqual(len(list((self.base/'backup').glob('2.0.26-*'))),1)
        self.assertIn('service stop',(self.root/'service-calls').read_text())
        self.assertFalse((self.base/'bin/opencode.restore').exists())
    def test_stop_only_calls_v2_service(self):
        self.cached('1.18.35')
        self.run_manager('stop')
        self.assertFalse((self.root/'service-calls').exists())
        self.cached('2.0.26')
        self.run_manager('stop')
        self.assertEqual((self.root/'service-calls').read_text().strip(),'service stop')
    def test_generated_xml_shell_and_sources(self):
        tree=ET.parse(ROOT/'opencode.plg')
        self.assertEqual(tree.getroot().get('min'),'7.1.4')
        for f in tree.findall('FILE'):
            script=f.findtext('INLINE')
            subprocess.run(['bash','-n'],input=script,text=True,check=True)
        self.assertIn((ROOT/'scripts/opencode-manager').read_text(),(ROOT/'opencode.plg').read_text())
        # Unraid skips files that already exist, so updates must remove them first.
        names=[f.get('Name') for f in tree.findall('FILE') if f.get('Name')]
        first=tree.findall('FILE')[0].findtext('INLINE')
        for name in names:
            self.assertIn(name, first.split('rm -f ')[-1])

if __name__=='__main__':
    unittest.main()
