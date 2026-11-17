#!/usr/bin/env bash
# 포털이 쓰는 바깥 부품(화면 키트 · 글꼴 · 아이콘 · 차트 · 흐름 그림 · 그래프 · 작은 도구)을 내려받아
# it/portal/www/vendor/ 에 「쓸 파일만」 넣는다. 포털은 실행 때 빌드도 CDN 도 쓰지 않으므로 이 폴더가 커밋된다.
#
# 쓰는 법(저장소 루트에서, Git Bash):  bash workspace/개발/scripts/portal_vendor.sh
#   - node 와 npm 이 있어야 한다(내려받기 · 아이콘 묶음 만들기 · bpmn-auto-layout 한 파일로 묶기).
#   - npm 의 설치 스크립트는 돌지 않는다(`npm pack` 으로 묶음만 받아 푼다).
#   - 버전을 올릴 때는 아래 표의 숫자와 RECEIVED 날짜만 바꾸고 다시 돌린다. vendor/ 는 통째로 다시 만들어진다(README.md 포함).
# 부품별 버전 · 라이선스 · 쓰임은 만들어진 it/portal/www/vendor/README.md 에 있다. 고르는 까닭은 디자인 기준 문서에 있다.
set -euo pipefail

RECEIVED="2026-11-14"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$ROOT/it/portal/www/vendor"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 아이콘: Lucide 에서 이 이름들만 한 파일(vendor/lucide/icons.svg)로 묶는다. 화면이 새 아이콘을 쓰면 여기에 이름을 더하고 다시 돌린다.
ICONS="house inbox book-open workflow bot factory flask-conical settings
 network list-checks file-up database sparkles plug message-circle-question
 zap droplets activity circuit-board receipt-text scale calculator clipboard-check git-compare
 layout-grid gauge wrench
 search bell panel-left chevron-right chevron-down chevron-left chevron-up arrow-right arrow-left arrow-up-right arrow-up arrow-down external-link
 check x plus minus circle circle-check circle-x circle-alert circle-dashed circle-dot loader-circle triangle-alert info clock timer
 play pause square refresh-cw rotate-ccw maximize-2 minimize-2 scan locate-fixed zoom-in zoom-out
 user user-check cpu server cog terminal code braces file-text file-json folder upload download copy trash-2 pencil eye eye-off
 ellipsis ellipsis-vertical filter sliders-horizontal link unlink route waypoints share-2 git-branch
 thermometer fan wind power shield-check shield-alert lock radio signal wifi wifi-off cloud hard-drive layers box boxes
 message-square send corner-down-right history calendar tag hash command keyboard
 chart-line chart-column trending-up trending-down target"

