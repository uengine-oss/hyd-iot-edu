"""대본 본문의 문장 끝을 센다. 사용: python3 endcheck.py <본문.md>
문장 = 마침표 · 물음표로 끝나는 덩이(표시 ▸ ‖ 는 지우고 이어 읽음). 끝 글자로 요 · 다 · 죠 · 기타를 가른다.
걸리는 것: 이어진 두 문장이 둘 다 「요」로 끝남, 「다」가 셋 넘게 이어짐. 단계(### 머리)가 바뀌면 새로 센다."""
import re, sys
bad = 0
for block in re.split(r'^### ', open(sys.argv[1], encoding='utf-8').read(), flags=re.M)[1:]:
    title, body = block.split('\n', 1)
    text = re.sub(r'‖\(따라 하기 \d+초\)|‖|▸', ' ', body)
    sents = [s.strip() for s in re.findall(r'[^.?!]+[.?!]', text) if s.strip()]
    kinds = []
    for s in sents:
        w = s.rstrip('.?!')
        k = '요' if w.endswith('요') else '다' if w.endswith('다') else '죠' if w.endswith('죠') else '기타'
        kinds.append(k)
    run = 0
    for i, k in enumerate(kinds):
        if i and k == '요' and kinds[i - 1] == '요':
            bad += 1; print(f'[요요] {title.split()[0]} {sents[i-1][-18:]} / {sents[i][-24:]}')
        run = run + 1 if k == '다' else 0
        if run == 4:
            bad += 1; print(f'[다×4] {title.split()[0]} {sents[i][-24:]}')
    print(f'{title.split()[0]} 문장 {len(sents)} · 요 {kinds.count("요")} · 다 {kinds.count("다")} · 죠 {kinds.count("죠")} · 기타 {kinds.count("기타")}')
print('걸린 곳', bad)
sys.exit(1 if bad else 0)
