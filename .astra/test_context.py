"""실제 교재/계정에 쓰지 않는 회귀 검사. 임시 디렉터리와 가짜 CLI를 쓴다."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("astra_context", Path(__file__).with_name("context.py"))
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)
REPO = c.ROOT


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.space = self.root / ".astra"
        self.space.mkdir()
        self.patcher = patch.multiple(c, ROOT=self.root, SPACE=self.space,
                                     LEDGER=self.space / "reading.json", CHECKS=self.space / "checks.json")
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_partial_output_does_not_record_hidden_lines(self):
        text = "\n".join("가" * 45 for _ in range(6))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            c.emit("x.md", text, "a", [[1, 6]], 100)
        self.assertEqual(c.load(c.LEDGER)["x.md"]["ranges"], [[1, 2]])
        self.assertIn("다음은 3줄", out.getvalue())
        c.remember("x.md", "a", [[3, 4]])
        self.assertEqual(c.load(c.LEDGER)["x.md"]["ranges"], [[1, 4]])
        c.remember("x.md", "changed", [[5, 6]])
        self.assertEqual(c.load(c.LEDGER)["x.md"]["ranges"], [[5, 6]])

    def test_unprinted_first_line_is_not_recorded(self):
        with contextlib.redirect_stdout(io.StringIO()):
            c.emit("x.md", "가" * 101, "a", [[1, 1]], 100)
        self.assertEqual(c.load(c.LEDGER), {})

    def test_source_boundary_and_sensitive_paths(self):
        (self.root / "ok.md").write_text("본문", encoding="utf-8")
        (self.root / ".env").write_text("not-a-secret", encoding="utf-8")
        self.assertEqual(c.source("ok.md")[1], "본문")
        for name in ["../outside", str(self.root / "ok.md"), ".env"]:
            with self.assertRaises(ValueError):
                c.relative_file(name)
        with tempfile.TemporaryDirectory() as other:
            dest = Path(other) / "elsewhere.md"
            dest.write_text("outside", encoding="utf-8")
            (self.root / "link.md").symlink_to(dest)
            with self.assertRaises(ValueError):
                c.relative_file("link.md")

    def test_slide_selection_includes_notes_and_ground(self):
        text = "# 덱\n## SLIDE 1 — 시작\n- 노트: 설명\n### 제작 기준\n근거\n## SLIDE 2 — 끝\n본문\n"
        self.assertEqual(c.slides(text), [(1, "시작", 2, 5), (2, "끝", 6, 7)])

    def test_check_fingerprint_changes_with_picture_and_builder(self):
        md = self.root / c.deck(1)
        md.parent.mkdir(parents=True)
        (md.parent / "figures").mkdir()
        pic = md.parent / "figures/a.svg"
        pic.write_text("<svg/>", encoding="utf-8")
        md.write_text("- 그림: figures/a.svg\n", encoding="utf-8")
        builder = self.root / c.BUILDER
        builder.parent.mkdir(parents=True)
        builder.write_text("# builder", encoding="utf-8")
        one = c.inputs(1)
        self.assertEqual(one, c.inputs(1))
        pic.write_text("<svg>changed</svg>", encoding="utf-8")
        two = c.inputs(1)
        self.assertNotEqual(one, two)
        builder.write_text("# new builder", encoding="utf-8")
        self.assertNotEqual(two, c.inputs(1))

    def test_failure_and_concurrent_change_invalidate_success(self):
        runtime = self.root / ".venv-deck/bin/python"
        runtime.parent.mkdir(parents=True)
        runtime.touch()
        ok = subprocess.CompletedProcess([], 0, "[검사 통과] 덱\n", "")
        bad = subprocess.CompletedProcess([], 1, "", "실패")
        for result, hashes, expect in [(ok, ["a", "a"], True), (bad, ["a", "a"], False), (ok, ["a", "b"], False)]:
            with patch.object(c, "inputs", side_effect=hashes), patch.object(c.subprocess, "run", return_value=result), contextlib.redirect_stdout(io.StringIO()):
                code = c.check(1)
            self.assertEqual(c.load(c.CHECKS)["1"]["passed"], expect)
            self.assertEqual(code, 0 if expect else 1)


class LauncherTests(unittest.TestCase):
    def test_new_resume_preserve_request_and_strip_key_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / "codex"
            # 실제 Codex/네트워크를 호출하지 않는다. 환경변수는 존재 여부만 기록한다.
            exe.write_text("#!/usr/bin/env python3\nimport os,sys,json\nfrom pathlib import Path\nPath(os.environ['ASTRA_TEST_CAPTURE']).write_text(json.dumps({'args':sys.argv[1:],'stdin':sys.stdin.read(),'key_present':'OPENAI_API_KEY' in os.environ}),encoding='utf-8')\n", encoding="utf-8")
            exe.chmod(0o755)
            req = root / "요청 with spaces.txt"
            content = "둘째 회차를 고쳐라.\n`literal` $(literal) **그대로**\n"
            req.write_text(content, encoding="utf-8")
            capture = root / "capture.json"
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"], ASTRA_TEST_CAPTURE=str(capture), OPENAI_API_KEY="test-placeholder")
            for sid in ["new", "test-session"]:
                subprocess.run(["bash", str(REPO / "production/tools/deck/아스트라세션.sh"), sid, str(req), str(root / "답.txt"), "image with spaces.png"], env=env, cwd=root, check=True, capture_output=True)
                data = json.loads(capture.read_text())
                self.assertTrue(data["stdin"].endswith(content))
                self.assertEqual(data["stdin"].count(".astra/README.md"), 1)
                self.assertIn("gpt-6-astra", data["args"])
                self.assertIn("image with spaces.png", data["args"])
                self.assertEqual("resume" in data["args"], sid != "new")
                self.assertFalse(data["key_present"])


if __name__ == "__main__":
    unittest.main()
