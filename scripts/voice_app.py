"""한국어 목소리 복제 웹 화면 (폰 브라우저에서 사용). 실행: python voice_app.py"""
import os
import sys
import tempfile

import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice as V  # noqa: E402

NONE = "없음"


def voices():
    return V.list_voices()


def do_say(name, text, emotion, speed, pause, seed, takes):
    if not name:
        raise gr.Error("먼저 '목소리 등록' 탭에서 목소리를 등록하세요.")
    if not (text or "").strip():
        raise gr.Error("말할 문장을 입력하세요.")
    m = V.get_model()
    outs = []
    for t in range(int(takes)):
        wav = V.synth(m, name, text, "" if emotion == NONE else emotion, float(speed), float(pause), int(seed) + t)
        path = V.save(m, wav, name, tag=f"_s{int(seed) + t}")
        outs.append(path)
    outs += [None] * (3 - len(outs))
    return outs


def do_add(name, audio, text):
    name = (name or "").strip()
    if not name:
        raise gr.Error("목소리 이름을 입력하세요.")
    if not audio:
        raise gr.Error("녹음 파일을 올리거나 직접 녹음하세요.")
    logs = []
    try:
        V.add_voice(name, audio, text, log=logs.append)
    except Exception as e:  # 화면에 이유를 보여 준다
        raise gr.Error(str(e))
    return "\n".join(logs), gr.Dropdown(choices=voices(), value=name)


def do_remove(name):
    if not name:
        raise gr.Error("삭제할 목소리를 고르세요.")
    V.cmd_remove(type("A", (), {"name": name}))
    v = voices()
    return f"'{name}' 삭제됨", gr.Dropdown(choices=v, value=(v[0] if v else None))


def build():
    with gr.Blocks(title="목소리 복제") as ui:
        gr.Markdown("# 🎙 한국어 목소리 복제\n본인 또는 동의받은 사람의 목소리만 사용하세요.")
        with gr.Tab("말하기"):
            vs = voices()
            name = gr.Dropdown(vs, value=(vs[0] if vs else None), label="목소리")
            text = gr.Textbox(lines=5, label="말할 문장",
                              placeholder="안녕하세요. [breath] 오늘은 3시 20분에 만나요. [pause 1.0] 알겠죠?")
            gr.Markdown("태그: `[breath]` 숨소리 · `[laughter]` 웃음 · `[cough]` 기침 · `<strong>강조</strong>` · `[pause 1.0]` 쉬기(초)")
            emotion = gr.Dropdown([NONE] + list(V.EMOTIONS), value=NONE, label="감정")
            with gr.Row():
                speed = gr.Slider(0.7, 1.3, value=1.0, step=0.05, label="속도")
                pause = gr.Slider(0.5, 2.0, value=1.0, step=0.1, label="쉬는 시간 배율")
            with gr.Row():
                seed = gr.Number(value=42, precision=0, label="시드 (말투 다시 뽑기)")
                takes = gr.Slider(1, 3, value=1, step=1, label="몇 개 만들어 골라 듣기")
            go = gr.Button("말하게 하기", variant="primary")
            outs = [gr.Audio(label=f"결과 {i + 1}", type="filepath") for i in range(3)]
            go.click(do_say, [name, text, emotion, speed, pause, seed, takes], outs)
        with gr.Tab("목소리 등록"):
            gr.Markdown("조용한 곳에서 **10~20초** 또박또박 말한 녹음을 올리세요. 대사를 비워 두면 자동으로 받아 적습니다.")
            new_name = gr.Textbox(label="이름 (예: 연재)")
            audio = gr.Audio(sources=["upload", "microphone"], type="filepath", label="녹음 파일 / 직접 녹음")
            ref_text = gr.Textbox(label="녹음 속 대사 (선택, 정확히 적으면 더 좋음)")
            add = gr.Button("등록", variant="primary")
            status = gr.Textbox(label="진행 결과", lines=4)
            add.click(do_add, [new_name, audio, ref_text], [status, name])
            with gr.Accordion("목소리 삭제", open=False):
                rm = gr.Button("선택한 목소리 삭제")
                rm.click(do_remove, [name], [status, name])
    return ui


if __name__ == "__main__":
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    build().queue().launch(share=True, server_name="0.0.0.0", show_error=True)
