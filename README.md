# Voice – 폰 로컬 한국어 목소리 복제

- 엔진: [FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice) · Fun-CosyVoice3-0.5B (Apache-2.0)
- 한국어, 제로샷 음성 복제(10~30초 샘플), 감정 instruct, `[breath]` `[laughter]` `[cough]` `<strong>` 태그
- 모든 추론은 폰 안에서(CPU) 실행. 인터넷은 설치/모델 다운로드 때만 필요.

## 설치 (폰의 Termux에서, F-Droid 버전 권장)
```
pkg install -y git
git clone <이 저장소> && cd Voice/scripts
termux-setup-storage          # 권한 허용
bash setup_phone.sh           # SD카드 자동 탐색, 또는 bash setup_phone.sh /storage/XXXX-XXXX
```
- 모델·레포·샘플·결과물 → SD카드(`.../voice`), 파이썬 환경 → 내부 저장소(proot Ubuntu, 약 3~4GB)
- SD 여유 약 5GB 이상 필요.

## 사용
1. 내 목소리 10~30초 wav를 SD의 `voice/samples/ref.wav` 로 복사
2. `bash run_phone.sh "안녕하세요. [breath] 오늘은 정말 기뻐요! [laughter]"`
3. 감정 지시: `EMOTION="슬프고 떨리는 목소리로 말해 주세요." bash run_phone.sh "보고 싶었어요. [breath]"`
4. 결과: SD의 `voice/outputs/out_0.wav`

## 한계 (솔직히)
- CPU 추론이라 문장당 수 분이 걸릴 수 있고 RAM 6GB 이상 권장. 폰에서 PyTorch 설치가 실패할 수 있음(미검증).
- 이 스크립트들은 클라우드 환경에서 작성되어 **실제 폰에서는 아직 실행해 보지 못함**.
- 본인 또는 동의받은 사람의 목소리만 복제하세요.