pack() {   # pack <npm 이름@버전> → 풀린 package 폴더 경로를 낸다
  local spec="$1" dir
  dir="$TMP/$(echo "$spec" | tr '/@' '__')"
  mkdir -p "$dir"
  (cd "$dir" && npm pack "$spec" --silent --ignore-scripts >/dev/null && tar -xzf ./*.tgz)
  echo "$dir/package"
}
version_file() {   # version_file <폴더> <패키지> <버전> <라이선스> <받은 곳> [덧붙일 말]
  printf '패키지: %s\n버전: %s\n라이선스: %s\n받은 곳: %s\n받은 날: %s\n%s' "$2" "$3" "$4" "$5" "$RECEIVED" "${6:+$6
}" > "$1/VERSION"
}

rm -rf "$OUT"
mkdir -p "$OUT"

# ── 화면 키트: Basecoat (shadcn/ui 의 부품을 React 없이 HTML 클래스로 쓰는 판) ──
P="$(pack basecoat-css@1.1.0)"
mkdir -p "$OUT/basecoat"
cp "$P/dist/basecoat-nova.cdn.min.css" "$OUT/basecoat/basecoat.min.css"       # nova 모양(촘촘한 판) 한 벌만
cp "$P/dist/js/all.min.js" "$OUT/basecoat/basecoat.min.js"                    # 드롭다운 · 선택 · 탭 · 토스트 · 명령 팔레트 · 메뉴 줄
cp "$P/LICENSE.md" "$OUT/basecoat/LICENSE.md"
version_file "$OUT/basecoat" basecoat-css 1.1.0 MIT "https://registry.npmjs.org/basecoat-css" "넣은 파일: dist/basecoat-nova.cdn.min.css(→ basecoat.min.css), dist/js/all.min.js(→ basecoat.min.js)"

# ── 한글 글꼴: Pretendard 가변 글꼴 한 파일 ──
P="$(pack pretendard@1.3.9)"
mkdir -p "$OUT/pretendard"
cp "$P/dist/web/variable/woff2/PretendardVariable.woff2" "$OUT/pretendard/"
if [ -f "$P/LICENSE" ]; then cp "$P/LICENSE" "$OUT/pretendard/LICENSE"; else curl -fsSL "https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/LICENSE" -o "$OUT/pretendard/LICENSE"; fi
version_file "$OUT/pretendard" pretendard 1.3.9 "SIL OFL 1.1" "https://registry.npmjs.org/pretendard" "넣은 파일: dist/web/variable/woff2/PretendardVariable.woff2 (굵기 45~920 한 파일)"

# ── 숫자 · 코드 글꼴: Geist Mono 가변 글꼴(라틴) ──
P="$(pack @fontsource-variable/geist-mono@5.3.0)"
mkdir -p "$OUT/geist-mono"
cp "$P/files/geist-mono-latin-wght-normal.woff2" "$OUT/geist-mono/GeistMonoVariable.woff2"
cp "$P/LICENSE" "$OUT/geist-mono/LICENSE"
version_file "$OUT/geist-mono" "@fontsource-variable/geist-mono" 5.3.0 "SIL OFL 1.1" "https://registry.npmjs.org/@fontsource-variable/geist-mono" "넣은 파일: files/geist-mono-latin-wght-normal.woff2(→ GeistMonoVariable.woff2)"

# ── 아이콘: Lucide — 위 ICONS 의 것만 한 파일로 ──
P="$(pack lucide-static@1.72.0)"
mkdir -p "$OUT/lucide"
ICONS="$ICONS" node -e '
const fs = require("fs"), path = require("path");
const [src, out] = process.argv.slice(1);
const names = [...new Set(process.env.ICONS.split(/\s+/).filter(Boolean))].sort();
const missing = [];
const symbols = names.map((n) => {
  const f = path.join(src, "icons", n + ".svg");
  if (!fs.existsSync(f)) { missing.push(n); return ""; }
  const inner = fs.readFileSync(f, "utf8").replace(/<!--[\s\S]*?-->/g, "").replace(/^[\s\S]*?<svg[^>]*>/, "").replace(/<\/svg>\s*$/, "").replace(/\s*\n\s*/g, "");
  return `<symbol id="${n}" viewBox="0 0 24 24">${inner}</symbol>`;
});
if (missing.length) { console.error("Lucide 에 없는 아이콘 이름: " + missing.join(", ")); process.exit(1); }
fs.writeFileSync(path.join(out, "icons.svg"), `<svg xmlns="http://www.w3.org/2000/svg">${symbols.join("")}</svg>\n`);
fs.writeFileSync(path.join(out, "icons.txt"), names.join("\n") + "\n");
console.error("아이콘 " + names.length + "개를 묶었습니다");
' "$P" "$OUT/lucide"
cp "$P/LICENSE" "$OUT/lucide/LICENSE"
version_file "$OUT/lucide" lucide-static 1.72.0 ISC "https://registry.npmjs.org/lucide-static" "넣은 파일: icons/<이름>.svg 가운데 icons.txt 의 것만 icons.svg 한 파일로 묶음(<svg><use href=\"vendor/lucide/icons.svg#이름\">)"

# ── 차트: uPlot ──
P="$(pack uplot@1.6.32)"
mkdir -p "$OUT/uplot"
cp "$P/dist/uPlot.iife.min.js" "$P/dist/uPlot.min.css" "$P/LICENSE" "$OUT/uplot/"
version_file "$OUT/uplot" uplot 1.6.32 MIT "https://registry.npmjs.org/uplot" "넣은 파일: dist/uPlot.iife.min.js, dist/uPlot.min.css"

# ── 흐름 그림: bpmn-js 의 보기 전용 완성본(끌기 · 확대 포함) — 포털은 그리지 않고 보여 주기만 한다 ──
P="$(pack bpmn-js@18.31.1)"
mkdir -p "$OUT/bpmn-js/bpmn-font/css" "$OUT/bpmn-js/bpmn-font/font"
cp "$P/dist/bpmn-navigated-viewer.production.min.js" "$OUT/bpmn-js/"
cp "$P/dist/assets/bpmn-js.css" "$P/dist/assets/diagram-js.css" "$OUT/bpmn-js/"
cp "$P/dist/assets/bpmn-font/css/bpmn.css" "$OUT/bpmn-js/bpmn-font/css/"
cp "$P/dist/assets/bpmn-font/font/bpmn.woff2" "$P/dist/assets/bpmn-font/font/bpmn.woff" "$OUT/bpmn-js/bpmn-font/font/"
cp "$P/LICENSE" "$OUT/bpmn-js/LICENSE"
version_file "$OUT/bpmn-js" bpmn-js 18.31.1 "bpmn.io 라이선스(MIT 본문 + 그림 오른쪽 아래의 bpmn.io 표시를 지우거나 가리지 않는다는 조건)" "https://registry.npmjs.org/bpmn-js" "넣은 파일: dist/bpmn-navigated-viewer.production.min.js, dist/assets/{bpmn-js.css,diagram-js.css,bpmn-font/css/bpmn.css,bpmn-font/font/bpmn.woff2,bpmn.woff}"

