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
녹음 파일(m4a/mp3/wav, 10~20초)을 SD의 `voice/samples/` 폴더에 넣은 뒤 (Voice 폴더에서 실행):

```
bash scripts/run_phone.sh add 민수 minsu.m4a          # 목소리 등록 (이름은 마음대로)
bash scripts/run_phone.sh add 엄마 mom.wav
bash scripts/run_phone.sh list                         # 등록된 목소리 보기
bash scripts/run_phone.sh say 민수 "안녕하세요. [breath] 반가워요."
bash scripts/run_phone.sh say 엄마 "보고 싶었어요." --emotion 슬픔
bash scripts/run_phone.sh talk                         # 모델을 한 번만 켜고 계속 입력
bash scripts/run_phone.sh remove 민수
```
결과는 SD의 `voice/outputs/이름_날짜시간.wav`.

- 한 번 등록한 목소리는 SD에 저장되어 계속 쓸 수 있고, 몇 명이든 등록 가능합니다.
- `talk` 모드: `/목소리 엄마`, `/감정 기쁨`, `/속도 1.1`, `/목록`, `/끝`
- 문장 태그: `[breath]` 숨소리, `[laughter]` 웃음, `[cough]` 기침, `<strong>강조</strong>`
- 감정 프리셋: 기쁨 슬픔 화남 작게 크게 느리게 빠르게 (공식 예제에서 검증된 지시문 사용)
- `--speed 0.9`, `--pause 0.5`(문장 사이 쉬는 시간)

## 품질을 높이는 처리
- 등록 시: 잡음 감소, 앞뒤·긴 무음 제거, 음량 정규화, 24kHz 변환, 20초로 제한
- 녹음 속 대사를 Whisper로 자동 받아 적어 음색 복제에 사용 (틀리면 `--text "정확한 대사"`로 다시 등록)
- 합성 시: 숫자를 한글로 읽기(2025 → 이천이십오), 문장 단위 분할·이어 붙이기, 음량 정규화
- 좋은 녹음: 조용한 방, 입에서 한 뼘 거리, 감정 없이 또박또박, 중간에 쉬지 않기

## 한계 (솔직히)
- CPU 추론이라 문장당 수 분이 걸릴 수 있고 RAM 6GB 이상 권장. 폰에서 PyTorch 설치가 실패할 수 있음(미검증).
- 이 스크립트들은 클라우드 환경에서 작성되어 **실제 폰에서는 아직 실행해 보지 못함**.
- 본인 또는 동의받은 사람의 목소리만 복제하세요.
