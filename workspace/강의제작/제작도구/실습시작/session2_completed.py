"""2회차 네 랩(두 과정의 설계 · 그래프 랩)의 학생용 완성본은 이 파일이 만들지 않는다.

네 랩은 새 프로젝트 구조로 바뀌었고, 완성본(`산출물/<과정>/실습/02회차/완성본/<랩>-completed.zip`)은 랩을 만드는 생성기가 `--completed`로 함께 만든다.
옛 구조 랩 폴더를 복사해 완성본을 묶던 길은 그 폴더를 지웠으므로 없앴다. 이 파일을 돌리면 새 생성기 이름을 대며 멈춘다.
"""

NEW_GENERATOR = {
    '통합반 설계 · 그래프': 'build_session2_projects.py <ontology|graph> --apply --completed',
    '실전반 설계 · 그래프': 'build_practical2_projects.py <ontology|graph> --apply --completed',
}


def main():
    raise SystemExit('session2_completed.py는 완성본을 만들지 않습니다. 2회차 완성본은 랩 생성기가 만듭니다:\n'
                     + '\n'.join(f'  {course}: {how}' for course, how in NEW_GENERATOR.items()))


if __name__ == '__main__':
    main()
