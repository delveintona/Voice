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

## 자연스럽게 읽히도록 하는 처리
- **숫자**: 한국어식으로 읽음
  - 2025년 3월 → 이천이십오 년 삼 월, 3시 5분 → 세 시 오 분, 6월/10월 → 유월/시월
  - 개수는 고유어: 3명 → 세 명, 20살 → 스무 살, 12개 → 열두 개
  - 전화번호는 숫자별로 끊어 읽기(010-1234-5678), 12,000원 → 만이천원, 3.5% → 삼 점 오 퍼센트
- **쉬는 시간(타이밍)**: 문장부호로 자동 결정
  - 마침표·느낌표 약 0.4초, 물음표 0.45초, 말줄임표(…) 0.7초, 쉼표 0.2초, 줄바꿈(문단) 0.8초
  - 직접 정하려면 문장 사이에 `[pause 1.5]` (초 단위)
  - 전체를 더 빠르게/느긋하게: `--pause 0.7` / `--pause 1.3`
- **띄어 말하기**: 너무 짧은 문장은 다음 문장과 붙여 읽고, 긴 문장은 쉼표 위치에서 나눔
- **톤 일관성**: 문장마다 같은 시드를 써서 말투가 들쭉날쭉하지 않음. 마음에 안 들면 `--seed 7`로 다시 뽑거나 `--takes 3`으로 3개를 만들어 골라 듣기
- **발음 사전**: SD의 `voice/dict.txt`에 `GPT=지피티` 처럼 적어 두면 항상 그렇게 읽음
- **그 외**: ㅋㅋ/ㅎㅎ → 웃음 소리, 이모지·`~` 제거, 문장 앞뒤 무음 정리, 음량 통일

예)
```
bash scripts/run_phone.sh say 민수 "3시 20분에 5명이 와요. [pause 1.0] 전화는 010-1234-5678로 주세요… 알겠죠?" --takes 3
```

## 한계 (솔직히)
- CPU 추론이라 문장당 수 분이 걸릴 수 있고 RAM 6GB 이상 권장. 폰에서 PyTorch 설치가 실패할 수 있음(미검증).
- 이 스크립트들은 클라우드 환경에서 작성되어 **실제 폰에서는 아직 실행해 보지 못함**.
- 본인 또는 동의받은 사람의 목소리만 복제하세요.
