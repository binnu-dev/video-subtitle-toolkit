---
name: video-subtitle-toolkit
description: >-
  YouTube / X(Twitter) 영상을 다운로드하고, 한국어+영어 이중자막을 생성해 영상에 번인하는 워크플로우.
  Download videos from YouTube / X(Twitter), generate bilingual (Korean + English) subtitles,
  and burn them into the video using yt-dlp, Whisper, and ffmpeg.
  "유튜브 자막 넣어줘", "이중자막 만들어줘", "bilingual subtitles", "영상 다운로드",
  "X 영상 저장", "Whisper 전사", "자막 번인", "subtitle burn-in",
  "VTT 자막 추출", "SRT to ASS" 등의 요청에 활성화됩니다.
skill-type: encoded-preference
argument-hint: [YouTube/X URL 또는 작업 설명]
---

# 🎬 Video Subtitle Toolkit

YouTube, X(Twitter) 등의 영상을 다운로드하고, 한국어/영어 이중자막을 생성해 영상에 합성하는 종합 워크플로우입니다.

---

## 📋 전제 조건 (Prerequisites)

```bash
# Python 패키지
pip install yt-dlp openai-whisper

# Node.js (X 영상 캡처 시)
npm install  # ws 패키지

# ffmpeg (libass 포함 빌드)
winget install Gyan.FFmpeg   # Windows
brew install ffmpeg          # macOS

# 폰트: Noto Sans KR (https://fonts.google.com/noto/specimen/Noto+Sans+KR)
```

---

## 워크플로우 A: YouTube 영상 (자막 있음) — 6단계

### Step 1: 영상 다운로드

```powershell
yt-dlp -f "bestvideo[height<=1080]+bestaudio" -o "output.mp4" "YOUTUBE_URL"
```

클립이 필요하면 전체 영상 다운 후 ffmpeg로 자르기:
```powershell
ffmpeg -y -ss HH:MM:SS -to HH:MM:SS -i full.mp4 -c copy clip.mp4
```

### Step 2: 영어 자막(VTT) 다운로드

```powershell
yt-dlp --write-auto-sub --sub-lang en --skip-download `
  --extractor-args "youtube:player_client=ios,web" `
  -o "subs" "YOUTUBE_URL"
# 결과: subs.en.vtt
```

> `--extractor-args "youtube:player_client=ios,web"` — 자막 다운로드 시 iOS/web 클라이언트를 지정해야 성공률이 높습니다.

### Step 3: VTT → 문장 단위 타임스탬프 추출

```powershell
python scripts/extract_by_sentence.py --vtt subs.en.vtt --start 0 --end 99999 --output sentence_cues.json
```

- YouTube VTT의 `<c>` 태그에서 단어별 타임스탬프를 파싱, `.!?` 경계에서 문장 단위로 분할
- 결과: `sentence_cues.json` — `[{"start": 0.2, "end": 3.5, "text": "..."}, ...]`
- 목표: **문장당 3~7초** (10초 이상이면 수동 분할 권장)

### Step 4: 한국어 번역 + 이중자막 SRT 생성

`sentence_cues.json`을 읽고, 각 문장을 한국어로 번역하여 이중자막 SRT를 작성합니다.  
LLM(ChatGPT, Copilot 등)에 번역을 요청하거나 수동으로 작성하세요.

**SRT 형식** (한 블록 = 영어 + 한국어):
```
1
00:00:00,200 --> 00:00:03,500
This is the English subtitle line.
이것은 한국어 자막 줄입니다.
```

**번역 규칙**:
- 의역 > 직역 — 자연스러운 한국어 우선
- 한 줄이 30자를 넘으면 `\n`으로 분리 (최대 2줄)

### Step 5: SRT → ASS 변환 (이중 스타일)

```powershell
python scripts/gen_ass.py --srt input.srt --ass output.ass
# 기본 해상도: 1280x720. 다른 해상도는 --res 1920x1080 지정
```

#### 🎨 ASS 스타일 (v6 — 최종 승인)

| 속성 | 한국어 (상단) | 영어 (하단) |
|------|-------------|------------|
| **폰트** | Noto Sans KR Medium | Noto Sans KR DemiLight |
| **크기** | 39pt | 27pt |
| **Bold** | Yes | No |
| **글자색** | `&H00FFFFFF` (흰색) | `&H20FFFFFF` (약간 투명) |
| **배경** | 검정 박스 (`BorderStyle=3`) | 동일 |
| **MarginV** | 90 (위쪽) | 14 (아래쪽) |
| **Alignment** | 2 (하단 중앙) | 2 (하단 중앙) |
| **PlayRes** | 1280×720 | — |

### Step 6: ffmpeg로 ASS 번인

```powershell
# ⚠️ 경로에 공백/특수문자가 있으면 임시 폴더로 복사 후 실행
$tmp = "$env:TEMP\subs_burn"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
Copy-Item output.mp4 "$tmp\input.mp4"
Copy-Item output.ass "$tmp\input.ass"

Push-Location $tmp
ffmpeg -y -i input.mp4 -vf "ass=input.ass" -c:a copy output.mp4
Pop-Location

Copy-Item "$tmp\output.mp4" "final_with_subs.mp4"
```

---

## 워크플로우 B: X(Twitter) 등 자막 없는 영상 — CDP + Whisper

