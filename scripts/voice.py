"""한국어 목소리 복제 도구 (CosyVoice3, CPU) - 여러 목소리를 이름으로 저장해 두고 골라 쓴다.

  python voice.py add 민수 ref.m4a [--text "녹음 속 실제 대사"]   목소리 등록
  python voice.py list                                           등록된 목소리
  python voice.py remove 민수                                     삭제
  python voice.py say 민수 "안녕하세요. [breath] 반가워요." [--emotion 기쁨] [--speed 1.0]
  python voice.py talk                                           모델을 한 번만 켜고 계속 대화형으로 합성

문장 태그: [breath] 숨소리  [laughter] 웃음  [cough] 기침  <strong>강조</strong>
감정: 기쁨 슬픔 화남 작게 크게 느리게 빠르게 (또는 직접 쓴 지시문)
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

BASE = os.environ.get("VOICE_DIR", "/voice")
VOICES = f"{BASE}/voices"
OUT = f"{BASE}/outputs"
MODEL_DIR = f"{BASE}/models/Fun-CosyVoice3-0.5B"
WHISPER_DIR = f"{BASE}/models/whisper"
HEAD = "You are a helpful assistant."
MAX_REF_SEC = 20

# CosyVoice 공식 예제에 있는 지시문만 프리셋으로 쓴다 (한국어 지시문은 검증되지 않음)
EMOTIONS = {
    "기쁨": "请非常开心地说一句话。",
    "슬픔": "请非常伤心地说一句话。",
    "화남": "请非常生气地说一句话。",
    "작게": "Please say a sentence in a very soft voice.",
    "크게": "Please say a sentence as loudly as possible.",
    "느리게": "请用尽可能慢地语速说一句话。",
    "빠르게": "请用尽可能快地语速说一句话。",
}


# ---------- 텍스트 처리 ----------
_D = "영일이삼사오육칠팔구"
_U = ["", "십", "백", "천"]
_B = ["", "만", "억", "조"]


def num_to_korean(n: int) -> str:
    if n == 0:
        return "영"
    parts, idx = [], 0
    while n > 0:
        n, chunk = divmod(n, 10000)
        if chunk:
            s = ""
            for i, ch in enumerate(reversed(str(chunk))):
                d = int(ch)
                if d:
                    s = (("" if d == 1 and i > 0 else _D[d]) + _U[i]) + s
            parts.append(("만" if (chunk == 1 and idx == 1) else s + _B[idx]) if idx == 1 and chunk == 1 else s + _B[idx])
        idx += 1
    return "".join(reversed(parts))


def normalize_ko(text: str) -> str:
    # CosyVoice의 영어용 정규화는 숫자를 영어로 읽어 버리므로, 숫자는 직접 한글(한자어)로 바꾼다
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)  # 12,000 -> 12000
    text = re.sub(r"\d+", lambda m: num_to_korean(int(m.group())) if len(m.group()) < 13 else m.group(), text)
    return re.sub(r"[ \t]+", " ", text).strip()


def split_text(text: str, max_len: int = 60):
    """문장 단위로 쪼개고, 너무 긴 문장은 쉼표/공백에서 한 번 더 나눈다. 태그는 쪼개지 않는다."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?…。！？])\s+|\n+", text) if s.strip()]
    out = []
    for s in sents:
        while len(s) > max_len:
            cut = max(s.rfind(c, 0, max_len) for c in (",", "，", " "))
            if cut < 20:
                cut = max_len
            out.append(s[:cut + 1].strip())
            s = s[cut + 1:].strip()
        if s:
            out.append(s)
    return out


# ---------- 목소리 저장소 ----------
def voice_dir(name):
    if not re.fullmatch(r"[\w가-힣-]+", name):
        sys.exit("이름에는 글자·숫자·_·- 만 쓸 수 있어요.")
    return f"{VOICES}/{name}"


def list_voices():
    if not os.path.isdir(VOICES):
        return []
    return sorted(d for d in os.listdir(VOICES) if os.path.exists(f"{VOICES}/{d}/ref.wav"))


def load_voice(name):
    d = voice_dir(name)
    if not os.path.exists(f"{d}/ref.wav"):
        sys.exit(f"'{name}' 목소리가 없어요. 등록된 목소리: {', '.join(list_voices()) or '(없음)'}")
    meta = json.load(open(f"{d}/meta.json", encoding="utf-8"))
    return f"{d}/ref.wav", meta["text"]


def preprocess_ref(src, dst):
    """잡음 줄이기 + 앞뒤/긴 무음 제거 + 음량 맞추기 + 24kHz 모노 + 최대 20초."""
    af = ("highpass=f=70,afftdn=nr=10:nf=-45,"
          "silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_duration=0.7:stop_threshold=-45dB,"
          "loudnorm=I=-20:TP=-2")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", af, "-ar", "24000", "-ac", "1", "-t", str(MAX_REF_SEC), dst]
    subprocess.run(cmd, check=True)


def wav_seconds(path):
    import soundfile as sf
    i = sf.info(path)
    return i.frames / i.samplerate


def transcribe(path):
    import whisper
    os.makedirs(WHISPER_DIR, exist_ok=True)
    print("녹음 속 대사를 받아 적는 중... (처음엔 모델을 내려받아요)")
    m = whisper.load_model("base", download_root=WHISPER_DIR, device="cpu")
    r = m.transcribe(path, language="ko", fp16=False, temperature=0)
    return r["text"].strip()


