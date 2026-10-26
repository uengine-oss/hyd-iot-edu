import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('launcher',Path(__file__).with_name('launcher.py'))
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)

class LauncherTests(unittest.TestCase):
    def test_download_reopen_and_new_preserve_student_work(self):
        item=json.loads(Path(__file__).with_name('catalog.json').read_text(encoding='utf-8'))['labs'][0]
        with tempfile.TemporaryDirectory() as root:
            a=launcher.acquire(item,root)
            (a/'student.txt').write_text('my work')
            self.assertEqual(a,launcher.acquire(item,root,reopen=True))
            b=launcher.acquire(item,root)
            self.assertNotEqual(a,b)
            self.assertEqual((a/'student.txt').read_text(),'my work')
            self.assertTrue((b/'입력/관계그림.json').is_file())
            self.assertFalse((b/'결과/schema.json').exists())
            self.assertFalse(list(b.rglob('*대본*')))
    def test_failed_download_can_retry(self):
        item=json.loads(Path(__file__).with_name('catalog.json').read_text(encoding='utf-8'))['labs'][0]
        with tempfile.TemporaryDirectory() as root:
            bad=dict(item,url='http://127.0.0.1:8765/missing-package.zip')
            with self.assertRaises(Exception):launcher.acquire(bad,root)
            self.assertFalse(list(Path(root).glob('integrated-*')))
            self.assertTrue(launcher.acquire(item,root).is_dir())
    def test_wrong_hash_rejected(self):
        item=json.loads(Path(__file__).with_name('catalog.json').read_text(encoding='utf-8'))['labs'][0]
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):launcher.acquire(dict(item,sha256='0'*64),root)
            self.assertFalse(list(Path(root).glob('integrated-*')))

if __name__=='__main__':unittest.main()