### Step B1: X(Twitter) 영상 다운로드 (CDP 방식)

X(Twitter)는 HLS(m3u8) 스트리밍으로 영상을 제공합니다. yt-dlp가 막힌 환경에서는 **CDP 네트워크 캡처** 방식을 사용합니다.

**전제 조건**:
- Edge 또는 Chrome을 디버그 모드로 실행:
  ```powershell
  # Edge
  Start-Process "msedge.exe" "--remote-debugging-port=9222 --user-data-dir=$env:TEMP\cdp-profile"
  # Chrome
  Start-Process "chrome.exe" "--remote-debugging-port=9222 --user-data-dir=$env:TEMP\cdp-profile"
  ```
- 브라우저에서 해당 X 트윗 페이지를 열어둔 상태

```powershell
# CDP로 비디오 URL 캡처 (트윗 ID 또는 URL 일부 지정)
node scripts/capture_video_url.js "TWEET_ID_OR_URL_SUBSTRING" 20

# 출력된 마스터 m3u8 URL로 다운로드
ffmpeg -y -i "MASTER_M3U8_URL" -c copy output.mp4
```

**yt-dlp를 쓸 수 있는 환경에서는** 더 간단:
```powershell
yt-dlp -f best -o "output.mp4" "https://x.com/USER/status/TWEET_ID"
```

### Step B2: 오디오 추출 + Whisper 전사

```powershell
# 오디오 추출 (Whisper 최적 포맷: 16kHz mono WAV)
ffmpeg -y -i output.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
```

```python
import whisper, json

model = whisper.load_model('base')  # tiny/base/small/medium/large
result = model.transcribe('audio.wav', language='en')
# language: en(영어), ko(한국어), ja(일본어), zh(중국어) 등

segments = [
    {'start': round(s['start'], 2), 'end': round(s['end'], 2), 'text': s['text'].strip()}
    for s in result['segments']
]

with open('whisper_output.json', 'w', encoding='utf-8') as f:
    json.dump(segments, f, ensure_ascii=False, indent=2)

print(f'Done! {len(segments)} segments')
```

| 모델 | 크기 | CPU 속도 | 정확도 |
|------|------|---------|--------|
| `tiny` | 39MB | 매우 빠름 | 낮음 |
| `base` | 139MB | 빠름 | 보통 ← **기본 권장** |
| `small` | 461MB | 보통 | 좋음 |
| `medium` | 1.5GB | 느림 | 높음 |

> Whisper 설치: `pip install openai-whisper`  
> GPU 없는 CPU 환경에서는 `base` 모델 권장

### Step B3: 번역 + 이중자막 SRT 생성

`whisper_output.json`을 읽어 원문을 교정하고, 한국어/영어로 번역하여 SRT를 작성합니다.

**SRT 형식** (원문 언어에 따라 영어/한국어 배치 결정):
```
1
00:00:00,000 --> 00:00:03,600
예를 들어, 천리 길도 한 걸음부터잖아요
For example, a thousand-mile journey starts with a single step
```

### Step B4~B5: ASS 변환 + ffmpeg 번인

워크플로우 A의 **Step 5~6과 동일**:

```powershell
python scripts/gen_ass.py --srt input.srt --ass output.ass

$tmp = "$env:TEMP\subs_burn"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
Copy-Item video.mp4 "$tmp\input.mp4"
Copy-Item output.ass "$tmp\input.ass"
Push-Location $tmp
ffmpeg -y -i input.mp4 -vf "ass=input.ass" -c:a copy output.mp4
Pop-Location
Copy-Item "$tmp\output.mp4" "final_with_subs.mp4"
```

---

## 출력 파일

| 파일 | 설명 |
|------|------|
| `sentence_cues.json` | 문장 단위 타임스탬프 (중간 산출물) |
| `*.srt` | 이중자막 SRT (중간 산출물) |
| `*.ass` | 이중 스타일 ASS (중간 산출물) |
| `final_with_subs.mp4` | 자막 번인된 최종 영상 |

---

## 트러블슈팅

| 문제 | 원인 | 해결 |
|------|------|------|
| yt-dlp 403 에러 | 구버전 yt-dlp | `pip install -U yt-dlp` |
| VTT 다운로드 실패 | 기본 클라이언트 제한 | `--extractor-args "youtube:player_client=ios,web"` 추가 |
| ffmpeg `ass=` 필터 에러 | 경로에 공백/특수문자 | `$env:TEMP\subs_burn`으로 복사 후 실행 |
| 자막 싱크 어긋남 | VTT 롤링 윈도우 중복 | `extract_by_sentence.py`의 "마지막 줄만" 파싱으로 해결됨 |
| 자막이 너무 길게 표시 | 문장이 10초 이상 | `sentence_cues.json`에서 수동 분할 (목표: 3~7초) |
| 폰트 없음 | Noto Sans KR 미설치 | [Google Fonts](https://fonts.google.com/noto/specimen/Noto+Sans+KR) 설치 |
| CDP 연결 실패 | 디버그 모드 미실행 | `--remote-debugging-port=9222` 옵션으로 브라우저 실행 |
| Whisper FP16 경고 | GPU 없는 환경 | 무시해도 됨 (자동으로 FP32 사용) |
| Whisper 전사 부정확 | base 모델 한계 | 문맥 기반 수동 교정 또는 `small`/`medium` 모델 사용 |
