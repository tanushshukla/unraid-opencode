#!/usr/bin/env python3
"""Exercise persistence paths in temporary directories; never modify the host."""
import os
from pathlib import Path
import subprocess
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
        self.mock('curl', 'echo download-failed >&2; exit 22')
        self.manager = self.root/'manager'
        src = (ROOT/'scripts/opencode-manager').read_text()
        src = src.replace('/mnt/user/appdata/opencode', str(self.base))
        src = src.replace('/root/', str(self.home)+'/')
        src = src.replace('/var/lock/opencode-plugin.lock', str(self.root/'lock'))
        self.manager.write_text(src)
        self.manager.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.bin)+':'+os.environ['PATH'])
    def mock(self, name, body):
        p=self.bin/name
        p.write_text('#!/bin/bash\n'+body+'\n')
        p.chmod(0o700)
    def cached(self):
        (self.base/'bin').mkdir(parents=True)
        p=self.base/'bin/opencode'
        p.write_text('#!/bin/bash\necho test-version\n')
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
        prev.write_text('#!/bin/bash\necho previous\n')
        prev.chmod(0o700)
        self.run_manager('rollback')
        self.assertEqual((self.base/'bin/opencode').read_bytes(),prev.read_bytes())
    def test_generated_xml_shell_and_sources(self):
        tree=ET.parse(ROOT/'opencode.plg')
        self.assertEqual(tree.getroot().get('min'),'7.1.4')
        for f in tree.findall('FILE'):
            script=f.findtext('INLINE')
            subprocess.run(['bash','-n'],input=script,text=True,check=True)
        self.assertIn((ROOT/'scripts/opencode-manager').read_text(),(ROOT/'opencode.plg').read_text())

if __name__=='__main__':
    unittest.main()
