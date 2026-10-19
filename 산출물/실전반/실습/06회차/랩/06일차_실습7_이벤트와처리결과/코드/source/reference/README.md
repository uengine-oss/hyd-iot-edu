# 참조 흐름

저장소 students/flows의 제공 참조다. 이번 제작에서 실행하지 않았다. 직접 만든 결과는 output에 저장한다. 참조 mapping의 ID를 직접 그린 BPMN 요소 ID와 대응시킨 후 사용한다. agent:cooling은 기본 예이므로 기존에 만든 에이전트의 실제 ID로 연결한다.

BPMN과 mapping.json을 함께 읽는다. 제공 XML에는 승인·회복의 실행 조건과 타이머 PT10M 값이 들어 있지 않다. 이 값은 mapping.json의 flows와 timers에 있다. 직접 그린 요소 ID에 대응시켜 저장하고 사전 검사에서 확인한다. 그림의 선 이름만으로 실행 조건이 적용되지는 않는다.