# ── 흐름 그림 자동 배치: bpmn-auto-layout 을 브라우저용 한 파일로 묶는다(배치 정보가 없는 BPMN 을 받았을 때만 쓴다) ──
P="$(pack bpmn-auto-layout@1.3.0)"
mkdir -p "$OUT/bpmn-auto-layout" "$TMP/bal"
(cd "$TMP/bal" && npm init -y >/dev/null && npm install --silent --ignore-scripts --no-audit --no-fund bpmn-auto-layout@1.3.0 >/dev/null \
  && printf 'import { layoutProcess } from "bpmn-auto-layout";\nglobalThis.BpmnAutoLayout = { layoutProcess };\n' > entry.js \
  && npx --yes esbuild@0.28.2 entry.js --bundle --minify --format=iife --platform=browser --legal-comments=none --outfile="$OUT/bpmn-auto-layout/bpmn-auto-layout.min.js" >/dev/null 2>&1)
{ echo "bpmn-auto-layout 1.3.0 — MIT (package.json 의 license 값. 이 패키지는 LICENSE 파일을 싣지 않는다)"; echo "저작권: bpmn.io contributors · https://github.com/bpmn-io/bpmn-auto-layout"; echo
  echo "이 묶음에 함께 들어간 것과 그 라이선스:"; (cd "$TMP/bal" && for d in node_modules/*/; do if [ -f "$d/package.json" ]; then node -e 'const p=require(process.argv[1]);console.log("- "+p.name+" "+p.version+" — "+p.license)' "$(pwd)/$d/package.json"; fi; done); } > "$OUT/bpmn-auto-layout/LICENSE"
version_file "$OUT/bpmn-auto-layout" bpmn-auto-layout 1.3.0 MIT "https://registry.npmjs.org/bpmn-auto-layout" "만든 법: esbuild 0.28.2 로 dist/index.js 와 그 의존을 한 파일(IIFE, 전역 BpmnAutoLayout.layoutProcess)로 묶음"

# ── 지식 지도: Cytoscape.js + 배치 확장 fcose ──
P="$(pack cytoscape@3.35.0)"
mkdir -p "$OUT/cytoscape"
cp "$P/dist/cytoscape.min.js" "$P/LICENSE" "$OUT/cytoscape/"
version_file "$OUT/cytoscape" cytoscape 3.35.0 MIT "https://registry.npmjs.org/cytoscape" "넣은 파일: dist/cytoscape.min.js"
mkdir -p "$OUT/cytoscape-fcose"
P="$(pack layout-base@2.0.1)";    cp "$P/layout-base.js" "$OUT/cytoscape-fcose/";    cp "$P/LICENSE" "$OUT/cytoscape-fcose/LICENSE.layout-base"
P="$(pack cose-base@2.2.0)";      cp "$P/cose-base.js" "$OUT/cytoscape-fcose/";      cp "$P/LICENSE" "$OUT/cytoscape-fcose/LICENSE.cose-base"
P="$(pack cytoscape-fcose@2.2.0)"; cp "$P/cytoscape-fcose.js" "$OUT/cytoscape-fcose/"; cp "$P/LICENSE" "$OUT/cytoscape-fcose/LICENSE"
version_file "$OUT/cytoscape-fcose" "cytoscape-fcose (+ cose-base, layout-base)" "2.2.0 (cose-base 2.2.0, layout-base 2.0.1)" MIT "https://registry.npmjs.org/cytoscape-fcose" "넣은 파일: layout-base.js → cose-base.js → cytoscape-fcose.js (이 차례로 싣는다)"

# ── 마크다운 보기: marked + 내용 소독 DOMPurify ──
P="$(pack marked@18.2.0)"
mkdir -p "$OUT/marked"
cp "$P/lib/marked.umd.js" "$OUT/marked/"; cp "$P/LICENSE" "$OUT/marked/LICENSE" 2>/dev/null || cp "$P/LICENSE.md" "$OUT/marked/LICENSE"
version_file "$OUT/marked" marked 18.2.0 MIT "https://registry.npmjs.org/marked" "넣은 파일: lib/marked.umd.js"
P="$(pack dompurify@3.4.17)"
mkdir -p "$OUT/dompurify"
cp "$P/dist/purify.min.js" "$P/LICENSE" "$OUT/dompurify/"
version_file "$OUT/dompurify" dompurify 3.4.17 "Apache-2.0 (MPL-2.0 와 둘 가운데 고름)" "https://registry.npmjs.org/dompurify" "넣은 파일: dist/purify.min.js"

# ── 코드 · JSON 구문 강조: Prism (핵심 + 쓰는 말만 한 파일로 이어 붙임) ──
P="$(pack prismjs@1.30.0)"
mkdir -p "$OUT/prism"
: > "$OUT/prism/prism.min.js"
for c in core markup clike javascript json yaml python bash sql cypher; do cat "$P/components/prism-$c.min.js" >> "$OUT/prism/prism.min.js"; printf '\n' >> "$OUT/prism/prism.min.js"; done
cp "$P/LICENSE" "$OUT/prism/"
version_file "$OUT/prism" prismjs 1.30.0 MIT "https://registry.npmjs.org/prismjs" "만든 법: components/prism-{core,markup,clike,javascript,json,yaml,python,bash,sql,cypher}.min.js 를 이 차례로 이어 붙임. 색은 포털 CSS 가 정한다(Prism 테마 파일은 넣지 않는다)"

# ── 목록(README.md) ──
size() { du -sk "$1" | cut -f1; }
{
  echo "# vendor — 포털이 싣는 바깥 부품"
  echo
  echo "이 폴더는 \`workspace/개발/scripts/portal_vendor.sh\` 가 통째로 만든다(손으로 고치지 않는다). 포털은 CDN 을 부르지 않고 이 파일들만 싣는다."
  echo "받은 날 $RECEIVED. 부품마다 그 폴더에 라이선스 원문과 \`VERSION\` 이 있다."
  echo
  echo "| 폴더 | 무엇 | 버전 | 라이선스 | 크기(KB) | 어디에 쓰나 |"
  echo "|---|---|---|---|---|---|"
  echo "| basecoat | 화면 키트 Basecoat(shadcn/ui 부품의 HTML 판, nova 모양) | 1.1.0 | MIT | $(size "$OUT/basecoat") | 단추 · 카드 · 뱃지 · 표 · 폼 · 탭 · 대화상자 · 드롭다운 · 토스트 · 메뉴 줄 · 명령 팔레트 · 빈 상태 · 스켈레톤 |"
  echo "| pretendard | 한글 글꼴 Pretendard(가변) | 1.3.9 | SIL OFL 1.1 | $(size "$OUT/pretendard") | 포털의 모든 글 |"
  echo "| geist-mono | 고정폭 글꼴 Geist Mono(가변, 라틴) | 5.3.0 | SIL OFL 1.1 | $(size "$OUT/geist-mono") | 숫자 · 코드 · 식별자 |"
  echo "| lucide | 아이콘 Lucide($(wc -l < "$OUT/lucide/icons.txt" | tr -d ' ')개만 묶음) | 1.72.0 | ISC | $(size "$OUT/lucide") | 메뉴 · 단추 · 상태 아이콘 |"
  echo "| uplot | 차트 uPlot | 1.6.32 | MIT | $(size "$OUT/uplot") | 설비 추이 · 성과 지표 |"
  echo "| bpmn-js | 흐름 그림 보기(NavigatedViewer) | 18.31.1 | bpmn.io(MIT + 표시 유지) | $(size "$OUT/bpmn-js") | 처리 건의 진행 길 · 흐름 화면. 그리기는 bpmn.io 에서 한다 |"
  echo "| bpmn-auto-layout | 흐름 그림 자동 배치(한 파일로 묶음) | 1.3.0 | MIT | $(size "$OUT/bpmn-auto-layout") | 배치 정보가 없는 BPMN 을 가져왔을 때 |"
  echo "| cytoscape | 그래프 그림 Cytoscape.js | 3.35.0 | MIT | $(size "$OUT/cytoscape") | 지식 지도 |"
  echo "| cytoscape-fcose | 그래프 배치 fcose(+ cose-base, layout-base) | 2.2.0 | MIT | $(size "$OUT/cytoscape-fcose") | 지식 지도의 배치 |"
  echo "| marked | 마크다운 → HTML | 18.2.0 | MIT | $(size "$OUT/marked") | 스킬 문서 · 문서 원문 · AI 답 |"
  echo "| dompurify | HTML 소독 | 3.4.17 | Apache-2.0 | $(size "$OUT/dompurify") | marked 가 낸 HTML 을 화면에 넣기 전 |"
  echo "| prism | 구문 강조 Prism(핵심 + json · yaml · python · bash · sql · cypher · xml) | 1.30.0 | MIT | $(size "$OUT/prism") | 도구 호출의 입력 · 출력, 흐름 XML, 질의 |"
  echo
  echo "전체 크기: $(size "$OUT") KB"
} > "$OUT/README.md"
echo "vendor 를 만들었습니다: $OUT ($(size "$OUT") KB)"
