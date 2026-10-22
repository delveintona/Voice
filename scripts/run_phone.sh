#!/data/data/com.termux/files/usr/bin/bash
# 사용: bash run_phone.sh "합성할 문장" ["참조 음성의 실제 대사"]
. "$HOME/.voice_env"
proot-distro login ubuntu --bind "$VOICE_BASE:/voice" -- bash -lc ". /root/venv/bin/activate && python /voice/clone_voice.py \"\$@\"" _ "$@"