def cmd_add(a, model=None):
    if not os.path.exists(a.audio):
        sys.exit(f"파일이 없어요: {a.audio}")
    d = voice_dir(a.name)
    os.makedirs(d, exist_ok=True)
    preprocess_ref(a.audio, f"{d}/ref.wav")
    sec = wav_seconds(f"{d}/ref.wav")
    print(f"참조 음성 {sec:.1f}초")
    if sec < 5:
        print("⚠ 5초보다 짧아요. 10~20초면 품질이 훨씬 좋아져요.")
    text = a.text or transcribe(f"{d}/ref.wav")
    print("대사:", text)
    if not a.text:
        print("  (틀렸다면: voice.py add 이름 파일 --text \"정확한 대사\" 로 다시 등록하세요)")
    json.dump({"text": text}, open(f"{d}/meta.json", "w", encoding="utf-8"), ensure_ascii=False)
    m = model or get_model()
    m.add_zero_shot_spk(f"{HEAD}<|endofprompt|>{text}", f"{d}/ref.wav", a.name)
    m.save_spkinfo()
    print(f"'{a.name}' 저장 완료. 이제: say {a.name} \"문장\"")


def cmd_remove(a):
    d = voice_dir(a.name)
    if not os.path.isdir(d):
        sys.exit("없는 이름이에요.")
    shutil.rmtree(d)
    print(f"'{a.name}' 삭제됨 (캐시된 음색 정보는 다음 등록 때 덮어써져요).")


# ---------- 합성 ----------
_model = None


def get_model():
    global _model
    if _model is None:
        sys.path[:0] = ["/voice/repo/CosyVoice", "/voice/repo/CosyVoice/third_party/Matcha-TTS"]
        from cosyvoice.cli.cosyvoice import AutoModel
        _model = AutoModel(model_dir=MODEL_DIR)
    return _model


def synth(model, name, text, emotion="", speed=1.0, pause=0.3):
    import torch
    ref, ref_text = load_voice(name)
    if name not in model.frontend.spk2info:
        model.add_zero_shot_spk(f"{HEAD}<|endofprompt|>{ref_text}", ref, name)
    text = normalize_ko(text)
    chunks = split_text(text)
    instruct = EMOTIONS.get(emotion, emotion)
    pieces = []
    gap = torch.zeros(1, int(model.sample_rate * pause))
    for n, ch in enumerate(chunks, 1):
        print(f"[{n}/{len(chunks)}] {ch}")
        if instruct:
            # 감정 모드: 저장된 음색 대신 참조 wav + 지시문을 사용 (저장된 프롬프트가 지시문을 덮어쓰기 때문)
            gen = model.inference_instruct2(ch, f"{HEAD} {instruct}<|endofprompt|>", ref, speed=speed, text_frontend=False)
        else:
            gen = model.inference_zero_shot(ch, "", ref, zero_shot_spk_id=name, speed=speed, text_frontend=False)
        seg = torch.cat([o["tts_speech"] for o in gen], dim=1)
        pieces += [seg, gap]
    wav = torch.cat(pieces[:-1], dim=1)
    # 음량 맞추기: RMS -20dBFS 목표, 피크 0.95 이하
    rms = wav.pow(2).mean().sqrt().clamp(min=1e-6)
    wav = wav * (0.1 / rms)
    wav = wav * min(1.0, 0.95 / wav.abs().max().clamp(min=1e-6))
    return wav


def save(model, wav, name, out=None):
    import torchaudio
    os.makedirs(OUT, exist_ok=True)
    path = out or f"{OUT}/{name}_{time.strftime('%m%d_%H%M%S')}.wav"
    torchaudio.save(path, wav, model.sample_rate)
    print("저장:", path)
    return path


def cmd_say(a):
    m = get_model()
    save(m, synth(m, a.name, a.text, a.emotion, a.speed, a.pause), a.name, a.out)


def cmd_talk(a):
    m = get_model()
    cur, emo, speed = (list_voices() or [None])[0], "", 1.0
    print("대화형 모드. 문장을 입력하면 합성해요.\n"
          "  /목소리 이름   /감정 기쁨(끄려면 /감정 없음)   /속도 1.1   /목록   /끝")
    while True:
        try:
            line = input(f"[{cur} · 감정:{emo or '없음'} · 속도:{speed}] > ").strip()
        except EOFError:
            break
        if not line:
            continue
        if line.startswith("/"):
            cmd, _, arg = line[1:].partition(" ")
            arg = arg.strip()
            if cmd in ("끝", "q", "quit"):
                break
            elif cmd == "목록":
                print(", ".join(list_voices()) or "(없음)")
            elif cmd == "목소리" and arg in list_voices():
                cur = arg
            elif cmd == "감정":
                emo = "" if arg in ("없음", "") else arg
            elif cmd == "속도":
                speed = float(arg or 1)
            else:
                print("모르는 명령이거나 없는 목소리예요. /목록 으로 확인하세요.")
            continue
        if not cur:
            print("먼저 목소리를 등록하세요: voice.py add 이름 파일")
            continue
        save(m, synth(m, cur, line, emo, speed), cur)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("add"); x.add_argument("name"); x.add_argument("audio"); x.add_argument("--text")
    s.add_parser("list")
    x = s.add_parser("remove"); x.add_argument("name")
    x = s.add_parser("say"); x.add_argument("name"); x.add_argument("text")
    x.add_argument("--emotion", default=""); x.add_argument("--speed", type=float, default=1.0)
    x.add_argument("--pause", type=float, default=0.3); x.add_argument("--out")
    s.add_parser("talk")
    a = p.parse_args()
    if a.cmd == "add":
        cmd_add(a)
    elif a.cmd == "list":
        print("\n".join(list_voices()) or "(등록된 목소리 없음)")
    elif a.cmd == "remove":
        cmd_remove(a)
    elif a.cmd == "say":
        cmd_say(a)
    elif a.cmd == "talk":
        cmd_talk(a)


if __name__ == "__main__":
    main()
