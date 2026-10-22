"""내 목소리 복제 + 한국어 감정/숨소리 합성 (CosyVoice3, CPU).

사용: python clone_voice.py "텍스트" ["ref.wav의 실제 대사"]

텍스트 안에서 쓸 수 있는 태그:
  [breath] 숨소리   [laughter] 웃음   [cough] 기침   [noise] 잡음
  <strong>강조</strong>
감정/말투는 EMOTION 환경변수로 지시 (예: EMOTION="슬프고 떨리는 목소리로 말해 주세요.")
"""
import os
import sys

sys.path[:0] = ["/voice/repo/CosyVoice", "/voice/repo/CosyVoice/third_party/Matcha-TTS"]
import torchaudio
from cosyvoice.cli.cosyvoice import AutoModel

BASE = "/voice"
REF = f"{BASE}/samples/ref.wav"
text = sys.argv[1] if len(sys.argv) > 1 else "안녕하세요. [breath] 제 목소리를 복제했어요."
ref_text = sys.argv[2] if len(sys.argv) > 2 else ""
emotion = os.environ.get("EMOTION", "")

model = AutoModel(model_dir=f"{BASE}/models/Fun-CosyVoice3-0.5B")
head = "You are a helpful assistant."

if emotion:
    # 감정/말투 지시 모드
    gen = model.inference_instruct2(text, f"{head} {emotion}<|endofprompt|>", REF)
elif ref_text:
    # 참조 대사를 알 때: 음색 유사도 최고
    gen = model.inference_zero_shot(text, f"{head}<|endofprompt|>{ref_text}", REF)
else:
    gen = model.inference_cross_lingual(f"{head}<|endofprompt|>{text}", REF)

os.makedirs(f"{BASE}/outputs", exist_ok=True)
for i, out in enumerate(gen):
    path = f"{BASE}/outputs/out_{i}.wav"
    torchaudio.save(path, out["tts_speech"], model.sample_rate)
    print("저장:", path)
