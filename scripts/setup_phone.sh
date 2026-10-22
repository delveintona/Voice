#!/data/data/com.termux/files/usr/bin/bash
# Termux에서 실행: bash setup_phone.sh [SD카드경로]
# - 모델/레포/결과물(용량 큰 것)은 SD카드에, 파이썬 환경(실행권한 필요)은 내부 저장소 proot Ubuntu에 만든다.
#   (SD카드는 FAT/exFAT라 심볼릭링크·실행권한이 안 돼서 venv를 SD에 만들 수 없음)
set -euo pipefail

SD="${1:-}"
if [ -z "$SD" ]; then
  # Termux가 보는 외장 SD 경로 자동 탐색 (termux-setup-storage 이후 ~/storage/external-1)
  for p in "$HOME"/storage/external-1 /storage/????-????; do
    [ -d "$p" ] && SD="$p" && break
  done
fi
[ -n "$SD" ] && [ -d "$SD" ] || { echo "SD카드 경로를 못 찾음. termux-setup-storage 실행 후 다시: bash $0 /storage/XXXX-XXXX"; exit 1; }

# Termux는 SD카드의 Android/data/com.termux/files 아래만 쓰기 가능
if [ -d "$SD/Android/data/com.termux/files" ]; then BASE="$SD/Android/data/com.termux/files/voice"; else BASE="$SD/voice"; fi
mkdir -p "$BASE"/{repo,models,samples,outputs}
echo "작업 폴더(SD): $BASE"
echo "export VOICE_BASE=\"$BASE\"" > "$HOME/.voice_env"

pkg update -y && pkg upgrade -y -o Dpkg::Options::="--force-confnew"
dpkg --configure -a || true
pkg install -y git proot-distro ffmpeg
proot-distro list | grep -q "ubuntu.*installed" || proot-distro install ubuntu

# 레포 다운로드 (Apache-2.0, 한국어/감정 instruct/[breath] 지원)
[ -d "$BASE/repo/CosyVoice/.git" ] || git clone --depth 1 --recursive https://github.com/FunAudioLLM/CosyVoice "$BASE/repo/CosyVoice"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/clone_voice.py" "$BASE/clone_voice.py"

# proot Ubuntu 안에 파이썬 환경 구성 (SD를 /voice 로 마운트)
proot-distro login ubuntu --bind "$BASE:/voice" -- bash -lc '
  set -e
  apt-get update && apt-get install -y python3 python3-venv python3-pip git ffmpeg sox libsox-dev build-essential
  python3 -m venv /root/venv
  . /root/venv/bin/activate
  pip install -U pip wheel
  pip install torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cpu
  # CPU 전용: GPU/CUDA 전용 패키지(deepspeed, tensorrt, onnxruntime-gpu)는 제외
  grep -v -E "^(--|deepspeed|tensorrt|onnxruntime-gpu|torch|torchaudio)" /voice/repo/CosyVoice/requirements.txt > /root/req-cpu.txt
  echo "onnxruntime==1.18.0" >> /root/req-cpu.txt
  pip install -r /root/req-cpu.txt
  python - <<PY
from modelscope import snapshot_download
snapshot_download("FunAudioLLM/Fun-CosyVoice3-0.5B-2512", local_dir="/voice/models/Fun-CosyVoice3-0.5B")
PY
'
echo "완료. 내 목소리 샘플(10~30초, wav)을 $BASE/samples/ref.wav 로 넣고:  bash $(dirname "$0")/run_phone.sh \"합성할 문장\""
