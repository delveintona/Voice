#!/data/data/com.termux/files/usr/bin/bash
# 사용:  bash run_phone.sh add 이름 녹음파일 | list | remove 이름 | say 이름 "문장" | talk
# (녹음파일은 SD의 voice/samples/ 폴더 안 이름만 써도 됨)
. "$HOME/.voice_env"
cp "$(dirname "$0")/voice.py" "$VOICE_BASE/voice.py"   # 항상 최신 버전 사용
mkdir -p "$VOICE_BASE/voices" "$VOICE_BASE/outputs"
ARGS=()
for a in "$@"; do
  # samples 폴더의 파일명을 그대로 쓸 수 있게 경로 보정
  if [ ! -e "$a" ] && [ -e "$VOICE_BASE/samples/$a" ]; then a="/voice/samples/$a"; fi
  ARGS+=("$a")
done
proot-distro login ubuntu --bind "$VOICE_BASE:/voice" -- bash -lc '. /root/venv/bin/activate && python /voice/voice.py "$@"' _ "${ARGS[@]}"
