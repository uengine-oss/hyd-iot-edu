import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('launcher',Path(__file__).with_name('launcher.py'))
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)

def ontology_item():
    data=json.loads(Path(__file__).with_name('catalog.json').read_text(encoding='utf-8'))
    return next(item for item in data['labs'] if item['id']=='integrated-02-ontology')

class LauncherTests(unittest.TestCase):
    def test_download_reopen_and_new_preserve_student_work(self):
        item=ontology_item()
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
        item=ontology_item()
        with tempfile.TemporaryDirectory() as root:
            bad=dict(item,url='http://127.0.0.1:8765/missing-package.zip')
            with self.assertRaises(Exception):launcher.acquire(bad,root)
            self.assertFalse(list(Path(root).glob('integrated-*')))
            self.assertTrue(launcher.acquire(item,root).is_dir())
    def test_wrong_hash_rejected(self):
        item=ontology_item()
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):launcher.acquire(dict(item,sha256='0'*64),root)
            self.assertFalse(list(Path(root).glob('integrated-*')))

class OutsideGuideTests(unittest.TestCase):
    """코딩 랩(guide_file): 가이드는 받은 실습 폴더 옆에 놓이고 폴더 안에는 없다(가이드.md P-3, 공용틀_계약 2)."""
    def setUp(self):
        import hashlib,http.server,threading,zipfile,functools
        self.serve=tempfile.TemporaryDirectory();d=Path(self.serve.name)
        with zipfile.ZipFile(d/'lab.zip','w') as z:
            z.writestr('02회차/랩/시험랩/START.md','# 시험\n')
            z.writestr('02회차/랩/시험랩/결과/README.md','결과 자리\n')
        (d/'lab_guide.html').write_bytes('<!doctype html><title>가이드</title>'.encode('utf-8'))
        handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(d))
        handler.log_message=lambda *a:None
        self.httpd=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
        threading.Thread(target=self.httpd.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{self.httpd.server_address[1]}/'
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        self.item={'id':'test-outside','folder':'02회차/랩/시험랩','version':'t','url':base+'lab.zip','sha256':sha(d/'lab.zip'),
                   'guide_file':{'url':base+'lab_guide.html','sha256':sha(d/'lab_guide.html')}}
    def tearDown(self):
        self.httpd.shutdown();self.httpd.server_close();self.serve.cleanup()
    def test_guide_beside_folder_and_reopen_restores_only_guide(self):
        with tempfile.TemporaryDirectory() as root:
            a=launcher.acquire(self.item,root)
            guide=launcher.guide_of(a)
            self.assertTrue(guide.is_file());self.assertEqual(guide.parent,a.parent)
            self.assertFalse((a/'guide.html').exists());self.assertFalse(list(a.rglob('*guide*')))
            (a/'결과/내것.txt').write_text('my work')
            guide.unlink()
            self.assertEqual(a,launcher.acquire(self.item,root,reopen=True))
            self.assertTrue(guide.is_file());self.assertEqual((a/'결과/내것.txt').read_text(),'my work')
    def test_wrong_guide_hash_rejected(self):
        bad=dict(self.item,guide_file=dict(self.item['guide_file'],sha256='0'*64))
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):launcher.acquire(bad,root)
            self.assertFalse(list(Path(root).glob('test-outside*')))

if __name__=='__main__':unittest.main()
