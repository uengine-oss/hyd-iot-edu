// 5분 예시(06-2 4장을 랩 한 바퀴로 줄인 것 — 근거 판정/샘플5분_대본.md)의 구간들이 함께 쓰는 값과 그림.
// 랩 폴더는 LABS.ws(06-2 2 · 3장을 학생 역 Codex로 마친 상태). 결과 화면은 둘째 페이지(PAGE=1)에서 찍는다.
export const RESULT_TITLE = '식별자와 관계';   // python run.py design 결과 화면의 제목 앞머리(첫 구간)
export const NAMES_TITLE = '구성 요소 이름과 실물';   // python run.py names 결과 화면의 제목 앞머리(끝 구간)
// 펌프 자리와 실물(프레임 px 1920×1080) — 편집기에 열린 components.csv 위에 판을 두고 긋는다.
export const SEAT = {id: '펌프 자리와 실물', board: [470, 200, 960, 620], items: [
 {id: 'seat', kind: 'box', at: [560, 270, 340, 90], text: '펌프가 놓이는 자리'},
 {id: 's1', kind: 'box', at: [1040, 240, 300, 60], text: '압력 센서'},
 {id: 's2', kind: 'box', at: [1040, 330, 300, 60], text: '유량 센서'},
 {id: 'as1', kind: 'arrow', from: 'seat', to: 's1'},
 {id: 'as2', kind: 'arrow', from: 'seat', to: 's2'},
 {id: 'now', kind: 'box', at: [540, 480, 220, 80], text: '지금 펌프'},
 {id: 'old', kind: 'box', at: [800, 480, 220, 80], text: '떼어 낸 펌프'},
 {id: 'an', kind: 'arrow', from: 'seat', to: 'now'},
 {id: 'ao', kind: 'arrow', from: 'seat', to: 'old'},
 {id: 'r1', kind: 'text', at: [520, 640], text: '길 1 — 일련번호를 자리의 속성으로'},
 {id: 'r2', kind: 'text', at: [520, 710], text: '길 2 — 펌프 한 대 한 대를 따로'},
]};
// 첫 번째 부탁(길뚫기에서 실제로 보낸 글 — 판정/길뚫기/고르기_d1.prompt.txt와 같다)
export const ASK1 = '파일은 바꾸지 말고 답해 줘. HYD-02 주 펌프 자리에 지난 펌프와 지금 펌프 두 줄이 있어. 일련번호를 구성 요소의 속성으로 둘 때와, 일련번호가 붙은 실물을 클래스로 따로 둘 때, 질문 1(설비의 구성 요소마다 어떤 센서가 붙고, 그 자리에 어떤 장치가 달렸나)의 답이 어떻게 달라지는지 실제 줄로 보여 주고, 추천과 그 이유도 말해 줘.';
// 두 번째 부탁(결정을 적고 그 결정대로 표를 맞추기 — 샘플에서 처음 보내는 묶은 부탁)
export const ASK2 = '「구성 요소 자리와 그 실물」 지점은 「실물을 클래스로 따로 둔다」로 정했어. 이유는 질문 1이 그 자리에 달린 장치를 일련번호로 묻고, 보전팀이 떼어 낸 펌프 행도 비고를 달아 보냈기 때문이야. 열어 본 근거 줄은 data/components.csv:13 · 14야. 그래서 HYD-02 펌프 자리의 답은 지금 실물 KP-2603-114와 지난 실물 KP-1902-551 둘이 돼. decisions.csv의 이 지점 줄에 적고, 이 선택대로 row_rules.csv의 떼어 낸 펌프 줄과 design.csv · relations.csv를 맞춰 줘. 근거 칸에는 내가 말한 이유를 적어 줘. 판단 함수 파일(.py)과 expected.csv는 바꾸지 마.';
