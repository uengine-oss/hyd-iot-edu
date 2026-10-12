# PR-7.4 구매 총비용 경계

최초 실제 C 결정은 승인·효과가 모두 0인 상태에서 대체 공급사를 추천했다. 당시 cards.score_option은 구매 카드에도 물리 유온 예측과 MES 생산 납기 점수를 가산했고, 단가 BSC 이득과 전수 검사 감점이 상쇄되어 순정/대체가 동점이었다. 원본 결정은 보존하며 과거 추천을 수정하지 않는다.

원문 docs/samples/PR-07_spare-parts-standard.md PR-7.4는 단가×수량+수량×불량률×불량 1건 손실과 조건부 전수 검사 비용을 비교한다. 실제 수량6의 A 견적은 210+180+20=410만원, 순정은330+30=360만원이다. 비승인 공급사는 AVL 규정으로 제외한다.

검토된 원문 정책 purchase_comparison_policy를 원문 anchor와 함께 Skill JSON에 보존한다. 금액/불량률 기준은 원문 인용과 대조하며 실제 Part 견적·수량·필요일·AVL이 없으면 계산을 거부한다. 구매 총비용 순위에는 물리 예측/MES 점수를 넣지 않는다. 현재 승인 재검사는 원문 정책과 실제 경제 비교 영수증의 변경을 검사한다. 정책 등록·배포·실제 선택과 효과 검증은 root가 공식 새 판본 경로에서 수행하며 이 문서는 운영 완료 증거를 대신하지 않는다.

집중 검증: 최초 87 passed(구매·기존 A 카드·현재 승인). 범위를 원문 정책 그래프 보존까지 넓힌 검사에서는 130 passed/1 failed였으며, 실패는 새 시험의 원문 anchor start/end 미입력으로 정식 좌표 검증이 거부한 것이다. 기대값과 검증기는 바꾸지 않고 새 입력 좌표를 보강했다. 이후 신규 총비용/원문 경계/현재 승인 검사는 16 passed(0.81초), 생성 스키마 검사는16 passed(0.09초)이다. 별도 신규 승인 시험은 테스트 역할 원천 name/deptName 누락 실패를 보존하고 실제 DTO 필수 입력을 보강했다. 전체 회귀는 재실행하지 않았다.

F/pytest-purchase-total-first.log는 초기 작성 중 문법 오류, final.log는 좌표 입력 누락 실패를 보존한다. corrected.log는 신규 역할 입력 누락 실패이며 corrected2.log가 신규16개 성공 증거다. final2.log는 잘못된 검사 파일명을 지정하여 실행되지 않은 기록이다. F/PR-comparison-review-producer.json은 실제 저장 추출 제안을 순수 apply_review로 검사하여 제안과 최초 리뷰 불변, 추출 method와 사용자위임 review_method 구분, 정확한 PR7.4 source anchor를 확인했다.

변경된 기존 시험은 test_purchase_scope_model.runtime_skill 입력 생산자에 명시 원문 비용 정책을 가산한 것뿐이며 기존 assertion/정본 seed/골든은 변경하지 않았다. 신규 test_purchase_total_cost는 410>360, AVL 제외와 비승인 검사비 미가산, 물리값 및 물리 ranking table 독립, 가격/수량/불량률/납기/AVL 재계산, missing/cross-source/tampered-quote 거부, 원문→그래프 JSON 보존, 현재 preview의 역사 불변 및 견적 변경 승인 거부를 검증한다.

운영 인계: process/agent/dmn-mcp는 Dockerfile이 공용 라이브러리를 COPY하므로 새 빌드가 필요하며 agent/dmn-mcp는 새 T3 Skill template도 COPY한다. 정식 신규 PR 검토는 reviews/PR-07-comparison.review.json이며 기존 accepted marker와 원결정은 보존한다. 현재 T_approve workitem의 공식 decision-preview({decision,option:OEM,parameters:{}})→반환 review_id를 선택 승인에 보내는 경로가 현재 graph/견적을 다시 계산한다. preview와 최종 approval-check가 새 경제 원문 및 실제 값이 같음을 검사하고 기존 DEC 추천을 덮지 않는다. 실제 API/ERP 효과 완료는 root 운영 증거로 별도 판정해야 한다.
