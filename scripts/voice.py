"""한국어 목소리 복제 도구 (CosyVoice3, CPU) - 여러 목소리를 이름으로 저장해 두고 골라 쓴다.

  python voice.py add 민수 ref.m4a [--text "녹음 속 실제 대사"]   목소리 등록
  python voice.py list                                           등록된 목소리
  python voice.py remove 민수                                     삭제
  python voice.py say 민수 "안녕하세요. [breath] 반가워요." [--emotion 기쁨] [--speed 1.0] [--pause 1.0] [--takes 3]
  python voice.py talk                                           모델을 한 번만 켜고 계속 대화형으로 합성

문장 태그: [breath] 숨소리  [laughter] 웃음  [cough] 기침  <strong>강조</strong>  [pause 1.0] 직접 쉬기(초)
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

BASE = os.environ.get("VOICE_DIR", "/voice")           # 목소리·결과·사전 (남겨야 하는 것)
ENGINE = os.environ.get("VOICE_ENGINE", BASE)           # CosyVoice 코드·모델 (다시 받을 수 있는 것)
VOICES = f"{BASE}/voices"
OUT = f"{BASE}/outputs"
MODEL_DIR = f"{ENGINE}/models/Fun-CosyVoice3-0.5B"
WHISPER_DIR = f"{ENGINE}/models/whisper"
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
_DIGIT = "공일이삼사오육칠팔구"
_N_ONES = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"]
_N_TENS_PRE = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"]
_N_TENS_ALONE = ["", "열", "스무", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"]
# 고유어 수(한 개, 두 명, 세 시)로 읽는 단위. '시간'을 '시'보다 먼저 검사해야 한다.
_NATIVE_COUNTERS = "시간|시|명|개|살|마리|번째|번|대|권|잔|병|장|곳|가지|송이|그루|켤레|채|사람"
_UNITS = {"kg": "킬로그램", "km": "킬로미터", "cm": "센티미터", "mm": "밀리미터", "ml": "밀리리터", "g": "그램"}


def num_to_korean(n: int) -> str:
    """한자어 수: 2025 -> 이천이십오"""
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
            parts.append("만" if (idx == 1 and chunk == 1) else s + _B[idx])
        idx += 1
    return "".join(reversed(parts))


def native_to_korean(n: int, ordinal_first=False) -> str:
    """고유어 수(단위 앞 형태): 3 -> 세, 12 -> 열두, 20 -> 스무"""
    if n >= 100 or n <= 0:
        return num_to_korean(n)
    t, o = divmod(n, 10)
    if o == 0:
        return _N_TENS_ALONE[t]
    return _N_TENS_PRE[t] + _N_ONES[o]


def digits_to_korean(s: str) -> str:
    return " ".join(_DIGIT[int(c)] for c in s if c.isdigit())


def _counter(m):
    n, unit = int(m.group(1)), m.group(2)
    if n < 100:
        if unit == "번째" and n == 1:
            return "첫 번째"
        return f"{native_to_korean(n)} {unit}"
    return f"{num_to_korean(n)} {unit}"


def _month(m):
    n = int(m.group(1))
    return {6: "유월", 10: "시월"}.get(n, num_to_korean(n) + "월")


def _time(m):
    h, mi = int(m.group(1)), int(m.group(2))
    return f"{native_to_korean(h)} 시" + (f" {num_to_korean(mi)} 분" if mi else "")


def normalize_ko(text: str, user_dict=None) -> str:
    """[pause 1.0] 같은 쉼 태그의 숫자는 건드리지 않고, 나머지 글만 한국어식으로 바꾼다."""
    parts = re.split(r"(\[pause(?:\s+[\d.]+)?\])", text)
    return "".join(p if i % 2 else _normalize_part(p, user_dict) for i, p in enumerate(parts)).strip()


def _normalize_part(text: str, user_dict=None) -> str:
    """CosyVoice의 영어용 정규화는 숫자를 영어로 읽어 버리므로, 한국어식 읽기로 직접 바꾼다."""
    for k in sorted(user_dict or {}, key=len, reverse=True):
        text = text.replace(k, user_dict[k])
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text)  # 이모지 제거
    text = re.sub(r"[ㅋㅎ]{2,}", " [laughter] ", text)
    text = re.sub(r"[ㅠㅜ]{2,}", "", text)
    text = re.sub(r"([!?])\1+", r"\1", text)
    text = re.sub(r"\.{3,}", "…", text)
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)                                    # 12,000 -> 12000
    text = re.sub(r"(?<!\d)0\d{1,2}-\d{3,4}-\d{4}(?!\d)", lambda m: ", ".join(digits_to_korean(g) for g in m.group().split("-")), text)
    text = re.sub(rf"(\d+)\s?~\s?(\d+)\s?({_NATIVE_COUNTERS})", r"\1 \3에서 \2 \3", text)  # 1~3개 -> 1개에서 3개
    text = re.sub(r"(\d{1,2}):(\d{2})", _time, text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s?(kg|km|cm|mm|ml|g)\b", lambda m: m.group(1) + _UNITS[m.group(2)], text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s?%", r"\1 퍼센트", text)
    text = re.sub(r"(\d+)\.(\d+)", lambda m: f"{num_to_korean(int(m.group(1)))} 점 {digits_to_korean(m.group(2))}", text)
    text = re.sub(rf"(?<!\d)(\d{{1,6}})\s?({_NATIVE_COUNTERS})", _counter, text)
    text = re.sub(r"(?<!\d)(\d{1,2})월", _month, text)
    text = re.sub(r"(?<=\d)\s?~\s?(?=\d)", "에서 ", text)
    text = text.replace("~", "")

    def generic(m):
        d = m.group()
        return digits_to_korean(d) if (d[0] == "0" and len(d) > 1) or len(d) >= 13 else num_to_korean(int(d))

    text = re.sub(r"\d+", generic, text)
    return re.sub(r"[ \t]+", " ", text).strip()


_TAG = re.compile(r"\[(?:breath|laughter|cough|noise|clucking|accent)\]|</?strong>")
_PAUSE = re.compile(r"\[pause(?:\s+([\d.]+))?\]")


def _ends_pause(s):
    s = s.rstrip()
    if s.endswith("…"):
        return 0.7
    if s.endswith("?"):
        return 0.45
    if s.endswith(("!", ".", "。")):
        return 0.4
    if s.endswith((",", "，")):
        return 0.2
    return 0.3


def _split_long(s, max_len):
    out = []
    while len(s) > max_len:
        cut = max(s.rfind(c, 0, max_len) for c in (",", "，"))
        if cut < 15:
            cut = s.rfind(" ", 0, max_len)
        if cut < 15:
            cut = max_len - 1
        out.append(s[:cut + 1].strip())
        s = s[cut + 1:].strip()
    if s:
        out.append(s)
    return out


def plan(text: str, scale: float = 1.0, max_len: int = 70, min_len: int = 8):
    """텍스트 -> [(읽을 문장, 뒤에 쉬는 초)]. 문장부호·줄바꿈·[pause 0.5] 로 쉬는 시간을 정한다."""
    items = []  # [text, pause, explicit]
    paras = [p for p in re.split(r"\n+", text) if p.strip()]
    for pi, para in enumerate(paras):
        pos = 0
        for m in _PAUSE.finditer(para):
            _add_sentences(items, para[pos:m.start()], max_len)
            if items:
                items[-1][1], items[-1][2] = float(m.group(1) or 0.6), True
            pos = m.end()
        _add_sentences(items, para[pos:], max_len)
        if items and pi < len(paras) - 1 and not items[-1][2]:
            items[-1][1] = max(items[-1][1], 0.8)  # 문단 사이
    merged, i = [], 0
    while i < len(items):
        t, ps, ex = items[i]
        # 너무 짧은 문장은 모델이 어색하게 읽으므로 다음 문장과 붙인다 (명시한 쉼·문단 경계는 유지)
        while len(_TAG.sub("", t).strip()) < min_len and not ex and ps < 0.8 and i + 1 < len(items):
            i += 1
            t, ps, ex = t + " " + items[i][0], items[i][1], items[i][2]
        merged.append((t, ps * scale))
        i += 1
    return merged


def _add_sentences(items, part, max_len):
    part = part.strip()
    if not part:
        return
    for sent in re.split(r"(?<=[.!?…])\s+", part):
        sent = sent.strip()
        if not sent:
            continue
        pieces = _split_long(sent, max_len)
        for k, pc in enumerate(pieces):
            items.append([pc, _ends_pause(pc) if k == len(pieces) - 1 else 0.2, False])


def load_dict():
    path = f"{BASE}/dict.txt"
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("# 발음 사전: 원문=읽는법 (한 줄에 하나). 예)\n# GPT=지피티\n# 3D=삼디\n")
    d = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


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
    del m  # 메모리가 모자란 폰에서 음성 모델을 올리기 전에 반드시 내린다
    import gc
    gc.collect()
    return r["text"].strip()


def add_voice(name, audio, text="", model_fn=None, log=print):
    """목소리를 등록(전처리 -> 받아쓰기 -> 음색 저장). CLI와 웹 화면이 같이 쓴다."""
    if not audio or not os.path.exists(audio):
        raise FileNotFoundError(f"파일이 없어요: {audio}")
    d = voice_dir(name)
    os.makedirs(d, exist_ok=True)
    preprocess_ref(audio, f"{d}/ref.wav")
    sec = wav_seconds(f"{d}/ref.wav")
    log(f"참조 음성 {sec:.1f}초")
    if sec < 5:
        log("⚠ 5초보다 짧아요. 10~20초면 품질이 훨씬 좋아져요.")
    text = (text or "").strip() or transcribe(f"{d}/ref.wav")
    log("대사: " + text)
    json.dump({"text": text}, open(f"{d}/meta.json", "w", encoding="utf-8"), ensure_ascii=False)
    m = (model_fn or get_model)()
    m.add_zero_shot_spk(f"{HEAD}<|endofprompt|>{text}", f"{d}/ref.wav", name)
    m.save_spkinfo()
    log(f"'{name}' 저장 완료.")
    return text


def cmd_add(a):
    try:
        add_voice(a.name, a.audio, a.text)
    except FileNotFoundError as e:
        sys.exit(str(e))
    print(f"이제: say {a.name} \"문장\"  (대사가 틀렸다면 --text \"정확한 대사\" 로 다시 등록)")


def cmd_remove(a):
    d = voice_dir(a.name)
    if not os.path.isdir(d):
        sys.exit("없는 이름이에요.")
    shutil.rmtree(d)
    print(f"'{a.name}' 삭제됨 (캐시된 음색 정보는 다음 등록 때 덮어써져요).")


# ---------- 합성 ----------
_model = None


def find_model_dir():
    """모델은 SD(models/) 또는 modelscope 캐시 어느 쪽에 받아졌든 찾아 쓴다."""
    import glob
    if os.path.exists(f"{MODEL_DIR}/cosyvoice3.yaml"):
        return MODEL_DIR
    hits = glob.glob("/root/.cache/modelscope/hub/**/cosyvoice3.yaml", recursive=True)
    if not hits:
        sys.exit("모델 파일을 못 찾았어요. bash scripts/setup_phone.sh 를 다시 실행해 주세요.")
    print("모델 위치:", os.path.dirname(hits[0]))
    return os.path.dirname(hits[0])


def get_model():
    global _model
    if _model is None:
        sys.path[:0] = [f"{ENGINE}/repo/CosyVoice", f"{ENGINE}/repo/CosyVoice/third_party/Matcha-TTS"]
        import torch
        from cosyvoice.cli.cosyvoice import AutoModel
        _model = AutoModel(model_dir=find_model_dir(), fp16=torch.cuda.is_available())
    return _model


def _trim(wav, sr):
    """문장 앞뒤의 어색한 무음만 잘라낸다 (숨소리가 잘리지 않게 뒤쪽 여유를 둠)."""
    peak = wav.abs().max()
    if peak <= 0:
        return wav
    idx = (wav.abs().max(dim=0).values > 0.02 * peak).nonzero()
    if len(idx) == 0:
        return wav
    start = max(int(idx[0]) - int(0.04 * sr), 0)
    end = min(int(idx[-1]) + int(0.15 * sr), wav.shape[1])
    wav = wav[:, start:end].clone()
    n = int(0.01 * sr)
    ramp = __import__("torch").linspace(0, 1, n)
    wav[:, :n] *= ramp
    wav[:, -n:] *= ramp.flip(0)
    return wav


def synth(model, name, text, emotion="", speed=1.0, pause=1.0, seed=42):
    import torch
    ref, ref_text = load_voice(name)
    if name not in model.frontend.spk2info:
        model.add_zero_shot_spk(f"{HEAD}<|endofprompt|>{ref_text}", ref, name)
    steps = plan(normalize_ko(text, load_dict()), scale=pause)
    instruct = EMOTIONS.get(emotion, emotion)
    sr = model.sample_rate
    pieces = []
    for n, (ch, gap) in enumerate(steps, 1):
        print(f"[{n}/{len(steps)}] {ch}  (쉼 {gap:.2f}s)")
        torch.manual_seed(seed)  # 문장마다 같은 시드 -> 문장 사이 톤/말투가 들쭉날쭉하지 않음
        if instruct:
            # 감정 모드: 저장된 음색 대신 참조 wav + 지시문 사용 (저장된 프롬프트가 지시문을 덮어쓰기 때문)
            gen = model.inference_instruct2(ch, f"{HEAD} {instruct}<|endofprompt|>", ref, speed=speed, text_frontend=False)
        else:
            gen = model.inference_zero_shot(ch, "", ref, zero_shot_spk_id=name, speed=speed, text_frontend=False)
        seg = _trim(torch.cat([o["tts_speech"] for o in gen], dim=1), sr)
        pieces += [seg, torch.zeros(1, int(sr * gap))]
    wav = torch.cat(pieces[:-1], dim=1)
    # 음량 맞추기: RMS -20dBFS 목표, 피크 0.95 이하
    rms = wav.pow(2).mean().sqrt().clamp(min=1e-6)
    wav = wav * (0.1 / rms)
    return wav * min(1.0, 0.95 / wav.abs().max().clamp(min=1e-6))


def save(model, wav, name, out=None, tag=""):
    import torchaudio
    os.makedirs(OUT, exist_ok=True)
    path = out or f"{OUT}/{name}_{time.strftime('%m%d_%H%M%S')}{tag}.wav"
    torchaudio.save(path, wav, model.sample_rate)
    print("저장:", path)
    return path


def cmd_say(a):
    m = get_model()
    for t in range(a.takes):
        seed = a.seed + t
        tag = f"_s{seed}" if a.takes > 1 else ""
        out = a.out if (a.out and a.takes == 1) else None
        save(m, synth(m, a.name, a.text, a.emotion, a.speed, a.pause, seed), a.name, out, tag)


def cmd_talk(a):
    m = get_model()
    cur, emo, speed, seed = (list_voices() or [None])[0], "", 1.0, 42
    print("대화형 모드. 문장을 입력하면 합성해요. (쉼: [pause 1.0], 줄바꿈은 문단 쉼)\n"
          "  /목소리 이름  /감정 기쁨(끄기: /감정 없음)  /속도 1.1  /시드 7(말투 다시 뽑기)  /목록  /끝")
    while True:
        try:
            line = input(f"[{cur} · 감정:{emo or '없음'} · 속도:{speed} · 시드:{seed}] > ").strip()
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
            elif cmd == "시드":
                seed = int(arg or 42)
            else:
                print("모르는 명령이거나 없는 목소리예요. /목록 으로 확인하세요.")
            continue
        if not cur:
            print("먼저 목소리를 등록하세요: voice.py add 이름 파일")
            continue
        save(m, synth(m, cur, line, emo, speed, 1.0, seed), cur)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("add"); x.add_argument("name"); x.add_argument("audio"); x.add_argument("--text")
    s.add_parser("list")
    x = s.add_parser("remove"); x.add_argument("name")
    x = s.add_parser("say"); x.add_argument("name"); x.add_argument("text")
    x.add_argument("--emotion", default=""); x.add_argument("--speed", type=float, default=1.0)
    x.add_argument("--pause", type=float, default=1.0, help="쉬는 시간 배율 (0.7=빠르게, 1.3=여유롭게)")
    x.add_argument("--seed", type=int, default=42, help="말투를 다시 뽑고 싶을 때 바꿔 보세요")
    x.add_argument("--takes", type=int, default=1, help="시드를 바꿔 N개 만들어 골라 듣기")
    x.add_argument("--out")
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
