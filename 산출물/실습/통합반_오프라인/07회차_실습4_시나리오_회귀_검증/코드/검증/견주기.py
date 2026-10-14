"""견주기. 결과 파일 두 판(변경 전과 변경 후)을 항목마다 칸마다 대어 보고 달라진 곳을 적는다.
항목은 요청 처리 결과에서는 요청 한 건, 점검 계획에서는 사례 한 건이다.
파일을 읽기만 하고 아무것도 고치지 않는다.

    python 검증/견주기.py                       검증/변경_전/요청_처리.json ↔ 결과/요청_처리.json
    python 검증/견주기.py <변경 전> <변경 후>     두 파일을 직접 고른다
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

_폴더 = Path(__file__).resolve().parent.parent
_기본_전 = _폴더 / "검증" / "변경_전" / "요청_처리.json"
_기본_후 = _폴더 / "결과" / "요청_처리.json"


def _읽기(경로):
    with open(경로, encoding="utf-8") as f:
        return json.load(f)


def _글(값, 길이=48):
    글 = json.dumps(값, ensure_ascii=False)
    return 글 if len(글) <= 길이 else 글[:길이] + "…"


def _다른_곳(전, 후, 자리=""):
    """두 값이 처음 갈리는 자리들을 (자리, 전, 후)로 돌려준다."""
    if type(전) is not type(후):
        return [(자리, 전, 후)]
    if isinstance(전, dict):
        곳 = []
        for 칸 in list(전) + [k for k in 후 if k not in 전]:
            아래 = f"{자리}.{칸}" if 자리 else 칸
            if 칸 not in 후:
                곳.append((아래, 전[칸], "(없어짐)"))
            elif 칸 not in 전:
                곳.append((아래, "(없었음)", 후[칸]))
            else:
                곳 += _다른_곳(전[칸], 후[칸], 아래)
        return 곳
    if isinstance(전, list):
        if len(전) != len(후):
            return [(자리, f"항목 {len(전)}개", f"항목 {len(후)}개")]
        곳 = []
        for i, (a, b) in enumerate(zip(전, 후)):
            곳 += _다른_곳(a, b, f"{자리}[{i}]")
        return 곳
    return [] if 전 == 후 else [(자리, 전, 후)]


def _이름(경로):
    """이 폴더 안의 파일이면 폴더에서 본 경로로 적는다."""
    try:
        return Path(경로).resolve().relative_to(_폴더).as_posix()
    except ValueError:
        return str(경로)


def 견주기(전_경로, 후_경로):
    전, 후 = _읽기(전_경로), _읽기(후_경로)
    줄 = [f"변경 전: {_이름(전_경로)}", f"변경 후: {_이름(후_경로)}", ""]

    전_번호 = [c.get("번호") for c in 전]
    후_번호 = [c.get("번호") for c in 후]
    줄.append(f"항목 수: {len(전)}건 → {len(후)}건")
    if 전_번호 == 후_번호:
        줄.append("항목의 순서: 같다")
    else:
        줄.append("항목의 순서: 다르다")
        줄.append(f"  변경 전: {' '.join(map(str, 전_번호))}")
        줄.append(f"  변경 후: {' '.join(map(str, 후_번호))}")
    줄.append("")

    후_요청 = {c.get("번호"): c for c in 후}
    달라진_요청 = 0
    더해진_칸, 없어진_칸 = [], []
    for 한_건 in 전:
        번호 = 한_건.get("번호")
        뒤 = 후_요청.get(번호)
        if 뒤 is None:
            줄.append(f"{번호}  변경 후에 없다")
            달라진_요청 += 1
            continue
        더해짐 = [k for k in 뒤 if k not in 한_건]
        없어짐 = [k for k in 한_건 if k not in 뒤]
        for k in 더해짐:
            if k not in 더해진_칸:
                더해진_칸.append(k)
        for k in 없어짐:
            if k not in 없어진_칸:
                없어진_칸.append(k)
        다름 = []
        for 칸 in 한_건:
            if 칸 in 뒤:
                다름 += _다른_곳(한_건[칸], 뒤[칸], 칸)
        if 다름 or 없어짐:
            달라진_요청 += 1
            줄.append(f"{번호}  기존 칸이 달라졌다")
            for 칸 in 없어짐:
                줄.append(f"      - 없어진 칸: {칸}")
            for 자리, a, b in 다름[:6]:
                줄.append(f"      - {자리}: {_글(a)} → {_글(b)}")
            if len(다름) > 6:
                줄.append(f"      - … 그 밖에 {len(다름) - 6}곳")
        else:
            줄.append(f"{번호}  기존 칸은 그대로다")
        for 칸 in 더해짐:
            줄.append(f"      + 더해진 칸 {칸}: {_글(뒤[칸])}")
    for 번호 in 후_번호:
        if 번호 not in 전_번호:
            줄.append(f"{번호}  변경 전에 없던 항목이다")

    줄 += [
        "",
        f"요약: 기존 칸이 달라진 항목 {달라진_요청}건 · "
        f"없어진 칸 {len(없어진_칸)}개{' (' + ', '.join(없어진_칸) + ')' if 없어진_칸 else ''} · "
        f"더해진 칸 {len(더해진_칸)}개{' (' + ', '.join(더해진_칸) + ')' if 더해진_칸 else ''} · "
        f"항목의 순서 {'같다' if 전_번호 == 후_번호 else '다르다'}",
    ]
    return "\n".join(줄)


def main(인자):
    if len(인자) not in (0, 2):
        raise SystemExit("쓰는 법: python 검증/견주기.py [<변경 전 json> <변경 후 json>]")
    전_경로, 후_경로 = (Path(인자[0]), Path(인자[1])) if 인자 else (_기본_전, _기본_후)
    for 경로 in (전_경로, 후_경로):
        if not 경로.is_file():
            raise SystemExit(f"파일이 없다: {_이름(경로)}")
    print(견주기(전_경로, 후_경로))


if __name__ == "__main__":
    main(sys.argv[1:])
