# 3-3 · 조치가 지표에 미치는 영향 관계 만들기

## 만들 것

조치와 성과 지표를 그래프에 넣고 "조치 → 영향 받는 지표" 관계를 만드는 프로그램 `work/load_effects.py`, 조치 하나의 좋은 영향과 나쁜 영향을 함께 찾는 프로그램 `work/action_effects.py`. 스키마 파일에도 새 클래스와 관계를 더합니다.

## 왜 만드나

조치 하나는 여러 지표를 함께 움직입니다. 팬을 세게 돌리면 온도는 내려가지만 전력비는 오릅니다. 이 방향을 지식으로 남겨 두어야 "가능한 조치"와 "더 유리한 조치"를 가를 수 있습니다. 다만 얼마나 오르고 내리는지는 계산해 보기 전에는 모릅니다. 추측한 숫자를 사실처럼 저장하면 뒤에서 누군가 그 숫자를 믿고 판단하게 됩니다.

## 주어지는 자료

- `day3/data/actions.csv` — 조치 3개
- `day3/data/measures.csv` — 성과 지표 4개
- `day3/data/action_effects.csv` — 조치가 지표에 주는 영향 7줄. `effect`는 긍정 또는 부정, `basis`는 이유, `note`에는 누군가 적어 둔 추정 숫자가 섞여 있다
- `cooler/schema_guide.md`의 Action · Measure · AFFECTS

## Claude Code에 전달할 요구사항의 뼈대

- **목표**: 조치와 지표를 그래프에 넣고 AFFECTS 관계를 만든 뒤, 조치 번호로 영향을 찾는다.
- **입력 자료**: 위 CSV 세 개. `action_id` · `measure_id`가 노드의 `id`.
- **꼭 지킬 것**
  - `work/schema.json`에 Action · Measure 클래스와 AFFECTS 관계를 더하고 고유 제약도 그래프에 건다(`apply_schema.py` 다시 실행).
  - 관계에는 방향(`effect`)과 이유(`basis`)만 넣는다. `note` 칸의 추정 숫자는 어떻게 다룰지 내가 정해서 말해 준다.
  - 다시 넣어도 늘어나지 않는다.
- **출력 모양**: `python work/action_effects.py --action-id ACT-FAN-UP`

```json
{"found": true, "action": {"id": "ACT-FAN-UP", "name": "…"}, "positive": [{"measure_id": "…", "measure": "…", "basis": "…"}], "negative": [{"measure_id": "…", "measure": "…", "basis": "…"}]}
```

  없는 조치면 `found`는 `false`, 두 목록은 빈 목록.
- **완료 기준**: 조치 하나를 물으면 긍정 영향과 부정 영향이 함께 나온다.

## 무엇이 나오면 성공

```
python -m labcheck 3-3
```

- 스키마 파일과 그래프에 Action · Measure와 고유 제약이 있다
- 조치 → 지표 관계 7개와 방향이 CSV와 같고, 겹친 관계가 없다
- 관계에 계산하지 않은 추정 숫자가 들어 있지 않다
- 조치마다 긍정 · 부정 영향을 받는 지표가 함께 나온다

## 다음 랩에서 어떻게 쓰이나

4일차에 매뉴얼에서 뽑은 "고장 → 조치" 지식이 같은 조치 노드에 이어집니다. 7일차에는 조치별 효과와 비용을 숫자로 비교한 자료가 따로 주어집니다. 그 숫자는 비교 자료에 있고, 그래프에는 방향만 있다는 점을 기억해 둡니다.
