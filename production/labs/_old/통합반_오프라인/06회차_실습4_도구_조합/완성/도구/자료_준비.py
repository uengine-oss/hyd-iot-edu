"""자료 저장소(자료/)를 만든다.

실행: 시작 폴더에서  python 도구/자료_준비.py
자료_판본/ 의 판본을 차례대로 자료/ 에 넣고, 판본마다 변경 기록(커밋)을 하나씩 남긴다.
자료/ 가 이미 있으면 아무것도 바꾸지 않고 지금의 변경 기록만 보여 준다.
"""
import json
import os
import shutil
import subprocess
import sys

여기 = os.path.dirname(os.path.abspath(__file__))
뿌리 = os.path.dirname(여기)
판본 = os.path.join(여기, "자료_판본")
자료 = os.path.join(뿌리, "자료")


def git(*args, env=None):
    r = subprocess.run(["git", *args], cwd=자료, env=env, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.exit("git " + " ".join(args) + " 이(가) 실패했다:\n" + r.stderr)
    return r.stdout


def 넣기(폴더):
    밑 = os.path.join(판본, 폴더)
    for 길, _, 파일들 in os.walk(밑):
        for 이름 in 파일들:
            원본 = os.path.join(길, 이름)
            대상 = os.path.join(자료, os.path.relpath(원본, 밑))
            os.makedirs(os.path.dirname(대상), exist_ok=True)
            shutil.copyfile(원본, 대상)


def 기록_보이기():
    print(git("-c", "core.quotepath=false", "log", "--date=format:%Y-%m-%d %H:%M", "--format=%h  %ad  %an  %s"))
    print(git("-c", "core.quotepath=false", "status", "--short") or "(커밋되지 않은 변경 없음)")


def main():
    if shutil.which("git") is None:
        sys.exit("git 을 찾지 못했다. Git 이 설치되어 있는지 확인한다.")
    if os.path.exists(자료):
        if not os.path.isdir(os.path.join(자료, ".git")):
            sys.exit("자료/ 폴더가 있는데 저장소가 아니다. 자료/ 폴더를 지우고 다시 실행한다.")
        print("자료/ 가 이미 있다. 바꾸지 않았다. 지금의 변경 기록:\n")
        기록_보이기()
        return
    os.makedirs(자료)
    git("init", "-q", "-b", "main")
    for 키, 값 in (("core.autocrlf", "false"), ("core.quotepath", "false"), ("commit.gpgsign", "false")):
        git("config", 키, 값)
    with open(os.path.join(판본, "차례.json"), encoding="utf-8") as f:
        차례 = json.load(f)
    for 한 in 차례:
        넣기(한["폴더"])
        env = dict(os.environ)
        for 누구 in ("AUTHOR", "COMMITTER"):
            env["GIT_" + 누구 + "_NAME"] = 한["사람"]
            env["GIT_" + 누구 + "_EMAIL"] = ""
            env["GIT_" + 누구 + "_DATE"] = 한["때"]
        git("add", "-A")
        git("commit", "-q", "-m", 한["내용"], env=env)
    넣기("작업중")
    print("자료/ 를 만들었다. 변경 기록 %d건:\n" % len(차례))
    기록_보이기()


if __name__ == "__main__":
    main()
