# 연습용 그래프의 스키마 설명

스키마는 "그래프에 어떤 종류의 것을, 어떤 이름표와 속성으로, 무엇과 무엇을 잇는가"를 정한 약속입니다. 랩에서는 아래 이름을 그대로 씁니다. 수업 스택의 스키마에서 쓰는 이름과 같아서, 나중에 큰 그래프를 볼 때도 같은 눈으로 읽을 수 있습니다.

## 클래스 (노드의 종류)

| 클래스 | 뜻 | 꼭 있어야 하는 속성 | 그 밖의 속성 | 언제 쓰나 |
|---|---|---|---|---|
| Asset | 설비 | id, name | line, model | 2일차 |
| Component | 부품 | id, name | kind | 2일차 |
| Sensor | 센서 | id, name, tag | kind, unit | 2일차 |
| Action | 조치 | id, name | kind | 3일차 |
| Measure | 성과 지표 | id, name | unit, better | 3일차 |
| Symptom | 증상 | id, name | sensor_kind, operator, threshold, unit | 4일차 |
| FailureMode | 고장 | id, name | | 4일차 |
| Cause | 원인 | id, name | | 4일차 |

- `id`는 그 클래스 안에서 겹치면 안 됩니다(중복 금지). 설비는 설비 번호(CL-01), 센서는 센서 번호(CL-01-TT-OUT)가 `id`입니다.
- `name`은 사람이 읽는 이름입니다.
- Sensor의 `tag`는 연습용 DB에서 그 센서를 부르는 이름입니다. 그래프와 DB를 잇는 열쇠입니다.

## 관계 (노드를 잇는 선)

| 관계 | 어디에서 → 어디로 | 뜻 | 관계에 적는 것 | 언제 쓰나 |
|---|---|---|---|---|
| HAS_COMPONENT | Asset → Component | 설비가 부품을 가진다 | | 2일차 |
| HAS_SENSOR | Asset → Sensor | 설비에 센서가 붙어 있다 | | 2일차 |
| MONITORED_BY | Component → Sensor | 부품을 센서가 지켜본다 | | 2일차 |
| AFFECTS | Action → Measure | 조치가 지표에 영향을 준다 | effect(긍정 또는 부정), basis(이유) | 3일차 |
| CAN_HAVE | Asset → FailureMode | 설비에 생길 수 있는 고장 | doc | 4일차 |
| INDICATES | Symptom → FailureMode | 증상이 고장을 가리킨다 | 출처 | 4일차 |
| CAUSES | Cause → FailureMode | 원인이 고장을 일으킨다 | 출처 | 4일차 |
| REMEDIED_BY | FailureMode → Action | 고장을 조치로 푼다 | 출처 | 4일차 |

관계에는 방향이 있습니다. `Asset → Component`를 거꾸로 넣으면 "부품이 설비를 가진다"가 되어 찾을 때 걸리지 않습니다.

**출처**는 그 지식이 문서 어디에서 왔는지입니다. 4일차 관계에는 다음 다섯 가지를 함께 적습니다.

| 속성 | 뜻 | 예 |
|---|---|---|
| doc | 문서 번호 | CM-01 |
| section | 절 번호 | 2 |
| line | 그 문서 파일의 몇째 줄 | 12 |
| quote | 원문 문장 그대로 | 방열핀 막힘이 생기면 … |
| candidate_id | 어느 후보에서 왔나 | C02 |

## 스키마 파일의 모양

2일차 첫 랩에서 `work/schema.json`을 만듭니다. 모양은 이렇습니다.

```json
{
  "name": "소형 냉각장치 연습 스키마",
  "classes": [
    {
      "name": "Asset",
      "label_ko": "설비",
      "properties": [
        {"name": "id", "type": "string", "required": true},
        {"name": "name", "type": "string", "required": true}
      ],
      "unique": ["id"]
    }
  ],
  "relationships": [
    {"type": "HAS_COMPONENT", "from": "Asset", "to": "Component", "description": "설비가 부품을 가진다"}
  ]
}
```

- `classes[].unique`에 적은 속성은 그래프에서도 겹치지 않게 막아야 합니다(Neo4j의 고유 제약).
- 날이 지나며 클래스와 관계가 늘면 이 파일에도 더합니다. 스키마 파일과 그래프가 서로 다른 말을 하지 않게 합니다.
