#!/usr/bin/env bash
# 클라우드 VM에서 이 PC와 같은 줄바꿈으로 덱을 렌더하는 환경을 만든다(apt의 LibreOffice 24.2는 줄바꿈이 달라 판정에 못 쓴다).
#   sudo bash workspace/강의제작/제작도구/기존제작/tools/deck/렌더환경_클라우드.sh <맑은 고딕 TTF가 든 폴더>
# 하는 일(이미 된 단계는 건너뛴다):
#   1. /opt/lo268 에 우분투 26.10(stonking) 최소 chroot — debootstrap(없으면 apt로 깐다)
#   2. 그 안에 libreoffice-impress 26.8 · fonts-noto-cjk · ko_KR.UTF-8 로캘
#   3. 맑은 고딕(MALGUN*.TTF)을 chroot와 VM 양쪽 /usr/share/fonts/malgun/에 넣고 fc-cache (글꼴은 커밋하지 않는다)
#   4. /proc · /dev · /sys 와 저장소 루트를 같은 경로로 bind mount — VM이 다시 켜지면 이 스크립트를 다시 돌린다
#   5. /usr/local/lo268/bin/soffice 감싸개: 그 chroot의 soffice를 지금 폴더에서 돌린다
# 렌더: PATH=/usr/local/lo268/bin:$PATH python3 .claude/skills/hyd-course-deck/scripts/deck2pptx.py <덱.pptx> --render <새 폴더>
#   (빌더의 글꼴 검사 · 잠금 · pdftoppm 80dpi가 그대로 돈다). 실측 2026-11-04: LibreOffice 26.8.1.1, 3 · 4회차 VM 렌더와 같은 판.
set -euo pipefail
FONTS=${1:?맑은 고딕 TTF가 든 폴더를 준다}
R=${LO_ROOT:-/opt/lo268}
REPO=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
MIRROR=${UBUNTU_MIRROR:-http://archive.ubuntu.com/ubuntu}
ls "$FONTS"/[Mm][Aa][Ll][Gg][Uu][Nn]*.[Tt][Tt][Ff] >/dev/null   # 글꼴이 없으면 여기서 멈춘다

if [ ! -x "$R/usr/bin/apt-get" ]; then
  command -v debootstrap >/dev/null || { apt-get update -qq && apt-get install -y -qq debootstrap; }
  # debootstrap에 새 판 이름표가 없어 같은 꼴의 gutsy 스크립트를 쓴다
  debootstrap --variant=minbase --include=ca-certificates,locales stonking "$R" "$MIRROR" /usr/share/debootstrap/scripts/gutsy
fi
for d in proc dev sys; do mountpoint -q "$R/$d" || mount --bind "/$d" "$R/$d"; done
mkdir -p "$R$REPO"; mountpoint -q "$R$REPO" || mount --bind "$REPO" "$R$REPO"
cp /etc/resolv.conf "$R/etc/resolv.conf"
[ -f /root/.ccr/ca-bundle.crt ] && cp /root/.ccr/ca-bundle.crt "$R/usr/local/share/ca-certificates/ccr.crt"
if [ ! -x "$R/usr/bin/soffice" ]; then
  printf 'deb %s stonking main universe\ndeb %s stonking-updates main universe\n' "$MIRROR" "$MIRROR" > "$R/etc/apt/sources.list"
  chroot "$R" /usr/bin/env http_proxy="${http_proxy:-}" https_proxy="${https_proxy:-}" DEBIAN_FRONTEND=noninteractive bash -c '
    update-ca-certificates >/dev/null
    apt-get update -qq && apt-get install -y -qq --no-install-recommends libreoffice-impress fonts-noto-cjk locales
    sed -i "s/^# *ko_KR.UTF-8/ko_KR.UTF-8/" /etc/locale.gen && locale-gen ko_KR.UTF-8 >/dev/null'
fi
for root in "$R" ""; do
  mkdir -p "$root/usr/share/fonts/malgun"; cp "$FONTS"/[Mm][Aa][Ll][Gg][Uu][Nn]*.[Tt][Tt][Ff] "$root/usr/share/fonts/malgun/"
done
chroot "$R" fc-cache -f >/dev/null; fc-cache -f >/dev/null
mkdir -p /usr/local/lo268/bin
cat > /usr/local/lo268/bin/soffice <<EOF
#!/usr/bin/env bash
# 렌더환경_클라우드.sh가 만든 감싸개 — $R 의 LibreOffice를 지금 폴더에서 돌린다(경로는 bind mount라 같다)
exec chroot "$R" /usr/bin/env -i HOME=/root LANG=ko_KR.UTF-8 LC_ALL=ko_KR.UTF-8 PATH=/usr/bin:/bin \\
  bash -c 'cd "\$1" && shift && exec /usr/bin/soffice "\$@"' _ "\$PWD" "\$@"
EOF
chmod +x /usr/local/lo268/bin/soffice
/usr/local/lo268/bin/soffice --version
chroot "$R" fc-list | grep -i malgun | head -3
