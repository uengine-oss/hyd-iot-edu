"""실전반 온라인3 실습3 매뉴얼 대조(포털 관찰 — 도구 실습)의 폴더 · ZIP. 코딩 랩이 아니다.

문서 자료는 data_documents.py(문서 지식 묶음과 같은 한 벌)가 만들고, 이 실습에는 HM-8의 판들만 넣는다.
같은 회차의 코딩 랩(실습4 지식 추출 · 실습5 그래프 반영)은 build_document_labs.py가 만든다.
이 실습을 실라버스 R35(올리기 · 추출 · 대조 · 적재)와 맞추는 일과 START · AGENTS를 빼는 일(가이드.md P-2)은 가이드 산출물 몫으로 넘겼다 —
그 전까지 이 생성기를 돌리면 문서 자료만 새 판으로 바뀐다. package-index · catalog 등록은 하지 않는다 — ZIP만 묶는다.
"""
from build_labs import OUT, page, write, pack, RULES
from pathlib import Path
import csv
import hashlib
import shutil
import sys

import data_documents as DD

HERE = Path(__file__).resolve().parent
LABS = OUT / '실전반/실습/03회차/랩'
MANUAL = '03일차_실습3_매뉴얼검토'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reset(folder):
    """이전 생성물을 지우고 새로 만든다(이 랩 폴더 안만)."""
    if not folder.is_dir() or folder.parent != LABS:
        raise FileNotFoundError(f'대상 랩 폴더가 아닙니다: {folder}')
    for child in folder.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()


def rules_file(folder, extra):
    text = RULES + ''.join(f'- {line}\n' for line in extra)
    for name in ['AGENTS.md', 'CLAUDE.md', '.github/copilot-instructions.md']:
        write(folder / name, text)


def register_rows(folder):
    """자료/문서_목록.csv의 행 — 첫 줄(내보내기 머리)은 건너뛴다."""
    lines = [x for x in (folder / '자료/문서_목록.csv').read_text(encoding='utf-8').splitlines() if not x.startswith('#')]
    return list(csv.DictReader(lines))


SAVE = '''## 저장과 다음 실습

결과 폴더를 저장하고 다시 열어 확인하세요. 재부팅하면 학교 PC의 작업 폴더가 사라질 수 있으니 보관할 결과는 USB 또는 개인 클라우드에 복사하세요. 다음 실습도 독립 시작본을 제공하므로 개인 결과는 선택 입력입니다.
'''


def guide(folder, title, intro, sections):
    text = page(title, intro, sections)
    write(folder / 'guide.html', text)
    write(folder / '안내.html', text)


def start(folder, text):
    write(folder / 'START.md', text)
    write(folder / '준비_안내.md', text)


def doc_table(folder):
    rows = register_rows(folder)
    lines = ['| 문서 | 판 | 상태 | 파일 |', '|---|---|---|---|']
    lines += [f'| {r["문서 식별자"]} | {r["판"]} | {r["상태"]} | {("`" + r["파일"] + "`") if r["파일"] else "(파일 없음)"} |' for r in rows]
    return '\n'.join(lines)


