"""덱 MD → PPTX(전문 기술 교재형). 색·글꼴·배치는 이 파일이 고정하고, 덱 MD는 장 유형·화면 문구·아이콘만 정한다.

형식: ../references/덱MD-PPTX형식.md
사용: python deck2pptx.py <덱.md> <출력.pptx> [--render <PNG 폴더>]
      python deck2pptx.py --check <덱.md | -> [--base <덱 폴더>]   # 파일을 하나도 쓰지 않고 검사만(읽기 전용 환경용, - 는 표준 입력)
규칙 위반(모르는 유형·없는 칸·요소 수·그림 없음·아이콘 수·넘침 추정)은 장 번호와 칸 이름을 찍고 실패한다.

본문 장은 제목(28pt) → 거버닝 메시지 한 줄 · 한 문장(16pt) → 본문(14~15pt)이다. 하단 넘기는 질문 상자와 반복 목차는 없고
목차는 한 번, 단원은 간지로 나눈다. 렌더(--render)는 파일 잠금으로 한 번에 하나씩 돌며 20분을 넘기면 끊는다.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from PIL import Image, ImageFilter
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

# ── 디자인 토큰 ────────────────────────────────────────────────────────────
FONT = "맑은 고딕"
MONO = "Consolas"
NAVY = RGBColor(0x13, 0x29, 0x4B)
NAVY_2 = RGBColor(0x24, 0x3D, 0x66)
INK = RGBColor(0x1F, 0x2A, 0x3A)
MUTED = RGBColor(0x55, 0x61, 0x75)
SKY = RGBColor(0x5C, 0xB8, 0xF2)          # 하늘색 채움(강조 칸·띠·꼬리표)
SKY_D = RGBColor(0x1A, 0x6F, 0xC4)        # 흰 바탕 위 강조 글자
SKY_ON_DARK = RGBColor(0x8F, 0xCF, 0xF8)  # 남색 바탕 위 강조 글자
SKY_SOFT = RGBColor(0xE7, 0xF3, 0xFD)     # 연파랑 바탕(간지·강조 칸)
PANEL = RGBColor(0xF3, 0xF6, 0xF9)
LINE = RGBColor(0xD3, 0xD9, 0xE1)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
COVER_SUB = RGBColor(0xC6, 0xD0, 0xDE)
CODE_FG = RGBColor(0xE8, 0xEE, 0xF6)

SLIDE_W, SLIDE_H = 13.333, 7.5
MX = 0.6                       # 좌우 여백
CW = SLIDE_W - 2 * MX          # 내용 폭
TITLE_PT, MSG_PT = 28, 16
BODY_PT = 14
BODY_Y, BODY_END = 1.78, 6.95
LINE_SPACING = 1.22

BODY_KINDS = ("흐름", "카드", "비교", "표", "단계", "강조", "그림", "삽화", "풀이", "구조", "파이프라인", "관계도",
              "코드", "문답")
COUNTS = {"표지": (0, 0), "목차": (2, 9), "간지": (0, 0),
          "흐름": (2, 6), "카드": (2, 4), "비교": (2, 2), "표": (2, 9), "단계": (3, 5), "강조": (0, 3),
          "그림": (0, 4), "삽화": (0, 16), "풀이": (2, 6), "구조": (2, 12), "파이프라인": (3, 7), "관계도": (2, 8),
          "코드": (0, 4), "문답": (2, 5)}
KEYS = {"유형", "메시지", "노트", "요소", "아이콘", "그림", "문장", "기관", "과정", "부제", "번호", "구분",
        "머리", "영역", "연결", "사이", "코드", "라벨"}
NEED = {"표지": ("기관", "과정"), "강조": ("문장",), "문답": ("문장",), "그림": ("그림",), "삽화": ("그림",), "구조": ("영역",),
        "코드": ("코드",), "관계도": ("연결",)}
SKILL_DIR = Path(__file__).resolve().parent.parent
ICON_DIR = SKILL_DIR / "assets" / "icons" / "tabler-outline"
LOGO = SKILL_DIR / "assets" / "logo" / "uengine-logo.svg"
ICON_CACHE = Path(os.environ.get("DECK2PPTX_CACHE") or Path(tempfile.gettempdir()) / "deck2pptx_icons")
CHECK_ONLY = False      # --check: 캐시에 없는 그림은 메모리에서만 만들고, PPTX도 메모리에만 쓴다
RENDER_FONT_KEYS = ("malgun", "mono", "consol", "menlo", "courier")   # 렌더 PDF에 박혀도 되는 글꼴 이름의 낱말
GONE = {"핵심": "핵심 띠는 없앴다. 핵심 낱말은 `메시지`·요소 안에서 **굵게** 강조한다",
        "설명": "제목 아래 2~3줄 설명은 없앴다(2026-10-10). `메시지:`에 한 줄 · 한 문장으로 쓴다",
        "다음": "하단 넘기는 질문 상자는 없앴다(2026-10-10). 연결은 본문과 노트로 한다",
        "현재": "반복 목차는 없앴다(2026-10-10). 목차는 한 번, 단원은 `간지` 유형으로 나눈다"}


class DeckError(Exception):
    pass


@dataclass
class Item:
    title: str
    desc: str = ""
    tag: str = ""

    @property
    def strong(self) -> bool:
        return self.title.startswith("**") and self.title.endswith("**") and len(self.title) > 4

    @property
    def plain_title(self) -> str:
        return self.title[2:-2] if self.strong else self.title

    @property
    def lines(self) -> list[str]:
        return [ln for ln in self.desc.split(" / ") if ln] if self.desc else []


@dataclass
class Slide:
    no: int
    title: str
    line: int
    fields: dict = field(default_factory=dict)
    items: list = field(default_factory=list)

    @property
    def kind(self) -> str:
        return self.fields.get("유형", "")

    @property
    def icons(self) -> list[str]:
        return [n.strip() for n in self.fields.get("아이콘", "").split(",") if n.strip()]


# ── 덱 MD 읽기 ─────────────────────────────────────────────────────────────
SLIDE_RE = re.compile(r"^##\s+SLIDE\s+(\d+)\s*[—–-]\s*(.+?)\s*$")
FIELD_RE = re.compile(r"^-\s*([^:：]+?)\s*[:：]\s*(.*)$")
ITEM_RE = re.compile(r"^\s+(?:\d+\.|-)\s+(.+)$")


def parse(md_path: Path) -> list[Slide]:
    slides: list[Slide] = []
    cur: Slide | None = None
    in_screen = in_items = False
    for ln, raw in enumerate(md_path.read_text(encoding="utf-8").splitlines(), 1):
        m = SLIDE_RE.match(raw)
        if m:
            cur = Slide(int(m.group(1)), m.group(2), ln)
            slides.append(cur)
            in_screen = in_items = False
            continue
        if raw.startswith("#"):
            in_screen = cur is not None and raw.strip() == "### 화면 내용"
            in_items = False
            continue
        if not in_screen or not raw.strip():
            continue
        im = ITEM_RE.match(raw)
        if in_items and im:
            parts = [p.strip() for p in re.split(r"(?<=\s)\|(?=\s|$)", " " + im.group(1))]   # 빈 칸(`a | | c`, `| b | c`)도 칸으로 센다
            if len(parts) > 3:
                raise DeckError(f"{md_path.name}:{ln} SLIDE {cur.no:02d} 요소 칸이 3개를 넘음: {raw.strip()}")
            cur.items.append(Item(*parts))
            continue
        fm = FIELD_RE.match(raw)
        if not fm:
            raise DeckError(f"{md_path.name}:{ln} SLIDE {cur.no:02d} 화면 내용에서 읽을 수 없는 줄: {raw.strip()}")
        key, val = fm.group(1).strip(), fm.group(2).strip()
        if key in GONE:
            raise DeckError(f"{md_path.name}:{ln} SLIDE {cur.no:02d} `{key}` 칸은 쓰지 않음 — {GONE[key]}")
        if key not in KEYS:
            raise DeckError(f"{md_path.name}:{ln} SLIDE {cur.no:02d} 모르는 칸 「{key}」 (허용: {', '.join(sorted(KEYS))})")
        in_items = key == "요소"
        if not in_items:
            cur.fields[key] = val
    if not slides:
        raise DeckError(f"{md_path.name}: `## SLIDE NN — 제목` 장이 없음")
    return slides


def plain(s: str) -> str:
    return s.replace("**", "")


def links_of(sl: Slide) -> list[tuple[str, str, str, str]]:
    """`연결: A > B : 라벨 ; C => D : 라벨` → (A, 종류, B, 라벨). `>`는 데이터, `=>`는 명령."""
    out = []
    for part in sl.fields.get("연결", "").split(";"):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(.+?)\s+(=>|>)\s+(.+?)(?:\s+:\s+(.*))?$", part)
        if not m:
            raise DeckError(f"SLIDE {sl.no:02d} `연결:`을 읽을 수 없음(`A > B : 라벨` 꼴, 기호 앞뒤는 띄운다): {part}")
        out.append((m.group(1).strip(), m.group(2), m.group(3).strip(), (m.group(4) or "").strip()))
    return out


def validate(slides: list[Slide], md_path: Path) -> None:
    errs = []
    for i, sl in enumerate(slides):
        where = f"{md_path.name}:{sl.line} SLIDE {sl.no:02d}"
        if sl.kind not in COUNTS:
            errs.append(f"{where} 유형 「{sl.kind}」 없음/모름 (허용: {', '.join(COUNTS)})")
            continue
        if i == 0 and sl.kind != "표지":
            errs.append(f"{where} 첫 장은 표지여야 함")
        for k in NEED.get(sl.kind, ()):
            if not sl.fields.get(k):
                errs.append(f"{where} {sl.kind} 장에 `{k}:`가 없음")
        texts = [sl.title, *sl.fields.values(), *(f"{it.title}{it.desc}{it.tag}" for it in sl.items)]
        if any("\u2212" in x for x in texts if isinstance(x, str) and x is not sl.fields.get("노트")):
            errs.append(f"{where} 유니코드 빼기표(−, U+2212)가 있음 — 덱 글꼴에 없어 렌더가 다른 글꼴로 바뀐다. 하이픈(-)으로 쓴다")
        if sl.kind in BODY_KINDS:
            msg = plain(sl.fields.get("메시지", ""))
            if not msg:
                errs.append(f"{where} 본문 장에 `메시지:`(거버닝 메시지 한 줄 · 한 문장)가 없음")
            elif re.search(r"(다|요|까|음|함)[.?!]\s+\S", msg):
                errs.append(f"{where} 메시지가 두 문장임(한 문장으로 쓴다): {msg}")
        lo, hi = COUNTS[sl.kind]
        if not lo <= len(sl.items) <= hi:
            errs.append(f"{where} {sl.kind} 요소 {len(sl.items)}개 (허용 {lo}~{hi})")
        if sl.kind in ("그림", "삽화"):
            src = sl.fields.get("그림", "")
            if src and not (md_path.parent / src).is_file():
                errs.append(f"{where} 그림 파일 없음: {src}")
        for name in sl.icons:
            if not (ICON_DIR / f"{name}.svg").is_file():
                errs.append(f"{where} 아이콘 「{name}」 없음 ({ICON_DIR.name} 폴더의 파일 이름에서 고른다)")
        n_ic, n_it = len(sl.icons), len(sl.items)
        if sl.kind == "표지":
            ok = 1 <= n_ic <= 3
        elif sl.kind in ("흐름", "카드", "비교", "표", "단계"):
            ok = n_ic in (0, n_it)
        elif sl.kind in ("강조", "관계도"):
            ok = n_ic in (0, n_it)
        elif sl.kind == "파이프라인":
            ok = n_ic == n_it
        else:
            ok = n_ic == 0
        if not ok:
            errs.append(f"{where} {sl.kind} 장 `아이콘:` {n_ic}개 (표지 1~3개, 파이프라인은 요소 수와 같게, 흐름·카드·비교·표·단계·강조·관계도는 요소 수와 같거나 0개, 그 밖은 0개)")
        if sl.kind == "삽화":
            if sl.fields.get("라벨", "보통") not in ("보통", "큰"):
                errs.append(f"{where} 삽화의 `라벨:`은 `보통` 또는 `큰`이어야 함")
            for it in sl.items:
                if not re.fullmatch(r"\s*\d{1,3}(\.\d+)?\s*,\s*\d{1,3}(\.\d+)?(\s*,\s*\d{1,3}(\.\d+)?)?\s*", it.tag or ""):
                    errs.append(f"{where} 삽화 라벨 「{it.plain_title}」의 셋째 칸은 `x,y` 또는 `x,y,폭`(그림 상자 기준 0~100)이어야 함")
        if sl.kind == "파이프라인":
            zones = [z.strip() for z in sl.fields.get("영역", "").split("|") if z.strip()]
            tags = [it.tag for it in sl.items]
            if zones:
                for it in sl.items:
                    if it.tag not in zones:
                        errs.append(f"{where} 파이프라인 요소 「{it.plain_title}」의 영역 「{it.tag}」이 `영역:`에 없음")
                runs = [t for k, t in enumerate(tags) if k == 0 or tags[k - 1] != t]
                if len(runs) != len(set(runs)):
                    errs.append(f"{where} 파이프라인의 같은 영역 요소는 이어서 놓아야 함(영역이 끊겼다 다시 나옴)")
            between = [b for b in sl.fields.get("사이", "").split("|")] if sl.fields.get("사이") else []
            if between and len(between) != n_it - 1:
                errs.append(f"{where} `사이:` {len(between)}개 (요소 사이의 수 {n_it - 1}개와 같아야 함)")
        if sl.kind == "관계도":
            names = [it.plain_title for it in sl.items]
            for it in sl.items:
                if not re.fullmatch(r"\s*\d{1,3}(\.\d+)?\s*,\s*\d{1,3}(\.\d+)?\s*", it.tag or ""):
                    errs.append(f"{where} 관계도 요소 「{it.plain_title}」의 셋째 칸은 `x,y`(본문 영역 기준 0~100)여야 함")
            try:
                for a, _, b, _ in links_of(sl):
                    for nm in (a, b):
                        if nm not in names:
                            errs.append(f"{where} `연결:`의 「{nm}」이 요소 이름에 없음")
            except DeckError as e:
                errs.append(str(e))
        if sl.kind == "구조":
            zones = [z.strip() for z in sl.fields.get("영역", "").split("|")]
            names = [it.plain_title for it in sl.items]
            for it in sl.items:
                if it.tag not in zones:
                    errs.append(f"{where} 구조 요소 「{it.plain_title}」의 영역 「{it.tag}」이 `영역:`에 없음")
            try:
                for a, _, b, _ in links_of(sl):
                    for nm in (a, b):
                        if nm not in names:
                            errs.append(f"{where} `연결:`의 「{nm}」이 요소 이름에 없음")
            except DeckError as e:
                errs.append(str(e))
    if errs:
        raise DeckError("덱 MD 규칙 위반:\n  " + "\n  ".join(errs))


# ── 글자 넘침 추정 ─────────────────────────────────────────────────────────
def char_em(ch: str) -> float:
    o = ord(ch)
    if ch == " ":
        return 0.3
    if 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F or 0x4E00 <= o <= 0x9FFF or o >= 0xFF00:
        return 1.0
    if ch in "→←↔·—–…「」『』○●■□▶•":
        return 1.0
    if ch.isupper() or ch.isdigit():
        return 0.62
    return 0.52


def text_w(text: str, pt: float) -> float:
    return sum(char_em(c) for c in plain(text)) * pt / 72


def wrap_widths(text: str, pt: float, width_in: float) -> list[float]:
    """상자 폭에서 줄바꿈된 줄마다의 글자 폭(인치)."""
    per_em = pt / 72
    out = []
    for para in plain(text).split("\n"):
        cur = 0.0
        for word in para.split(" "):
            w = sum(char_em(c) for c in word) * per_em
            sp = 0.3 * per_em if cur else 0
            if cur + sp + w <= width_in:
                cur += sp + w
            elif w <= width_in:
                out.append(cur)
                cur = w
            else:  # 긴 낱말은 글자 단위로 끊긴다
                for c in word:
                    cw = char_em(c) * per_em
                    if cur + cw > width_in:
                        out.append(cur)
                        cur = 0
                    cur += cw
        out.append(cur)
    return out


def line_count(text: str, pt: float, width_in: float) -> int:
    return len(wrap_widths(text, pt, width_in))


class Fit:
    """만든 상자마다 넘침을 추정해 모아 두고, 끝에 한꺼번에 실패시킨다."""

    def __init__(self):
        self.errs: list[str] = []

    def check(self, slide_no, name, text, pt, w, h, max_lines=None, first_pt=None, mono=False):
        inner_w, inner_h = w - 0.2, h - 0.1
        if mono:
            inner_w /= 1.12        # 고정폭 글꼴은 영문·기호가 넓다
        paras = text.split("\n")
        if first_pt and len(paras) > 1:   # 첫 문단(요소 제목)만 큰 글자인 상자
            n0, n1 = line_count(paras[0], first_pt, inner_w), line_count("\n".join(paras[1:]), pt, inner_w)
            n, need = n0 + n1, (n0 * first_pt + n1 * pt) * LINE_SPACING / 72
        else:
            n = line_count(text, first_pt or pt, inner_w)
            need = n * (first_pt or pt) * LINE_SPACING / 72
        if need > inner_h + 1e-6 or (max_lines and n > max_lines):
            self.errs.append(f"SLIDE {slide_no:02d} {name}: {n}줄 ≈ {need:.2f}in > 상자 {inner_h:.2f}in"
                             f"{f' (최대 {max_lines}줄)' if max_lines else ''} — {plain(text)[:40]}")


FIT = Fit()
DECK: dict = {}     # 덱 전체에 걸친 값(표지의 기관명 등). build()가 채운다


# ── 도형 도우미 ────────────────────────────────────────────────────────────
def set_font(run, size, color, bold=False, face=FONT):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    f.name = face
    rpr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = rpr.makeelement(qn(tag), {})
            rpr.append(el)
        el.set("typeface", FONT)      # 한글은 고정폭 글꼴 상자에서도 덱 글꼴로


UNIT_GLUE = re.compile(r"(\d) (℃|%|bar\b|mm/s|ms\b|Hz\b|초|분|시간|장\b|개\b|번\b)")
TAIL_SHRINK = 1.0   # 꼬리 줄을 없애려고 글자를 줄여 보는 한도(pt)


def tail_lines(text: str, pt: float, width_in: float, skip_first: bool) -> int:
    """마지막 줄이 짧은 낱말 하나뿐인 문단(꼬리 줄)의 수. 줄바꿈은 띄어쓰기 단위(eaLnBrk=0과 같다)."""
    n = 0
    for i, para in enumerate(text.split("\n")):
        if skip_first and i == 0:
            continue
        widths = wrap_widths(para, pt, width_in)
        words = plain(para).split()
        if len(widths) < 2 or not words:
            continue
        last_w = sum(char_em(c) for c in words[-1]) * pt / 72
        if widths[-1] <= last_w + 0.01 and widths[-1] < max(0.55, 0.18 * width_in):   # 마지막 줄 = 짧은 낱말 하나
            n += 1
    return n


def fit_tail(text: str, size: float, w: float, first_size, face) -> float:
    """꼬리 줄이 있으면 글자를 0.5pt씩 TAIL_SHRINK까지 줄여 꼬리가 사라지는 크기를 찾는다. 없으면 원래 크기."""
    if face != FONT or "\n" not in text and line_count(text, size, w - 0.2) < 2:
        return size
    skip = bool(first_size)
    base = tail_lines(text, size, w - 0.2, skip)
    if not base:
        return size
    pt = size - 0.5
    while pt >= size - TAIL_SHRINK - 1e-6:
        if tail_lines(text, pt, w - 0.2, skip) < base:
            return pt
        pt -= 0.5
    return size


def add_text(sl, x, y, w, h, text, size, color, *, bold=False, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, hi_color=SKY_D, name=None, slide_no=0, max_lines=None,
             space_after=0, first_size=None, first_color=None, face=FONT):
    text = UNIT_GLUE.sub("\\1\u00a0\\2", text)   # 숫자와 단위(55 ℃, 46.2 %)가 두 줄로 갈리지 않게 붙인다
    if not max_lines or max_lines > 1:
        size = fit_tail(text, size, w, first_size, face)
    if name:
        FIT.check(slide_no, name, text, size, w, h, max_lines, first_size, mono=face == MONO)
    tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.1)
    tf.margin_top = tf.margin_bottom = Inches(0.05)
    for pi, para_text in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if pi == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = 1.1
        p._p.get_or_add_pPr().set("eaLnBrk", "0")   # 한글 낱말을 글자 사이에서 자르지 않는다(줄은 띄어쓰기에서만 바뀐다)
        if space_after:
            p.space_after = Pt(space_after)
        first = bool(first_size) and pi == 0
        psize = first_size if first else size
        if para_text.startswith("• ") and align == PP_ALIGN.LEFT:   # 둘째 줄이 글머리표 뒤 글자에 맞춰 시작하게(내어쓰기)
            hang = Emu(int(Pt(psize) * 0.9))
            p._p.get_or_add_pPr().set("marL", str(hang))
            p._p.get_or_add_pPr().set("indent", str(-hang))
        base = (first_color or color) if first else color
        for k, chunk in enumerate(para_text.split("**")):
            if not chunk:
                continue
            segs = [chunk] if face != MONO else [m for m in re.split(r"([^\x00-\x7f]+)", chunk) if m]
            for seg in segs:   # 고정폭 글꼴에 없는 글자(℃ · 한글 · 화살표)는 덱 글꼴로 그려 다른 글꼴로 떨어지지 않게 한다
                r = p.add_run()
                r.text = seg
                set_font(r, psize, hi_color if k % 2 else base, bold=bold or first or bool(k % 2),
                         face=FONT if face == MONO and ord(seg[0]) > 0x7f else face)
    return tb


def add_box(sl, x, y, w, h, fill, *, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06):
    sh = sl.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line[0]
        sh.line.width = Pt(line[1])
    # 테마 스타일 참조(p:style)가 그림자·테두리를 다시 입히므로 지운다. 채움·선은 위에서 직접 정했다.
    style = sh._element.find(qn("p:style"))
    if style is not None:
        sh._element.remove(style)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = radius
    return sh


def add_arrow(sl, x1, y1, x2, y2, color, width, dashed=False):
    cn = sl.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    cn.line.color.rgb = color
    cn.line.width = Pt(width)
    if dashed:
        cn.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    style = cn._element.find(qn("p:style"))
    if style is not None:
        cn._element.remove(style)
    ln = cn.line._get_or_add_ln()
    ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"}))
    return cn


def set_bg(sl, color):
    bg = sl.background.fill
    bg.solid()
    bg.fore_color.rgb = color


def svg_png(src: Path, color: RGBColor, key: str, scale: float, stroke: float | None = None) -> Path:
    if not src.is_file():
        raise DeckError(f"그림 파일 없음: {src}")
    out = ICON_CACHE / f"{key}_{color}_{stroke}.png"
    if not out.exists():
        svg = src.read_text(encoding="utf-8").replace("currentColor", f"#{color}")
        if stroke:
            svg = svg.replace('stroke-width="2"', f'stroke-width="{stroke}"')
        doc = pymupdf.open(stream=svg.encode("utf-8"), filetype="svg")
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True)
        if CHECK_ONLY:
            return io.BytesIO(pix.tobytes("png"))
        ICON_CACHE.mkdir(parents=True, exist_ok=True)
        pix.save(out)
    return out


def pic_src(x):
    """add_picture에 넘길 것: 파일이면 경로 문자열, 메모리 그림이면 그대로."""
    return str(x) if isinstance(x, Path) else x


def add_icon(sl, name, cx, cy, size, color, stroke=1.6):
    """(cx, cy)를 가운데로 아이콘 하나. 이름표 「아이콘:」으로 저장본 검사에서 캡처와 구분한다."""
    png = svg_png(ICON_DIR / f"{name}.svg", color, name, 24, stroke)   # 24px → 576px
    pic = sl.shapes.add_picture(pic_src(png), Inches(cx - size / 2), Inches(cy - size / 2), Inches(size), Inches(size))
    pic.name = f"아이콘:{name}"
    return pic


def chip(sl, x, y, text, strong, slide_no, w=None, size=12, limit=None):
    w = w or max(0.9, text_w(text, size) + 0.4)
    if limit and w > limit + 1e-6:      # 꼬리표가 담긴 칸보다 넓으면 밖으로 넘친다
        FIT.errs.append(f"SLIDE {slide_no:02d} 꼬리표: 폭 {w:.2f}in > 칸 {limit:.2f}in — {plain(text)[:40]}")
    h = 0.32 if size <= 12 else 0.38
    add_box(sl, x, y, w, h, SKY if strong else LINE, radius=0.5)
    add_text(sl, x, y, w, h, text, size, NAVY, bold=True, align=PP_ALIGN.CENTER,
             anchor=MSO_ANCHOR.MIDDLE, name="꼬리표", slide_no=slide_no, max_lines=1)
    return w


def bullets(lines: list[str]) -> str:
    return "\n".join(f"• {ln}" for ln in lines)


def notes(sl, s: Slide):
    """발표자 노트. 덱 MD에서는 한 줄이고, ` / `(앞뒤 공백)가 노트 안의 줄바꿈이다(오프라인 강의 메모, 2026-10-28)."""
    if s.fields.get("노트"):
        sl.notes_slide.notes_text_frame.text = s.fields["노트"].replace(" / ", "\n")


def page_no(sl, page: int):
    add_text(sl, SLIDE_W - MX - 0.8, 7.08, 0.9, 0.3, str(page), 10, MUTED, align=PP_ALIGN.RIGHT)


def frame(sl, s: Slide, page: int) -> tuple[float, float]:
    """본문 장의 틀: 제목 → 거버닝 메시지 한 줄 → (본문 영역). 본문 영역의 위·아래 y를 돌려준다."""
    set_bg(sl, WHITE)
    add_text(sl, MX - 0.1, 0.36, CW + 0.2, 0.66, s.title, TITLE_PT, NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE,
             hi_color=SKY_D, name="제목", slide_no=s.no, max_lines=1)
    add_text(sl, MX - 0.1, 1.02, CW + 0.2, 0.46, s.fields["메시지"], MSG_PT, MUTED, anchor=MSO_ANCHOR.MIDDLE,
             hi_color=SKY_D, name="메시지(한 줄 · 한 문장)", slide_no=s.no, max_lines=1)
    add_box(sl, MX, 1.54, CW, 0.02, LINE, shape=MSO_SHAPE.RECTANGLE)
    page_no(sl, page)
    notes(sl, s)
    return BODY_Y, BODY_END


# ── 표지 · 목차 · 간지 ─────────────────────────────────────────────────────
def render_cover(sl, s: Slide, _page):
    set_bg(sl, NAVY)
    org = s.fields["기관"]
    add_text(sl, MX - 0.1, 0.92, 9.0, 0.5, org, 20, SKY_ON_DARK, bold=True, name="기관", slide_no=s.no, max_lines=1)
    add_box(sl, MX, 1.44, text_w(org, 20) + 0.1, 0.045, SKY, shape=MSO_SHAPE.RECTANGLE)
    add_text(sl, MX, 1.86, 8.6, 0.46, s.fields["과정"], 18, SKY_ON_DARK, bold=True,
             name="과정", slide_no=s.no, max_lines=1)
    lines = s.title.split(" / ")
    add_text(sl, MX - 0.1, 2.62, 9.2, 2.1, "\n".join(lines), 40, WHITE, bold=True, hi_color=SKY_ON_DARK,
             name="표지 제목(한 줄을 넘으면 ` / `로 끊을 자리를 정한다)", slide_no=s.no, max_lines=len(lines))
    if s.fields.get("부제"):
        add_text(sl, MX - 0.1, 4.82, 9.2, 0.8, s.fields["부제"], 19, COVER_SUB,
                 name="표지 부제", slide_no=s.no, max_lines=2)
    logo = sl.shapes.add_picture(pic_src(svg_png(LOGO, WHITE, "logo-uengine", 1.2)), Inches(8.0), Inches(6.2),
                                 width=Inches(1.45))
    logo.name = "로고:uEngine"
    icons = s.icons
    t, gap, cx = 1.3, 0.5, 11.0
    top = (SLIDE_H - (t * len(icons) + gap * (len(icons) - 1))) / 2
    for i, name in enumerate(icons):
        y, last = top + i * (t + gap), i == len(icons) - 1
        add_box(sl, cx - t / 2, y, t, t, SKY if last else NAVY_2, shape=MSO_SHAPE.RECTANGLE)
        add_icon(sl, name, cx, y + t / 2, t * 0.6, NAVY if last else SKY, 1.5)
        if not last:
            add_box(sl, cx - 0.17, y + t + 0.08, 0.34, gap - 0.16, SKY, shape=MSO_SHAPE.DOWN_ARROW)
    notes(sl, s)


def render_agenda(sl, s: Slide, page):
    """목차. 덱에 한 번만 둔다. 요소는 `단원명` 또는 `단원명 | 구분`."""
    set_bg(sl, WHITE)
    add_text(sl, MX - 0.1, 0.36, CW + 0.2, 0.66, s.title, TITLE_PT, NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE,
             name="제목", slide_no=s.no, max_lines=1)
    add_box(sl, MX, 1.2, CW, 0.02, LINE, shape=MSO_SHAPE.RECTANGLE)
    top = 1.35
    n = len(s.items)
    rh = min(0.8, (BODY_END - top) / n)
    y0 = top + (BODY_END - top - rh * n) / 2
    for i, it in enumerate(s.items, 1):
        y = y0 + (i - 1) * rh
        add_text(sl, MX, y, 0.9, rh, f"{i:02d}", 22, SKY_D, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        add_text(sl, MX + 0.95, y, CW - 0.95 - (1.9 if it.desc else 0.1), rh, it.plain_title, 19, NAVY, bold=True,
                 anchor=MSO_ANCHOR.MIDDLE, name=f"줄{i} 단원명", slide_no=s.no, max_lines=2)
        if it.desc:
            chip(sl, MX + CW - 1.7, y + rh / 2 - 0.16, it.desc, False, s.no, w=1.5)
        if i < n:
            add_box(sl, MX, y + rh - 0.01, CW, 0.015, LINE, shape=MSO_SHAPE.RECTANGLE)
    page_no(sl, page)
    notes(sl, s)


def render_divider(sl, s: Slide, _page):
    """단원 간지: 연한 배경에 (번호와) 단원명. 본문과 구별되는 장의 전환."""
    set_bg(sl, SKY_SOFT)
    org = DECK.get("기관", "")
    if org:   # 표지와 같은 자리 · 같은 틀의 기관명
        add_text(sl, MX - 0.1, 0.42, 9.0, 0.5, org, 20, SKY, bold=True, name="간지 기관", slide_no=s.no, max_lines=1)
        add_box(sl, MX, 0.94, text_w(org, 20) + 0.1, 0.045, SKY, shape=MSO_SHAPE.RECTANGLE)
    x = MX + 0.2
    if s.fields.get("번호"):
        add_text(sl, MX, 2.35, 2.6, 1.9, s.fields["번호"], 88, SKY, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        x = MX + 2.7
    lines = s.title.split(" / ")
    add_text(sl, x, 2.2, SLIDE_W - MX - x, 2.2, "\n".join(lines), 34, NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE,
             name="간지 단원명(한 줄을 넘으면 ` / `로 끊는다)", slide_no=s.no, max_lines=len(lines))
    y = 4.55
    if s.fields.get("구분"):
        chip(sl, x + 0.1, y, s.fields["구분"], True, s.no, size=13)
        y += 0.5
    if s.fields.get("부제"):
        add_text(sl, x, y, SLIDE_W - MX - x, 0.5, s.fields["부제"], 17, MUTED, name="간지 부제",
                 slide_no=s.no, max_lines=1)
    notes(sl, s)


# ── 본문 유형 ──────────────────────────────────────────────────────────────
FILL = 0.8   # 카드 · 비교 · 흐름 · 단계: 본문 영역 높이의 이만큼까지 글자를 키워 채운다(내용이 적어 위아래가 비지 않게)


def grow(base: float, cap: float, height_at, avail: float, step: float = 0.5, tails=None) -> float:
    """base pt에서 cap pt까지 step씩 키워 보며, height_at(pt)가 avail * FILL 안에 들고
    tails(pt)(꼬리 줄의 수)가 base보다 늘지 않는 가장 큰 크기를 돌려준다. base에서도 넘치면 base 그대로(넘침은 Fit 검사가 잡는다)."""
    best, pt = base, base
    t0 = tails(base) if tails else 0
    while pt <= cap + 1e-6:
        if height_at(pt) <= avail * FILL and (not tails or tails(pt) <= t0):
            best = pt
        pt += step
    return best


def item_block(sl, x, y, w, h, it: Item, slide_no, name, *, title_pt=17, desc_pt=BODY_PT, align=PP_ALIGN.LEFT,
               bullet=True, anchor=MSO_ANCHOR.TOP):
    """요소 제목(굵게) + 설명 여러 줄을 한 상자에."""
    body = bullets(it.lines) if bullet and len(it.lines) > 1 else "\n".join(it.lines)
    text = it.plain_title + (f"\n{body}" if body else "")
    add_text(sl, x, y, w, h, text, desc_pt, INK, align=align, first_size=title_pt, first_color=NAVY,
             name=name, slide_no=slide_no, space_after=4, anchor=anchor)


def render_flow(sl, s, page):
    top, end = frame(sl, s, page)
    n, gap = len(s.items), 0.42
    w = (CW - gap * (n - 1)) / n
    d = 0.8 if s.icons else 0
    small = n >= 5
    base = 12.5 if small else 13.5

    def flow_h(pt):
        tpt = pt + (3 if small else 3.5)
        need = max(line_count("\n".join(it.lines) or " ", pt, w - 0.36) for it in s.items)
        tl = max(line_count(it.plain_title, tpt, w - 0.36) for it in s.items)
        return 0.3 + d + 0.25 + tl * tpt * LINE_SPACING / 72 + 0.4 + need * pt * LINE_SPACING / 72 + 0.3

    desc_pt = grow(base, base + 3, flow_h, end - top,
                   tails=lambda pt: sum(tail_lines("\n".join(it.lines), pt, w - 0.36, False) for it in s.items))
    h = min(end - top, flow_h(desc_pt))
    y = top + (end - top - h) / 2
    for i, it in enumerate(s.items):
        x = MX + i * (w + gap)
        add_box(sl, x, y, w, h, SKY_SOFT if it.strong else PANEL, line=(SKY, 2) if it.strong else None, radius=0.05)
        ty = y + 0.2
        if s.icons:
            add_box(sl, x + w / 2 - d / 2, ty, d, d, SKY if it.strong else WHITE, shape=MSO_SHAPE.OVAL)
            add_icon(sl, s.icons[i], x + w / 2, ty + d / 2, d * 0.58, NAVY)
            ty += d + 0.08
        item_block(sl, x + 0.08, ty, w - 0.16, y + h - ty - 0.08, it, s.no, f"요소{i + 1}",
                   title_pt=desc_pt + (3 if small else 3.5), desc_pt=desc_pt, align=PP_ALIGN.CENTER, bullet=False)
        if i < n - 1:
            add_box(sl, x + w + 0.07, y + h / 2 - 0.15, gap - 0.14, 0.3, NAVY, shape=MSO_SHAPE.RIGHT_ARROW)


def render_cards(sl, s, page):
    top, end = frame(sl, s, page)
    n, gap = len(s.items), 0.3
    w = (CW - gap * (n - 1)) / n
    d = 0.8
    base = 13.5 if n == 4 else BODY_PT

    def card_h(pt):
        tpt = pt + 4
        need = max(line_count(it.plain_title, tpt, w - 0.56) * tpt + line_count(
            (bullets(it.lines) if len(it.lines) > 1 else "\n".join(it.lines)) or " ", pt, w - 0.56) * pt
            for it in s.items) * LINE_SPACING / 72
        return (0.22 + (d + 0.1 if s.icons else 0) + need + 0.45
                + (0.55 if any(it.tag for it in s.items) else 0.12))   # 내용이 적으면 빈 칸을 늘이지 않는다

    desc_pt = grow(base, base + 4, card_h, end - top,
                   tails=lambda pt: sum(tail_lines(bullets(it.lines) if len(it.lines) > 1 else "\n".join(it.lines), pt, w - 0.56, False)
                                        for it in s.items))
    h = min(end - top, card_h(desc_pt))
    top += (end - top - h) / 2
    for i, it in enumerate(s.items):
        x = MX + i * (w + gap)
        add_box(sl, x, top, w, h, WHITE, line=(SKY, 2.25) if it.strong else (LINE, 1.25), radius=0.04)
        ty = top + 0.22
        if s.icons:
            add_box(sl, x + 0.25, ty, d, d, SKY if it.strong else SKY_SOFT, shape=MSO_SHAPE.OVAL)
            add_icon(sl, s.icons[i], x + 0.25 + d / 2, ty + d / 2, d * 0.58, NAVY)
            ty += d + 0.1
        bottom = top + h - (0.55 if it.tag else 0.12)
        item_block(sl, x + 0.18, ty, w - 0.36, bottom - ty, it, s.no, f"요소{i + 1}", title_pt=desc_pt + 4,
                   desc_pt=desc_pt)
        if it.tag:
            chip(sl, x + 0.25, top + h - 0.47, it.tag, it.strong, s.no, limit=w - 0.5)


def render_compare(sl, s, page):
    top, end = frame(sl, s, page)
    gap = 0.8
    w = (CW - gap) / 2
    d = 0.8

    def cmp_h(pt):
        need = max(line_count(bullets(it.lines) or " ", pt, w - 0.8) for it in s.items)
        return (1.15 + need * (pt * LINE_SPACING + 6) / 72 + 0.35
                + (0.6 if any(it.tag for it in s.items) else 0.15))   # 내용이 적으면 빈 칸을 늘이지 않는다

    body_pt = grow(14.5, 18, cmp_h, end - top,
                   tails=lambda pt: sum(tail_lines(bullets(it.lines), pt, w - 0.8, False) for it in s.items))
    h = min(end - top, cmp_h(body_pt))
    top += (end - top - h) / 2
    for i, it in enumerate(s.items):
        x = MX + i * (w + gap)
        add_box(sl, x, top, w, h, SKY_SOFT if it.strong else PANEL, line=(SKY, 2.25) if it.strong else None,
                radius=0.04)
        tx = x + 0.3
        if s.icons:
            add_box(sl, tx, top + 0.22, d, d, SKY if it.strong else WHITE, shape=MSO_SHAPE.OVAL)
            add_icon(sl, s.icons[i], tx + d / 2, top + 0.22 + d / 2, d * 0.58, NAVY)
            tx += d + 0.15
        add_text(sl, tx, top + 0.22, x + w - tx - 0.2, d, it.plain_title, 20, NAVY, bold=True,
                 anchor=MSO_ANCHOR.MIDDLE, name=f"요소{i + 1} 제목", slide_no=s.no, max_lines=2)
        bottom = top + h - (0.6 if it.tag else 0.15)
        add_text(sl, x + 0.3, top + 1.15, w - 0.6, bottom - top - 1.15, bullets(it.lines), body_pt, INK,
                 name=f"요소{i + 1} 줄", slide_no=s.no, space_after=6)
        if it.tag:
            chip(sl, x + 0.35, top + h - 0.5, it.tag, it.strong, s.no, limit=w - 0.7)
    vx, vy = MX + w + gap / 2, top + h / 2
    add_box(sl, vx - 0.3, vy - 0.3, 0.6, 0.6, NAVY, shape=MSO_SHAPE.OVAL)
    add_text(sl, vx - 0.3, vy - 0.3, 0.6, 0.6, "vs", 14, WHITE, bold=True, align=PP_ALIGN.CENTER,
             anchor=MSO_ANCHOR.MIDDLE)


def render_table(sl, s, page):
    """`라벨 | 값 | 상태` 2~9줄. `머리: A | B | C`를 주면 머리줄을 그린다. 값은 줄 높이만큼 여러 줄."""
    top, end = frame(sl, s, page)
    head = [h.strip() for h in s.fields["머리"].split("|")] if s.fields.get("머리") else []
    n = len(s.items)
    hh = 0.44 if head else 0
    rh = min(1.0, (end - top - hh) / n)
    y0 = top + (end - top - hh - rh * n) / 2
    has_tag = any(it.tag for it in s.items)
    c1 = 3.3 if s.icons else 2.9
    c3 = 2.4 if has_tag else 0
    c2 = CW - c1 - c3
    lab_pt = 16 if rh >= 0.6 else 14.5
    val_pt = BODY_PT if rh >= 0.56 else 12.5
    if head:
        add_box(sl, MX, y0, CW, hh - 0.06, NAVY, radius=0.12)
        for hx, hw, txt in ((MX + 0.15, c1 - 0.15, head[0]), (MX + c1, c2, head[1] if len(head) > 1 else ""),
                            (MX + c1 + c2, c3, head[2] if len(head) > 2 else "")):
            if txt and hw > 0:
                add_text(sl, hx, y0, hw, hh - 0.06, txt, 13, WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE,
                         name="머리", slide_no=s.no, max_lines=1)
    for i, it in enumerate(s.items):
        y = y0 + hh + i * rh
        add_box(sl, MX, y + 0.035, CW, rh - 0.07, SKY_SOFT if it.strong else PANEL, radius=0.08)
        lx = MX + 0.15
        if s.icons:
            d = min(0.5, rh - 0.24)
            add_box(sl, lx, y + rh / 2 - d / 2, d, d, SKY if it.strong else WHITE, shape=MSO_SHAPE.OVAL)
            add_icon(sl, s.icons[i], lx + d / 2, y + rh / 2, d * 0.6, NAVY)
            lx += d + 0.1
        add_text(sl, lx, y, MX + c1 - lx, rh, it.plain_title, lab_pt, NAVY, bold=True,
                 anchor=MSO_ANCHOR.MIDDLE, name=f"줄{i + 1} 라벨", slide_no=s.no, max_lines=2)
        if it.desc:
            add_text(sl, MX + c1, y, c2 - 0.1, rh, "\n".join(it.lines), val_pt, INK, anchor=MSO_ANCHOR.MIDDLE,
                     name=f"줄{i + 1} 값", slide_no=s.no)
        if it.tag:
            add_text(sl, MX + c1 + c2, y, c3 - 0.1, rh, it.tag.replace(" / ", "\n"), 12.5,
                     SKY_D if it.strong else MUTED, bold=True, anchor=MSO_ANCHOR.MIDDLE,
                     name=f"줄{i + 1} 상태", slide_no=s.no, max_lines=3)


def render_steps(sl, s, page):
    top, end = frame(sl, s, page)
    n = len(s.items)
    w = CW / n
    d = 0.95
    base = 13 if n == 5 else 13.5

    def step_h(pt):
        need = max(line_count("\n".join(it.lines) or " ", pt, w - 0.36) for it in s.items)
        return d + 0.25 + 0.9 + need * pt * LINE_SPACING / 72 + 0.2

    desc_pt = grow(base, base + 3, step_h, end - top,
                   tails=lambda pt: sum(tail_lines("\n".join(it.lines), pt, w - 0.36, False) for it in s.items))
    h = min(end - top, step_h(desc_pt))
    y = top + (end - top - h) / 2
    add_box(sl, MX + w / 2, y + d / 2 - 0.02, CW - w, 0.04, LINE, shape=MSO_SHAPE.RECTANGLE)
    for i, it in enumerate(s.items):
        cx = MX + i * w + w / 2
        hot = it.strong
        add_box(sl, cx - d / 2, y, d, d, SKY if hot else WHITE, line=None if hot else (NAVY, 2), shape=MSO_SHAPE.OVAL)
        if s.icons:
            add_icon(sl, s.icons[i], cx, y + d / 2, d * 0.5, NAVY)
            bx, by = cx + d / 2 - 0.3, y - 0.05
            add_box(sl, bx, by, 0.38, 0.38, NAVY, shape=MSO_SHAPE.OVAL)
            add_text(sl, bx, by, 0.38, 0.38, str(i + 1), 12, WHITE, bold=True, align=PP_ALIGN.CENTER,
                     anchor=MSO_ANCHOR.MIDDLE)
        else:
            add_text(sl, cx - d / 2, y, d, d, str(i + 1), 26, NAVY, bold=True, align=PP_ALIGN.CENTER,
                     anchor=MSO_ANCHOR.MIDDLE)
        ly = y + d + 0.2
        item_block(sl, cx - w / 2 + 0.08, ly, w - 0.16, y + h - ly, it, s.no, f"단계{i + 1}",
                   title_pt=desc_pt + 3.5, desc_pt=desc_pt, align=PP_ALIGN.CENTER, bullet=False)


def render_statement(sl, s, page):
    top, end = frame(sl, s, page)
    lines = s.fields["문장"].split(" / ")
    n = len(s.items)
    band_h = 0.5 + 0.5 * len(lines)
    if not n:
        y = top + (end - top - band_h) / 2
        add_box(sl, MX, y, CW, band_h, SKY_SOFT, radius=0.05)
        add_text(sl, MX + 0.3, y, CW - 0.6, band_h, "\n".join(lines), 28, NAVY, bold=True, align=PP_ALIGN.CENTER,
                 anchor=MSO_ANCHOR.MIDDLE, name="강조 문장(넘으면 ` / `로 끊는다)", slide_no=s.no, max_lines=len(lines))
        return
    gap = 0.3
    w = (CW - gap * (n - 1)) / n
    d = 0.8 if s.icons else 0
    need = max(line_count("\n".join(it.lines) or " ", BODY_PT, w - d - 0.3) for it in s.items)
    item_h = 0.5 + need * BODY_PT * LINE_SPACING / 72 + 0.25
    y = top + max(0.0, (end - top - (band_h + 0.4 + item_h)) / 2)
    add_box(sl, MX, y, CW, band_h, SKY_SOFT, radius=0.05)
    add_text(sl, MX + 0.3, y, CW - 0.6, band_h, "\n".join(lines), 26, NAVY, bold=True, align=PP_ALIGN.CENTER,
             anchor=MSO_ANCHOR.MIDDLE, name="강조 문장(넘으면 ` / `로 끊는다)", slide_no=s.no, max_lines=len(lines))
    iy = y + band_h + 0.4
    for i, it in enumerate(s.items):
        x = MX + i * (w + gap)
        tx = x
        if s.icons:
            add_box(sl, x, iy, d, d, SKY if it.strong else SKY_SOFT, shape=MSO_SHAPE.OVAL)
            add_icon(sl, s.icons[i], x + d / 2, iy + d / 2, d * 0.58, NAVY)
            tx += d + 0.1
        item_block(sl, tx, iy - 0.05, x + w - tx, min(end - iy + 0.05, item_h + 0.2), it, s.no, f"보조{i + 1}",
                   bullet=False)


def render_picture(sl, s, page, base: Path):
    top, end = frame(sl, s, page)
    img = picture_file(base, s.fields["그림"])
    n = len(s.items)
    box_w, box_h = (7.9 if n else CW), end - top - 0.05
    pic = sl.shapes.add_picture(pic_src(img), Inches(MX), Inches(top))
    ratio = min(Inches(box_w) / pic.width, Inches(box_h) / pic.height)
    pic.width, pic.height = int(pic.width * ratio), int(pic.height * ratio)
    pic.top = Inches(top + (box_h - Emu(pic.height).inches) / 2)
    if not n:
        pic.left = Inches(MX + (box_w - Emu(pic.width).inches) / 2)
    pic.line.color.rgb = LINE
    pic.line.width = Pt(1)
    if not n:
        return
    px = MX + Emu(pic.width).inches + 0.4
    pw = SLIDE_W - MX - px
    rh = min(1.7, box_h / n)
    y0 = top + (box_h - rh * n) / 2
    for i, it in enumerate(s.items):
        y = y0 + i * rh
        hot = it.strong or i == 0
        add_box(sl, px, y + 0.06, 0.38, 0.38, SKY if hot else NAVY, shape=MSO_SHAPE.OVAL)
        add_text(sl, px, y + 0.06, 0.38, 0.38, str(i + 1), 12, NAVY if hot else WHITE,
                 bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        item_block(sl, px + 0.45, y, pw - 0.45, rh, it, s.no, f"짚을 점{i + 1}", bullet=False)


def picture_file(base: Path, rel: str) -> Path:
    """그림 파일 경로. SVG는 PNG로 바꿔 넣는다(PowerPoint · LibreOffice 어디서나 같은 모양)."""
    src = base / rel
    if src.suffix.lower() != ".svg":
        return src
    out = ICON_CACHE / f"illust_{abs(hash(str(src.resolve())))}_{int(src.stat().st_mtime)}.png"
    if not out.exists():
        doc = pymupdf.open(stream=src.read_bytes(), filetype="svg")
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=True)
        if CHECK_ONLY:
            return io.BytesIO(pix.tobytes("png"))
        ICON_CACHE.mkdir(parents=True, exist_ok=True)
        pix.save(out)
    return out


def render_illust(sl, s, page, base: Path):
    """삽화. 직접 그린 그림을 본문 영역에 깔고, 요소 `라벨 | 설명 | x,y[,폭]`를 그 위에 글상자로 얹는다.
    x · y는 그림 상자의 왼쪽 위를 0,0 · 오른쪽 아래를 100,100으로 본 글상자 **가운데 위** 지점, 폭은 그림 폭의 %(기본 16)."""
    top, end = frame(sl, s, page)
    box_w, box_h = CW, end - top
    pic = sl.shapes.add_picture(pic_src(picture_file(base, s.fields["그림"])), Inches(MX), Inches(top))
    ratio = min(Inches(box_w) / pic.width, Inches(box_h) / pic.height)
    pic.width, pic.height = int(pic.width * ratio), int(pic.height * ratio)
    pw, ph = Emu(pic.width).inches, Emu(pic.height).inches
    px, py = MX + (box_w - pw) / 2, top + (box_h - ph) / 2
    pic.left, pic.top = Inches(px), Inches(py)
    pic.name = "삽화:" + Path(s.fields["그림"]).name
    t_pt, d_pt = (16, 13) if s.fields.get("라벨") == "큰" else (13.5, 11)   # `라벨: 큰` = 라벨이 적고 그림이 큰 장
    ink = drawing_edges(picture_file(base, s.fields["그림"]), pw, ph)
    placed: list[tuple[str, list]] = []
    for i, it in enumerate(s.items):
        nums = [float(v) for v in it.tag.split(",")]
        w = pw * (nums[2] if len(nums) > 2 else 16) / 100
        small = not it.plain_title          # 이름 칸이 비면 설명 줄만 작은 글씨로 쓴다(그래프의 관계 이름처럼)
        text = "\n".join(it.lines) if small else it.plain_title + ("\n" + "\n".join(it.lines) if it.lines else "")
        n1 = 0 if small else line_count(it.plain_title, t_pt, w - 0.2)
        n2 = line_count("\n".join(it.lines), d_pt, w - 0.2) if it.lines else 0
        h = (n1 * t_pt + n2 * d_pt) * LINE_SPACING / 72 + 0.14
        x, y = px + pw * nums[0] / 100 - w / 2, py + ph * nums[1] / 100
        label = text.replace("\n", " ")
        add_text(sl, x, y, w, h, text, d_pt, NAVY if small else MUTED,
                 align=PP_ALIGN.CENTER, first_size=None if small else t_pt, first_color=SKY_D if it.strong else NAVY,
                 name=f"라벨 「{label}」", slide_no=s.no, space_after=1)
        rows = label_rows(x - px, y - py, w, it, t_pt, d_pt)
        hit = label_on_drawing(ink, rows)
        if hit:
            FIT.errs.append(f"SLIDE {s.no:02d} 삽화 라벨 「{label}」의 {hit}번째 줄이 그림의 선 · 아이콘과 겹치거나 "
                            f"{LABEL_GAP}인치 안으로 붙음(좌표를 옮기거나 폭을 바꾼다)")
        g = LABEL_GAP
        for name, other in placed:      # 라벨끼리도 LABEL_GAP만큼 떨어져야 한다
            if any(a[0] < b[2] + g and b[0] < a[2] + g and a[1] < b[3] + g and b[1] < a[3] + g for a in rows for b in other):
                FIT.errs.append(f"SLIDE {s.no:02d} 삽화 라벨 「{label}」이 라벨 「{name}」과 겹치거나 "
                                f"{LABEL_GAP}인치 안으로 붙음(좌표를 옮기거나 폭을 바꾼다)")
        placed.append((label, rows))


EDGE = 24          # 이웃 픽셀과 밝기가 이만큼 넘게 다르면 그림의 선 · 아이콘 · 글자의 가장자리다(흐린 선 약 30, 같은 색 칸 안은 0)
EDGE_SHARE = 0.01  # 라벨 한 줄의 글자 자리에서 가장자리 픽셀이 이만큼을 넘으면 겹친 것으로 본다(가는 선 하나가 지나가면 약 2%)
LABEL_GAP = 0.1    # 라벨 글자와 그림 사이에 둘 여백(인치). 글자 자리를 이만큼 넓혀 재므로 붙어 있어도 실패한다


def drawing_edges(png: Path, pw: float, ph: float):
    """그림을 1인치 = 100픽셀로 줄여 흰 바탕에 얹고, 가장자리 세기(0~255)만 남긴 흑백 그림. 같은 색으로 칠한 칸은 0이다."""
    im = Image.open(png).convert("RGBA").resize((round(pw * 100), round(ph * 100)))
    flat = Image.new("RGBA", im.size, (255, 255, 255, 255))
    flat.alpha_composite(im)
    return flat.convert("L").filter(ImageFilter.FIND_EDGES)


def label_rows(x, y, w, it, t_pt, d_pt) -> list[tuple[float, float, float, float]]:
    """라벨 글상자 안의 줄마다 글자가 차지하는 자리(가운데 맞춤)의 (왼, 위, 오른, 아래). 그림 왼쪽 위 기준 인치."""
    rows = [(lw, t_pt) for lw in wrap_widths(it.plain_title, t_pt, w - 0.2)] if it.plain_title else []
    if it.lines:
        rows += [(lw, d_pt) for lw in wrap_widths("\n".join(it.lines), d_pt, w - 0.2)]
    out, cy = [], y + 0.05
    for lw, pt in rows:
        lh = pt * LINE_SPACING / 72
        out.append((x + w / 2 - lw / 2, cy + lh * 0.15, x + w / 2 + lw / 2, cy + lh * 0.85))
        cy += lh
    return out


def label_on_drawing(edges, rows) -> int:
    """라벨의 줄마다 글자 자리를 그림의 가장자리와 맞대어, 겹치거나 붙은 첫 줄 번호를 돌려준다(없으면 0).
    글자 자리에 그림이 들어오면 겹침, 둘레 LABEL_GAP 안에 들어오면 붙음이다. 다만 라벨 전체의 위와 아래(각 3 × LABEL_GAP 안)를
    칸의 테두리가 가로지르면 칸 안에 쓴 글자(표의 행처럼)로 보고 붙음은 따지지 않는다."""
    def px(v):
        return round(v * 100)

    def clip(b):
        return max(1, b[0]), max(1, b[1]), min(edges.width - 1, b[2]), min(edges.height - 1, b[3])

    def share(box):
        if box[2] <= box[0] or box[3] <= box[1]:
            return 0.0
        hist = edges.crop(box).histogram()
        return sum(hist[EDGE + 1:]) / sum(hist)

    def border(box):        # 띠를 가로지르는 선이 글자 폭의 60 % 넘게 이어지는가
        if box[2] <= box[0] or box[3] <= box[1]:
            return False
        cols = edges.crop(box).point(lambda v: 255 if v > EDGE else 0).resize((box[2] - box[0], 1), Image.BOX)
        return sum(1 for v in cols.tobytes() if v) / cols.width > 0.6

    g = LABEL_GAP
    lx0, lx1 = min(r[0] for r in rows), max(r[2] for r in rows)
    top, bottom = rows[0][1], rows[-1][3]
    boxed = (border(clip((px(lx0), px(top - 3 * g), px(lx1), px(top))))           # 라벨 전체의 위와 아래를 칸 테두리가 가로지른다
             and border(clip((px(lx0), px(bottom), px(lx1), px(bottom + 3 * g)))))
    for k, (x0, y0, x1, y1) in enumerate(rows, 1):
        if share(clip((px(x0), px(y0), px(x1), px(y1)))) > EDGE_SHARE:
            return k
        if not boxed and share(clip((px(x0 - g), px(y0 - g), px(x1 + g), px(y1 + g)))) > EDGE_SHARE:
            return k
    return 0


def render_terms(sl, s, page):
    """용어 풀이. `용어 | 설명 여러 줄 | 정식 명칭(풀네임)`. 왼쪽에 용어와 풀네임, 오른쪽에 설명."""
    top, end = frame(sl, s, page)
    n = len(s.items)
    rh = min(1.5, (end - top) / n)
    y0 = top + (end - top - rh * n) / 2
    c1 = 3.8
    for i, it in enumerate(s.items):
        y = y0 + i * rh
        if it.strong:
            add_box(sl, MX, y + 0.03, CW, rh - 0.06, SKY_SOFT, radius=0.06)
        left = it.plain_title + (f"\n{it.tag}" if it.tag else "")
        add_text(sl, MX + 0.1, y, c1 - 0.2, rh, left, 11.5, MUTED, anchor=MSO_ANCHOR.MIDDLE, first_size=18,
                 first_color=NAVY, name=f"용어{i + 1}", slide_no=s.no, space_after=2)
        add_text(sl, MX + c1, y, CW - c1 - 0.1, rh, "\n".join(it.lines), BODY_PT, INK, anchor=MSO_ANCHOR.MIDDLE,
                 name=f"용어{i + 1} 설명", slide_no=s.no, space_after=3)
        if i < n - 1:
            add_box(sl, MX, y + rh - 0.01, CW, 0.015, LINE, shape=MSO_SHAPE.RECTANGLE)


def render_structure(sl, s, page):
    """구조도. `영역: A | B | C`가 왼쪽에서 오른쪽으로 놓이는 띠, 요소 `이름 | 설명 | 영역`이 그 띠 안의 상자,
    `연결: A > B : 라벨 ; C => D : 라벨`이 화살표(`>` 데이터 흐름 실선, `=>` 명령 흐름 점선)."""
    top, end = frame(sl, s, page)
    zones = [z.strip() for z in s.fields["영역"].split("|")]
    links = links_of(s)
    gap = 1.25 if links else 0.3
    zw = (CW - gap * (len(zones) - 1)) / len(zones)
    zh = end - top
    pos: dict[str, tuple[float, float, float, float]] = {}
    for zi, zone in enumerate(zones):
        zx = MX + zi * (zw + gap)
        add_box(sl, zx, top, zw, zh, PANEL, radius=0.03)
        add_text(sl, zx, top + 0.05, zw, 0.4, zone, 14, SKY_D, bold=True, align=PP_ALIGN.CENTER,
                 anchor=MSO_ANCHOR.MIDDLE, name="영역 이름", slide_no=s.no, max_lines=1)
        mine = [it for it in s.items if it.tag == zone]
        if not mine:
            continue
        vgap = 0.38 if links else 0.16
        area_top, area_h = top + 0.5, zh - 0.62
        bh = min(1.3, (area_h - vgap * (len(mine) - 1)) / len(mine))
        y = area_top + (area_h - (bh * len(mine) + vgap * (len(mine) - 1))) / 2
        for it in mine:
            bx, bw = zx + 0.2, zw - 0.4
            add_box(sl, bx, y, bw, bh, SKY_SOFT if it.strong else WHITE,
                    line=(SKY, 2) if it.strong else (LINE, 1.25), radius=0.08)
            text = it.plain_title + ("\n" + "\n".join(it.lines) if it.lines else "")
            add_text(sl, bx + 0.05, y, bw - 0.1, bh, text, 11.5, MUTED, align=PP_ALIGN.CENTER,
                     anchor=MSO_ANCHOR.MIDDLE, first_size=14.5, first_color=NAVY,
                     name=f"상자 「{it.plain_title}」", slide_no=s.no, space_after=1)
            pos[it.plain_title] = (bx, y, bw, bh)
            y += bh + vgap
    for a, kind, b, label in links:
        ax, ay, aw, ah = pos[a]
        bx, by, bw, bh = pos[b]
        cmd = kind == "=>"
        color, width = (SKY_D, 2.25) if cmd else (NAVY, 1.5)
        off = 0.16 if cmd else -0.16          # 같은 두 상자를 오가는 데이터·명령 화살표가 겹치지 않게
        if abs(ax - bx) < 0.01:               # 같은 영역: 위아래
            down = by > ay
            x = ax + aw / 2 + off * 2.5
            y1, y2 = (ay + ah, by) if down else (ay, by + bh)
            add_arrow(sl, x, y1, x, y2, color, width, dashed=cmd)
            lw = text_w(label, 10.5) + 0.25
            lx, ly = (x + 0.04 if cmd else x - lw - 0.04), (y1 + y2) / 2 - 0.15
        else:                                 # 다른 영역: 좌우
            right = bx > ax
            x1, x2 = (ax + aw, bx) if right else (ax, bx + bw)
            y1, y2 = ay + ah / 2 + off, by + bh / 2 + off
            add_arrow(sl, x1, y1, x2, y2, color, width, dashed=cmd)
            lw = abs(x2 - x1) + 0.3
            lx, ly = (x1 + x2) / 2 - lw / 2, (y1 + y2) / 2 + (0.02 if cmd else -0.32)
        if label:
            add_text(sl, lx, ly, lw, 0.3, label, 10.5, color, bold=True, align=PP_ALIGN.CENTER,
                     anchor=MSO_ANCHOR.MIDDLE, name=f"연결 라벨 「{label}」", slide_no=s.no, max_lines=1)


def render_pipeline(sl, s, page):
    """아이콘 파이프라인. 요소 `이름 | 설명 | 영역`이 한 줄의 관 위에 놓인 원(아이콘)이고, `영역:`이 원들을 묶는 바탕,
    `사이: 라벨 | 라벨`이 이웃한 원 사이의 관 위 글자다. 값이 왼쪽에서 오른쪽으로 한 방향으로 흐를 때 쓴다."""
    top, end = frame(sl, s, page)
    n = len(s.items)
    zones = [z.strip() for z in s.fields.get("영역", "").split("|") if z.strip()]
    between = [b.strip() for b in s.fields["사이"].split("|")] if s.fields.get("사이") else []
    cell = CW / n
    d = min(1.3, cell * 0.52)
    title_pt, desc_pt = (15, 12) if n >= 6 else (16.5, 13)
    need = max(line_count(it.plain_title, title_pt, cell - 0.4) * title_pt
               + line_count("\n".join(it.lines) or " ", desc_pt, cell - 0.4) * desc_pt for it in s.items)
    th = need * LINE_SPACING / 72 + 0.3
    head = 0.5 if zones else 0.1
    total = head + 0.5 + d + 0.2 + th + 0.15
    y0 = top + max(0.0, (end - top - total) / 2)
    cy = y0 + head + 0.5 + d / 2
    if zones:
        for zone in zones:
            idx = [i for i, it in enumerate(s.items) if it.tag == zone]
            if not idx:
                continue
            zx, zw = MX + idx[0] * cell + 0.07, (idx[-1] - idx[0] + 1) * cell - 0.14
            add_box(sl, zx, y0, zw, total, PANEL, radius=0.04)
            add_text(sl, zx, y0 + 0.06, zw, 0.4, zone, 14, SKY_D, bold=True, align=PP_ALIGN.CENTER,
                     anchor=MSO_ANCHOR.MIDDLE, name="영역 이름", slide_no=s.no, max_lines=1)
    add_box(sl, MX + cell / 2, cy - 0.08, CW - cell, 0.16, SKY, shape=MSO_SHAPE.RECTANGLE)    # 관
    for i, it in enumerate(s.items):
        cx = MX + cell * (i + 0.5)
        if i < n - 1:
            mx = cx + cell / 2
            add_box(sl, mx - 0.13, cy - 0.2, 0.26, 0.4, NAVY, shape=MSO_SHAPE.CHEVRON)
            if between and between[i]:
                add_text(sl, cx + d / 2 - 0.1, cy - 0.58, cell - d + 0.2, 0.34, between[i], 11.5, SKY_D, bold=True,
                         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=f"사이 라벨 「{between[i]}」",
                         slide_no=s.no, max_lines=1)
        add_box(sl, cx - d / 2, cy - d / 2, d, d, SKY if it.strong else WHITE, line=(NAVY, 2.25), shape=MSO_SHAPE.OVAL)
        add_icon(sl, s.icons[i], cx, cy, d * 0.52, NAVY)
        item_block(sl, cx - cell / 2 + 0.1, cy + d / 2 + 0.15, cell - 0.2, th, it, s.no, f"요소{i + 1}",
                   title_pt=title_pt, desc_pt=desc_pt, align=PP_ALIGN.CENTER, bullet=False)


def render_graph(sl, s, page):
    """관계도(노드와 관계). 요소 `이름 | 종류 | x,y`가 원(노드)이고 x,y는 본문 영역 기준 0~100의 원 중심,
    `연결: A > B : 라벨`이 이름 있는 관계 화살표(`=>`는 점선)다. `아이콘:`을 주면 원 위쪽에 놓는다."""
    top, end = frame(sl, s, page)
    d = 1.9 if len(s.items) <= 5 else 1.6
    r = d / 2
    pos = {}
    for i, it in enumerate(s.items):
        px, py = (float(v) for v in it.tag.split(","))
        cx = MX + r + (CW - d) * px / 100
        cy = top + r + (end - top - d) * py / 100
        for other, (ox, oy) in pos.items():   # 화살표와 관계 라벨이 들어갈 틈이 없으면 그리지 않는다
            if ((cx - ox) ** 2 + (cy - oy) ** 2) ** 0.5 < d + 0.6:
                raise DeckError(f"SLIDE {s.no:02d} 관계도의 「{it.plain_title}」과 「{other}」이 너무 가깝다(좌표를 벌린다)")
        pos[it.plain_title] = (cx, cy)
        add_box(sl, cx - r, cy - r, d, d, SKY if it.strong else SKY_SOFT, line=(NAVY, 2) if it.strong else (SKY, 2),
                shape=MSO_SHAPE.OVAL)
        ty, th = cy - r * 0.62, d * 0.62
        if s.icons:
            add_icon(sl, s.icons[i], cx, cy - r * 0.48, d * 0.24, NAVY)
            ty, th = cy - r * 0.2, d * 0.5
        text = it.plain_title + ("\n" + "\n".join(it.lines) if it.lines else "")
        add_text(sl, cx - r * 0.86, ty, d * 0.86, th, text, 11, MUTED, align=PP_ALIGN.CENTER,
                 anchor=MSO_ANCHOR.MIDDLE, first_size=14, first_color=NAVY, name=f"노드 「{it.plain_title}」",
                 slide_no=s.no)
    for a, kind, b, label in links_of(s):
        (ax, ay), (bx, by) = pos[a], pos[b]
        dist = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        ux, uy = (bx - ax) / dist, (by - ay) / dist
        cmd = kind == "=>"
        color = SKY_D if cmd else NAVY
        x1, y1, x2, y2 = ax + ux * (r + 0.05), ay + uy * (r + 0.05), bx - ux * (r + 0.08), by - uy * (r + 0.08)
        add_arrow(sl, x1, y1, x2, y2, color, 2.25, dashed=cmd)
        if label:
            lw = text_w(label, 11.5) * (1.18 if label.isascii() else 1.0) + 0.3   # 굵은 영문 대문자 · 밑줄은 추정보다 넓다
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            lx, ly = (mx - lw / 2, my - 0.4) if abs(ux) >= abs(uy) else (mx + 0.1, my - 0.16)
            add_box(sl, lx, ly, lw, 0.32, WHITE, line=(color, 1), radius=0.5)
            add_text(sl, lx, ly, lw, 0.32, label, 11.5, color, bold=True, align=PP_ALIGN.CENTER,
                     anchor=MSO_ANCHOR.MIDDLE, name=f"관계 라벨 「{label}」", slide_no=s.no, max_lines=1)


def render_code(sl, s, page):
    """데이터 · 메시지 · 질의 예시. `코드:`의 ` / `는 줄바꿈. 요소는 오른쪽의 짚을 점."""
    top, end = frame(sl, s, page)
    n = len(s.items)
    cw = 7.4 if n else CW
    code = s.fields["코드"].replace(" / ", "\n").replace("\\/", "/")   # ` / `는 줄바꿈, `\/`는 글자 빗금
    pw0 = SLIDE_W - MX - (MX + cw + 0.35) - 0.2
    need_items = sum((line_count(it.plain_title, 17, pw0) * 17 + line_count("\n".join(it.lines) or " ", BODY_PT, pw0)
                      * BODY_PT) * LINE_SPACING / 72 + 0.45 for it in s.items)
    need_code = line_count(code, 13, (cw - 0.6) / 1.12) * (13 * LINE_SPACING + 2) / 72 + 0.6
    h = min(end - top, max(need_code, need_items, 2.4))   # 코드와 짚을 점 가운데 긴 쪽에 맞춘다
    top += (end - top - h) / 2
    add_box(sl, MX, top, cw, h, NAVY, radius=0.03)
    add_text(sl, MX + 0.2, top + 0.15, cw - 0.4, h - 0.3, code, 13, CODE_FG, face=MONO,
             name="코드", slide_no=s.no, space_after=2)
    if not n:
        return
    px = MX + cw + 0.35
    pw = SLIDE_W - MX - px
    rh = h / n
    y0 = top
    for i, it in enumerate(s.items):
        item_block(sl, px, y0 + i * rh, pw, rh, it, s.no, f"짚을 점{i + 1}", bullet=False,
                   anchor=MSO_ANCHOR.MIDDLE)


def render_quiz(sl, s, page):
    """문답. `문장:`이 물음, 요소가 보기(`보기 | 덧붙임`). 정답과 판단 기준은 뒤의 표 장에 모은다."""
    top, end = frame(sl, s, page)
    lines = s.fields["문장"].split(" / ")
    band_h = 0.35 + 0.42 * len(lines)
    add_box(sl, MX, top, CW, band_h, SKY_SOFT, radius=0.05)
    add_text(sl, MX + 0.25, top, CW - 0.5, band_h, "\n".join(lines), 19, NAVY, bold=True,
             anchor=MSO_ANCHOR.MIDDLE, name="물음(넘으면 ` / `로 끊는다)", slide_no=s.no, max_lines=len(lines))
    n = len(s.items)
    y0 = top + band_h + 0.2
    rh = min(1.0, (end - y0) / n)
    for i, it in enumerate(s.items):
        y = y0 + i * rh
        add_box(sl, MX, y + 0.05, CW, rh - 0.1, PANEL, radius=0.08)
        add_box(sl, MX + 0.2, y + rh / 2 - 0.2, 0.4, 0.4, NAVY, shape=MSO_SHAPE.OVAL)
        add_text(sl, MX + 0.2, y + rh / 2 - 0.2, 0.4, 0.4, str(i + 1), 13, WHITE, bold=True,
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text = it.plain_title + ("\n" + "\n".join(it.lines) if it.lines else "")
        add_text(sl, MX + 0.75, y, CW - 0.95, rh, text, 13, MUTED, anchor=MSO_ANCHOR.MIDDLE, first_size=15.5,
                 first_color=INK, name=f"보기{i + 1}", slide_no=s.no)


RENDER = {"표지": render_cover, "목차": render_agenda, "간지": render_divider, "흐름": render_flow,
          "카드": render_cards, "비교": render_compare, "표": render_table, "단계": render_steps,
          "강조": render_statement, "풀이": render_terms, "구조": render_structure, "파이프라인": render_pipeline, "관계도": render_graph,
          "코드": render_code,
          "문답": render_quiz}


class StdinDeck:
    """--check - : 표준 입력으로 받은 덱 MD. parse · validate가 쓰는 name · parent · read_text만 갖는다."""

    def __init__(self, text: str, parent: Path):
        self.text, self.parent, self.name = text, parent, "<표준 입력>"

    def read_text(self, encoding="utf-8"):
        return self.text


def build(md_path, out) -> list[Slide]:
    slides = parse(md_path)
    validate(slides, md_path)
    DECK["기관"] = slides[0].fields.get("기관", "")
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(SLIDE_W), Inches(SLIDE_H)
    blank = prs.slide_layouts[6]
    # 저장소의 추가 설명 레이아웃도 동일한 디자인 토큰·프레임을 사용한다.
    import importlib.util
    layout_path = Path(__file__).resolve().parents[4] / '제작용/온라인/tools/deck/설명레이아웃.py'
    custom = None
    layout_names = {}
    for block in re.split(r'(?=^## SLIDE )', md_path.read_text(encoding='utf8'), flags=re.M):
        number = re.match(r'## SLIDE (\d+)', block)
        name = re.search(r'^레이아웃: (.+)$', block, re.M)
        if number and name:
            layout_names[int(number[1])] = name[1].strip()
    if layout_names:
        spec = importlib.util.spec_from_file_location('lecture_layouts', layout_path)
        custom = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(custom)
    for page, s in enumerate(slides, 1):
        sl = prs.slides.add_slide(blank)
        if s.no in layout_names:
            import sys
            custom.render(sys.modules[__name__], sl, s, page, layout_names[s.no])
        elif s.kind == "그림":
            render_picture(sl, s, page, md_path.parent)
        elif s.kind == "삽화":
            render_illust(sl, s, page, md_path.parent)
        else:
            RENDER[s.kind](sl, s, page)
    if FIT.errs:
        raise DeckError("글자 넘침 추정(문구를 줄이거나 장을 나눈다):\n  " + "\n  ".join(FIT.errs))
    if isinstance(out, Path):
        out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    return slides


def audit(pptx_path: Path, slides: list[Slide]) -> list[str]:
    """저장된 파일을 다시 열어 통이미지·텍스트 상자 규칙을 잰다."""
    errs = []
    prs = Presentation(pptx_path)
    slide_area = prs.slide_width * prs.slide_height
    for s, sl in zip(slides, prs.slides):
        all_pics = [sh for sh in sl.shapes if sh.shape_type == 13]
        icons = [sh for sh in all_pics if sh.name.startswith("아이콘:")]
        pics = [sh for sh in all_pics if not sh.name.startswith(("아이콘:", "로고:", "삽화:"))]
        texts = [sh for sh in sl.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
        if s.kind != "그림" and pics:
            errs.append(f"SLIDE {s.no:02d} 그림 장이 아닌데 이미지 {len(pics)}개")
        if s.kind == "그림" and len(pics) != 1:
            errs.append(f"SLIDE {s.no:02d} 그림 장 이미지 {len(pics)}개(1개여야 함)")
        if len(icons) != len(s.icons):
            errs.append(f"SLIDE {s.no:02d} 아이콘 {len(icons)}개 (덱 MD {len(s.icons)}개)")
        for sh in icons:   # 아이콘이 장을 덮으면 통이미지와 같다
            if sh.width * sh.height > slide_area * 0.12:
                errs.append(f"SLIDE {s.no:02d} 아이콘 {sh.name}이 장 면적의 12%를 넘음")
        on_screen = "".join(sh.text_frame.text for sh in texts).replace("\n", "").replace(" ", "").replace("\u00a0", "")
        if plain(s.title).replace(" / ", "").replace(" ", "") not in on_screen:
            errs.append(f"SLIDE {s.no:02d} 제목이 텍스트 상자에 없음")
    return errs


@contextlib.contextmanager
def _render_lock():
    lock = Path(tempfile.gettempdir()) / "deck2pptx_render.lock"
    with open(lock, "w") as fh:
        try:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX)      # 다른 렌더가 끝날 때까지 기다린다
        except ImportError:                      # Windows: 잠금 없이 돈다
            pass
        yield


def render_png(pptx_path: Path, out_dir: Path) -> None:
    soffice = shutil.which("soffice") or r"C:\Program Files\LibreOffice\program\soffice.exe"
    if not Path(soffice).exists():
        raise DeckError("렌더용 LibreOffice(soffice)가 없음")
    out_dir.mkdir(parents=True, exist_ok=True)
    # LibreOffice는 같은 사용자 프로필로 둘이 동시에 돌면 CPU를 쓰지 않고 멈춘다(2026-10-11 실측).
    # 파일 잠금으로 한 번에 하나씩 돌리고, 그래도 멈추면 시간 제한으로 끊어 알린다.
    with _render_lock():
        try:
            subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx_path)],
                           check=True, capture_output=True, timeout=1200)
        except subprocess.TimeoutExpired:
            raise DeckError("PDF 변환이 20분 안에 끝나지 않음(LibreOffice가 멈춘 것으로 보인다. 남은 soffice 프로세스를 확인한다)")
    pdf = out_dir / (pptx_path.stem + ".pdf")
    if not pdf.exists():
        raise DeckError(f"PDF 변환 실패: {pdf}")
    # 덱 글꼴이 시스템에 없으면 LibreOffice가 실행마다 다른 글꼴로 바꿔 그린다(2026-10-10 macOS 실측: 손글씨체로 바뀜).
    # 바뀐 글꼴의 그림으로는 잘림·넘침을 판정할 수 없으므로 PDF에 박힌 글꼴 이름을 확인해 멈춘다.
    with pymupdf.open(pdf) as doc:
        used = {f[3] for page in doc for f in page.get_fonts()}
    other = sorted(n for n in used if not any(k in n.replace(" ", "").lower() for k in RENDER_FONT_KEYS))
    if other:
        raise DeckError(f"렌더가 「{FONT}」이 아닌 글꼴로 그려짐: {', '.join(other)} — 이 그림으로는 잘림·넘침을 판정할 수 없다. "
                        f"「{FONT}」(malgun.ttf · malgunbd.ttf)을 시스템에 설치한 뒤 다시 렌더한다")
    # Windows용 pdftoppm은 전체 경로가 약 240자를 넘으면 「Couldn't open file」로 실패한다(2026-10-08 실측).
    if len(str(pdf.resolve())) > 235:
        raise DeckError(f"렌더 폴더 경로가 너무 김({len(str(pdf.resolve()))}자). 짧은 폴더를 --render로 준다: {out_dir}")
    r = subprocess.run(["pdftoppm", "-r", "80", "-png", pdf.name, pptx_path.stem], cwd=out_dir,
                       capture_output=True, text=True)
    if r.returncode:
        raise DeckError(f"PNG 변환 실패({pdf}): {r.stderr.strip()}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("deck", help="덱 MD. --check와 함께 - 를 주면 표준 입력에서 읽는다")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--render", help="PNG를 낼 폴더(LibreOffice + pdftoppm)")
    ap.add_argument("--check", action="store_true", help="파일을 하나도 쓰지 않고 규칙 · 넘침 · 라벨 간격 · 저장본 검사만 한다")
    ap.add_argument("--base", help="--check - 일 때 그림 경로의 기준 폴더(덱 MD가 있는 폴더)")
    a = ap.parse_args()
    if a.check:
        global CHECK_ONLY
        CHECK_ONLY = True
        md = StdinDeck(sys.stdin.read(), Path(a.base or ".")) if a.deck == "-" else Path(a.deck)
        try:
            buf = io.BytesIO()
            slides = build(md, buf)
            buf.seek(0)
            errs = audit(buf, slides)
            if errs:
                raise DeckError("저장본 검사 실패:\n  " + "\n  ".join(errs))
        except DeckError as e:
            print(f"[실패] {e}", file=sys.stderr)
            return 1
        print(f"[검사 통과] {md.name} — {len(slides)}장, 파일은 쓰지 않았다")
        return 0
    if not a.out:
        ap.error("출력 PPTX 경로가 필요하다(검사만 하려면 --check)")
    md, out = Path(a.deck), Path(a.out)
    if out.exists() and out.resolve() == md.resolve():
        print("입력과 출력이 같음", file=sys.stderr)
        return 2
    try:
        slides = build(md, out)
        errs = audit(out, slides)
        if errs:
            raise DeckError("저장본 검사 실패:\n  " + "\n  ".join(errs))
        if a.render:
            render_png(out, Path(a.render))
    except DeckError as e:
        print(f"[실패] {e}", file=sys.stderr)
        return 1
    kinds: dict[str, int] = {}
    for s in slides:
        kinds[s.kind] = kinds.get(s.kind, 0) + 1
    print(f"[완료] {out} — {len(slides)}장 ({', '.join(f'{k} {v}' for k, v in kinds.items())})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
