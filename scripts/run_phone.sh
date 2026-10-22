#!/data/data/com.termux/files/usr/bin/bash
# 사용:  bash run_phone.sh add 이름 녹음파일 | list | remove 이름 | say 이름 "문장" | talk
# 녹음파일은 휴대폰 '다운로드' 폴더에 넣고 파일 이름만 쓰면 된다.
# 결과 wav는 자동으로 '다운로드/목소리결과' 폴더에도 복사된다 (파일 앱/음악 앱에서 재생 가능).
. "$HOME/.voice_env"
DL="$HOME/storage/downloads"
cp "$(dirname "$0")/voice.py" "$VOICE_BASE/voice.py"   # 항상 최신 버전 사용
mkdir -p "$VOICE_BASE/voices" "$VOICE_BASE/outputs" "$VOICE_BASE/samples"
ARGS=()
for a in "$@"; do
  if [ ! -e "$a" ] && [ -e "$VOICE_BASE/samples/$a" ]; then
    a="/voice/samples/$a"
  elif [ ! -e "$a" ] && [ -e "$DL/$a" ]; then
    cp "$DL/$a" "$VOICE_BASE/samples/$a" && a="/voice/samples/$a"
  fi
  ARGS+=("$a")
done
proot-distro login ubuntu --bind "$VOICE_BASE:/voice" -- bash -lc '. /root/venv/bin/activate && python /voice/voice.py "$@"' _ "${ARGS[@]}"
RC=$?
if [ -d "$DL" ]; then
  mkdir -p "$DL/목소리결과" && cp -u "$VOICE_BASE"/outputs/*.wav "$DL/목소리결과/" 2>/dev/null && echo "결과 복사됨 → 다운로드/목소리결과/"
fi
exit $RC