# ---------------------------------------------------------------- 실습3 매뉴얼 대조(포털 관찰, 코드 과제 아님)
def build_manual():
    folder = LABS / MANUAL
    reset(folder)
    DD.write_bundle(folder, docs={'HM-8'}, sub='자료/원문', register_sub='자료')
    rules_file(folder, ['이번 실습은 포털 관찰과 기록이다. 포털에서 매뉴얼 등록·미리보기·에이전트 추출 요청·적재를 하지 않는다. 직접 추가 적재는 마지막 교대 실습에서 한다.',
                        '포털에서 보지 못한 표시는 보았다고 적지 않는다. 화면에서 찾지 못한 항목은 「포털에서 찾지 못함」으로 둔다.'])
    title = '포털 지식과 매뉴얼 원문 대조하기'
    intro = '포털에 등록된 HM-8 지식을 문서 목록의 현행 원문과 나란히 놓고, 팬 최대 운전과 쿨러 핀 세척을 하기 전에 확인할 항목을 원문 절에 연결합니다. 현장에 남아 있는 다른 판도 함께 대조합니다.'
    start(folder, f'''# {title}

{intro} 코드를 작성하지 않는 관찰 실습입니다.

자료는 교육용 가상 자료입니다(공개 현업 문제 유형을 따라 생성).

## 출발 상태

`자료/문서_목록.csv`에 등록된 HM-8의 판과 상태입니다.

{doc_table(folder)}

- 수업용 포털: 강사가 준비한 교육 환경입니다. 1회차에서 본 매뉴얼 적재 이후의 지식이 지식 지도에 있습니다. 상태가 다르면 강사에게 알리고 그 사실을 기록합니다.
- `결과/대조_기록.md`: 비어 있는 기록 틀입니다.

## 이번에 할 일

1. 문서 목록에서 포털 지식과 대조할 판을 정하고, 포털의 HM-8이 그 판인지 확인할 방법을 적습니다.
2. 그 판의 원문에서 **팬 최대 운전**과 **쿨러 핀 세척**을 찾습니다. 절차의 단계뿐 아니라 그 작업을 가리키거나 적용 범위를 정하는 다른 절도 찾습니다.
3. 포털 왼쪽 메뉴의 지식 묶음에서 **지식 지도**를 열고 조치 방법 칸에서 두 작업을 찾습니다. 화면에 보이는 단계·조건·근거 표시를 그대로 기록합니다. **지식 관리** 화면에서는 HM-8이 등록되어 있는지만 확인합니다.
4. 두 작업마다 적용 조건·금지 사항·완료 기준·승인을 원문 절과 원문 문장에 연결하고, 포털에서 본 표현과 일치하는지 적습니다.
5. 다른 판에서 같은 작업을 찾아, 현장에서 그 판을 보고 일하면 작업 전 확인이 어떻게 달라지는지 적습니다.
6. 문서에 적힌 **기준값**과 작업 직전에 설비·기록에서 읽어야 하는 **현재 값**을 다른 칸에 적습니다.
7. 원문의 한 문장이 어느 작업에 적용되는지 원문만으로 정해지지 않으면, 어떻게 적용할지 정하고 근거를 적습니다. 정할 수 없으면 남은 질문으로 둡니다.

## 확인할 사례의 종류

- 작업 조건이 그 절차 밖의 다른 절에 적혀 있는 경우
- 표의 머리글이 값의 뜻을 정하는 경우
- 경계를 정하는 표현(이상·초과·미만·이내)
- 판이 다르면 같은 작업의 ID·절 번호·기준·승인이 달라지는 경우
- 문서가 정하지 않은 것(현재 상태, 적용 설비 범위)

## 완료 판정 원칙

두 작업 모두 각 항목이 원문 절과 문장으로 이어지고, 포털 표시와의 대조 결과가 일치 / 표현 다름 / 포털에서 찾지 못함으로 구별되어 있으면 됩니다. 판 차이는 어느 판의 어느 문장인지와 함께 적습니다. 기준값과 현재 값이 섞이지 않아야 합니다. 포털에서 보지 못한 것을 추정으로 채우지 않습니다.

## 저장할 결과

`결과/대조_기록.md`

{SAVE}
다음 실습에서는 이렇게 대조한 지식을 원문에서 직접 추출하는 기능을 만듭니다.
''')
    write(folder / '입력/README.md', '이 실습은 앞 단계 결과가 필요 없습니다. 대조 대상은 자료/원문의 HM-8과 수업용 포털의 등록 지식입니다.\n')
    write(folder / '결과/README.md', '대조_기록.md를 여기에 작성합니다.\n')
    table = '| 구분 | 원문 절 | 원문 문장(그대로) | 포털에서 본 표현과 위치 | 대조 결과 | 작업 전 확인할 현재 값과 읽을 곳 |\n|---|---|---|---|---|---|\n| 적용 조건 | | | | | |\n| 금지·제한 | | | | | |\n| 완료 기준 | | | | | |\n| 승인 | | | | | |\n'
    write(folder / '결과/대조_기록.md', f'''# 매뉴얼 원문과 포털 지식 대조 기록

- 확인 일시:
- 포털에서 연 화면:
- 대조한 원문 판과 SHA-256 앞 12자리:
- 포털 지식이 그 판인지 확인한 방법:

대조 결과는 일치 / 표현 다름(무엇이) / 포털에서 찾지 못함 중 하나로 적습니다. 한 구분에 항목이 여럿이면 행을 늘립니다.

## 1. 팬 최대 운전

{table}
## 2. 쿨러 핀 세척

{table}
## 3. 다른 판과의 차이

| 작업 | 다른 판의 ID·절 | 다른 판의 문장(그대로) | 대조한 판의 문장(그대로) | 작업 전 확인이 어떻게 달라지는가 |
|---|---|---|---|---|

## 4. 기준값과 현재 값

| 항목 | 문서의 기준값과 절 | 현재 값을 읽을 곳 | 관찰한 현재 값과 시각(또는 미확인) |
|---|---|---|---|

## 5. 적용 범위를 정한 것

| 원문 문장(그대로) | 정한 적용 범위 | 근거 | 다르게 정하면 바뀌는 것 |
|---|---|---|---|

## 6. 남은 질문

''')
    # 가이드 그림 = 강사 촬영 영상의 실제 포털 화면(screens/practical-03-manual, 2026-10-28 녹화 p33-2·3에서 장면 끝 프레임, vs-01은 VS Code 구간 p33-1). 폴더를 비우는 생성기라 원본에서 복사한다.
    screens = HERE / 'screens/practical-03-manual'
    (folder / 'images').mkdir(exist_ok=True)
    for f in sorted(screens.glob('*.jpg')):
        shutil.copy2(f, folder / 'images' / f.name)
    def shot(name, caption):
        if not (folder / 'images' / f'{name}.jpg').is_file():
            raise FileNotFoundError(f'가이드 그림 없음: {screens / (name + ".jpg")}')
        return f'<figure><a href="images/{name}.jpg" target="_blank"><img src="images/{name}.jpg" alt="{caption}"></a><figcaption>{caption} · 누르면 크게 보기</figcaption></figure>'
    guide(folder, title, intro, [
        ('시작하기', '<p>압축을 푼 폴더를 VS Code에서 열고 <a href="START.md">START.md</a>를 읽으세요. 이번 실습은 포털 관찰과 기록이며 코드를 만들지 않습니다.</p><pre>자료/문서_목록.csv   HM-8의 판·상태·해시\n자료/원문/          문서 목록에 파일이 있는 판\n결과/대조_기록.md   작성할 기록</pre><p>두 원문을 나란히 보려면 탐색기에서 두 파일을 함께 선택하고 마우스 오른쪽 버튼 → <b>선택한 항목 비교</b>를 누릅니다.</p>'),
        ('요구 정하기', '<p>문서 목록을 보고 어느 판을 포털 지식과 대조할지 먼저 정하고 그 이유를 적으세요. 두 작업(팬 최대 운전, 쿨러 핀 세척)에 대해 무엇을 확인해야 작업을 시작할 수 있는지 원문에서 찾습니다. 절차 단계만 보지 말고 그 작업을 가리키는 다른 절도 찾습니다.</p>'+shot('vs-01-doclist','탐색기 자료 → 문서_목록.csv를 연 화면(판 · 상태 · SHA-256)')),
        ('포털에서 대조하기', '<p>포털 왼쪽 메뉴의 지식 묶음에서 <b>지식 지도</b>를 열고 검색 칸에 작업 이름(예: 팬 최대 운전)을 넣어 조치 방법 칸의 작업을 누르세요. 상세 칸은 지도 <b>아래</b>에 나옵니다. 화면에 보이는 단계·조건·근거 표시를 기록하고 원문 문장과 나란히 적습니다.</p>'+shot('mr-01-citation','조치 방법 상세의 citation과 source_id — 끝의 해시 앞자리를 문서 목록의 판 해시와 비교')+'<p>나가는 관계에서 승인 역할과 절차 단계를, 들어오는 관계에서 「적용 대상」으로 이어진 규칙을 읽습니다.</p>'+shot('mr-02-rules','들어오는 관계의 적용 대상 규칙들')+shot('mr-03-cool14','다른 작업의 상세: 승인 역할과 절차 단계')+'<p><b>지식 관리</b>에서는 HM-8 등록 여부만 확인합니다.</p>'+shot('mr-04-registered','등록된 매뉴얼 목록의 HM-8 현재 판본')+'<p>작업 직전에 읽을 현재 값은 설비 묶음의 <b>결함 시뮬레이션</b> 설비 카드에서 읽고 시각과 함께 적습니다. 화면에 없는 값은 미확인으로 둡니다.</p>'+shot('mr-05-current','설비 카드의 현재 유온·냉각 효율·팬 속도·운전 모드')+'<p class="check">매뉴얼 등록·미리보기·에이전트 추출 요청·적재, 운전 모드·결함 버튼은 누르지 않습니다. 직접 추가 적재는 마지막 교대 실습에서 제공 보충 매뉴얼로 합니다.</p>'),
        ('결과 확인하기', '<ul><li>각 항목이 원문 절과 원문 문장으로 이어지나요?</li><li>절차 밖의 절에 있는 조건도 찾았나요?</li><li>경계 표현을 원문 그대로 옮겼나요?</li><li>다른 판과의 차이를 어느 판의 어느 문장인지와 함께 적었나요?</li><li>원문만으로 적용 범위가 정해지지 않은 문장을 어떻게 처리했는지, 다르게 정하면 무엇이 바뀌는지 적었나요?</li><li>문서의 기준값과 작업 직전에 읽을 현재 값을 다른 칸에 적었나요?</li></ul><p class="check">포털에서 찾지 못한 항목은 찾지 못했다고 적습니다. 추정으로 채운 대조는 확인한 대조가 아닙니다.</p>'),
        ('저장하기', '<p>결과/대조_기록.md를 저장하고 다시 열어 확인하세요. 보관할 결과는 USB 또는 개인 클라우드에 복사합니다.</p><p>다음 실습은 이 대조를 원문에서 직접 추출하는 기능으로 이어집니다. 다음 실습은 이 기록 없이도 시작할 수 있습니다.</p>')])
    return folder, title


def main():
    folder, title = build_manual()
    archive = pack(folder)
    print(f'{folder.name}: {archive.relative_to(OUT).as_posix()} {sha(archive)[:12]} — package-index · catalog 등록은 하지 않았습니다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
