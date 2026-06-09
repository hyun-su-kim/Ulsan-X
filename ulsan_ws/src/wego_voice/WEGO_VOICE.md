# wego_voice — 음성 파이프라인 패키지

## 개요

LIMO 안내 로봇의 음성 처리 패키지. 마이크 입력부터 목적지 발행까지 전 과정을 담당한다.

**입력**: 마이크 (상시)
**출력**: `/goal_destination` 토픽 → `wego_behaviour`가 받아서 로봇 출발

---

## 전체 파이프라인

```
마이크
 ↓ 20ms 단위로 캡처 (pyaudio)
VAD        ← 사람 목소리? No → 버림        (webrtcvad, CPU)
 ↓
on_duty    ← 이 로봇 담당? No → 버림        (ROS /on_duty 토픽)
 ↓
Wake Word  ← "hey jarvis"? No → 버림       (openWakeWord, CPU)
 ↓
TTS        ← "어디로 안내해드릴까요?" 출력   (edge-tts)
 ↓ 큐 flush (TTS 에코 제거)
발화 수집   ← 침묵 1.5s or 최대 10s
 ↓
STT        ← 음성 → 텍스트                 (faster-whisper, GPU)
 ↓
NLU        ← 텍스트 → 목적지 키            (키워드 매핑 → Gemini fallback)
 ↓
TTS        ← "{목적지}로 안내해드릴게요." 출력
 ↓
/goal_destination 발행 → wego_behaviour
```

---

## 설계 결정 및 근거

### VAD: webrtcvad 선택 (Silero VAD 아님)

초기 설계에서는 Silero VAD를 사용하려 했으나 Jetson 환경에서 torchaudio 의존성 충돌이 발생했다.

- Silero VAD는 내부적으로 `torchaudio`를 사용
- 로봇 PC의 conda 환경(dl_env)에 설치된 torchaudio가 시스템 torch(2.8.0)와 버전 불일치
- venv로 격리해도 `PYTHONPATH`에 conda 경로가 선행 등록되어 우선 적용됨

**webrtcvad 선택 이유**:
- Google이 Chrome에서 사용하는 WebRTC VAD — production 검증됨
- torch / torchaudio 의존성 없음 (순수 C 구현)
- 파이프라인에서 VAD의 역할은 침묵/소음을 걸러주는 문지기이므로 webrtcvad의 정확도로 충분
- `pip install webrtcvad` 한 줄로 설치 완료

### Wake Word: openWakeWord + hey_jarvis (확정)

**"헤이 리모" 커스텀 wake word 검토 후 hey_jarvis 유지로 확정.**

검토한 대안:
- **Porcupine (Picovoice)**: 커스텀 wake word를 계정 없이 생성 가능하나 회사 이메일만 가입 허용 → 사용 불가
- **openWakeWord 커스텀 학습**: TTS 샘플 생성 + 모델 학습으로 계정 불필요하나, 학습 파이프라인 세팅 비용 대비 포트폴리오 기여도가 낮음

**hey_jarvis 유지 근거**:
- 파이프라인에서 wake word는 입력 트리거 역할. 핵심 기술은 STT → NLU → 목적지 추출 → 로봇 제어 흐름임
- "헤이 자비스"로 호출하면 동작에 문제 없음
- 교체 설계는 완료: `voice_params.yaml`의 `wakeword_model`만 바꾸면 다른 모델로 즉시 전환 가능

### STT: faster-whisper (ctranslate2 직접 빌드)

- PyPI의 faster-whisper는 x86 전용 — Jetson(ARM)에서 pip install 불가
- CTranslate2를 `-DWITH_CUDA=ON -DCUDA_ARCH_LIST="Auto"`로 직접 빌드 후 설치
- `compute_type="int8_float16"`: Orin Nano에서 float16보다 속도·메모리 효율 좋음
- `beam_size=1`: greedy decoding으로 추론 속도 우선
- `language="ko"` 명시로 언어 감지 생략

### TTS: edge-tts (Microsoft Neural)

한국어 음성 응답을 위해 edge-tts 선택.

| 라이브러리 | 한국어 품질 | 설치 | 인터넷 |
|-----------|------------|------|--------|
| **edge-tts** | ★★★ (Microsoft Neural) | pip 한 줄 | 필요 |
| gTTS | ★★ | pip 한 줄 | 필요 |
| Piper | ★ (한국어 공식 모델 없음) | ONNX 모델 별도 | 불필요 |

**edge-tts 선택 이유**:
- Microsoft Neural TTS — 자연스러운 한국어 억양
- 순수 Python (asyncio 기반) — ARM 호환 문제 없음
- 이미 Gemini API를 사용하므로 인터넷 의존성 추가가 문제 없음
- voice: `ko-KR-SunHiNeural` (여성), yaml에서 교체 가능

**TTS가 블로킹인 이유**:
`speak()`가 재생 완료까지 블로킹됨 → 로봇이 말하는 중에 마이크가 TTS 음성을 다시 줍는 피드백 루프 방지.
재생 완료 후 `audio.flush()`로 큐에 남은 에코 오디오를 제거하고 발화 수집을 시작한다.

### NLU: 키워드 매핑 + Gemini API fallback

1차: 키워드 매핑 — 목적지가 고정된 학원 환경에서 빠르고 오프라인으로 동작.
2차: Gemini API fallback — "강의실 첫 번째"처럼 키워드 매핑이 실패하는 모호한 발화 처리.

키워드를 길이 내림차순으로 정렬해 순회:
"상담실2"가 "상담실"보다 먼저 비교되어 오매핑 방지.

Gemini 응답은 실제 waypoints 키인지 검증 후 사용 — 존재하지 않는 목적지로 이동 방지.

### waypoints.yaml 참조 방식

NLU가 목적지 키의 유효성을 검사하기 위해 `wego_behaviour` 패키지의 `waypoints.yaml`을 참조한다.
`get_package_share_directory('wego_behaviour')`로 경로를 동적으로 가져오므로 경로 하드코딩 없음.
두 패키지가 같은 workspace(ulsan_ws)에서 빌드되면 자동으로 동작한다.

---

## 파일별 역할

### `audio_stream.py`

마이크에서 소리를 20ms 단위로 잘라 queue에 넣는다.

- `pyaudio`로 마이크 스트림 열기 (16kHz, 모노, int16)
- 별도 스레드(pyaudio 내부 콜백)로 계속 캡처
- `read(timeout)`: pipeline 스레드에서 프레임 꺼낼 때 사용
- `flush()`: TTS 재생 중 쌓인 에코 오디오를 큐에서 전부 제거

```
마이크 → pyaudio 콜백 → queue[bytes] → pipeline 스레드
```

주요 상수:
- `SAMPLE_RATE = 16000`
- `CHUNK_MS = 20` → `CHUNK_SAMPLES = 320`

---

### `vad.py`

20ms 프레임이 사람 목소리인지 판단한다.

- `webrtcvad.Vad(aggressiveness)`: 민감도 0~3
- `is_speech(frame, sample_rate)` → bool 반환
- 목소리 아니면 이후 단계 실행하지 않음

aggressiveness 가이드:
- 0: 조용한 실내 환경
- 2: 일반 사무/학원 환경 (기본값)
- 3: 시끄러운 환경 (오감지 위험)

---

### `wakeword.py`

VAD를 통과한 오디오에서 "hey jarvis"를 감지한다.

openWakeWord는 80ms(1280 sample) 단위로 처리한다. 20ms 프레임을 4개 누적해서 넘기는 버퍼 로직이 내부에 있다.

감지 점수가 `threshold` 이상이면 True 반환 → TTS 안내 후 발화 수집 시작.

교체 방법: `voice_params.yaml`의 `wakeword_model` 값만 변경.

---

### `stt.py`

수집된 발화 bytes 리스트를 한국어 텍스트로 변환한다.

- bytes 리스트 → `b"".join()` → int16 numpy → float32 (÷32768) → Whisper
- `language="ko"`, `beam_size=1` (속도 우선)
- CUDA + `int8_float16` 사용

---

### `tts.py`

edge-tts로 한국어 음성 출력.

- `TTS(voice)`: Microsoft Neural TTS 래퍼
- `speak(text)`: 동기 인터페이스 — 내부적으로 `asyncio.run()`으로 비동기 처리
- 동작 순서: edge-tts API → 임시 MP3 저장 → `mpg123 -q` 재생 → 임시 파일 삭제
- 예외 발생 시 조용히 무시 (파이프라인 중단 없음)

호출 위치 (voice_node.py):
1. 웨이크워드 감지 직후 → "어디로 안내해드릴까요?"
2. 목적지 확정 후 → "{label}로 안내해드릴게요."
3. 목적지 매핑 실패 시 → "죄송합니다, 다시 말씀해 주시겠어요?"

---

### `nlu.py`

STT 텍스트에서 목적지 waypoint 키를 추출한다.

- `KEYWORD_MAP`: 키워드 → waypoint 키 사전 (길이 내림차순 정렬로 오매핑 방지)
- `extract_destination(text, waypoints)`: 1차 키워드 매핑 → 2차 Gemini fallback
- `load_waypoints()`: wego_behaviour의 waypoints.yaml 로드
- `_call_gemini()`: Gemini 1.5 Flash에 목적지 목록 + 발화 전달 → 키 반환

현재 지원 목적지:
`classroom_1~5`, `counseling_1~2`, `intensive_counseling_1~2`,
`counter`, `multi`, `vice_principal`

---

### `voice_node.py`

위 모듈들을 ROS2 노드로 연결하는 메인 파일.

**구독**:
- `/on_duty` (`std_msgs/Bool`): False면 웨이크워드 단계에서 차단

**발행**:
- `/goal_destination` (`std_msgs/String`): waypoint 키 문자열

파이프라인은 별도 스레드(`_run`)로 실행되고, `rclpy.spin()`은 메인 스레드에서 콜백만 처리한다.

---

## 설치 방법 (로봇 PC)

### 사전 조건

- JetPack R36 (Ubuntu 22.04, CUDA 12.6)
- PyTorch 2.8.0 + CUDA 확인: `python3 -c "import torch; print(torch.cuda.is_available())"`
- 가상환경: `~/Ulsan-X/wego_venv` (--system-site-packages)

### 패키지 설치

```bash
# 1. apt
sudo apt install -y portaudio19-dev libsndfile1 cmake ninja-build mpg123

# 2. activate_voice.sh 실행 (PYTHONPATH + API 키 설정)
source ~/Ulsan-X/activate_voice.sh

# 3. pip 패키지
pip install pyaudio webrtcvad openwakeword edge-tts google-generativeai

# 4. ctranslate2 빌드 (30~60분) — PyPI 버전은 x86 전용이라 ARM에서 직접 빌드 필요
# ~/CTranslate2 에 이미 클론됨 (2026-05-07 완료)
git clone --recursive https://github.com/OpenNMT/CTranslate2  # 이미 있으면 생략
cd CTranslate2 && mkdir -p build && cd build
cmake .. -DWITH_CUDA=ON -DCUDA_ARCH_LIST="Auto" -DWITH_MKL=OFF -DCMAKE_BUILD_TYPE=Release -GNinja
ninja -j$(nproc)
sudo ninja install  # 헤더·so를 /usr/local/에 설치 — python 빌드가 헤더를 찾기 위해 필요
cd ~/CTranslate2/python && pip install .

# 5. numpy 다운그레이드 (필수) — tflite_runtime이 numpy 2.x와 호환 안 됨
pip install "numpy<2"

# 6. faster-whisper
pip install faster-whisper

# 7. openWakeWord 모델 다운로드 (최초 1회)
python3 -c "from openwakeword.utils import download_models; download_models()"
```

### 설치 확인

```bash
python3 -c "import webrtcvad; print('webrtcvad OK')"
python3 -c "import openwakeword; print('openwakeword OK')"
python3 -c "import faster_whisper; print('faster_whisper OK')"
python3 -c "import pyaudio; print('pyaudio OK')"
python3 -c "import edge_tts; print('edge_tts OK')"
python3 -c "import google.generativeai; print('google-generativeai OK')"
python3 -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

### Gemini API 키 등록

```bash
# ~/.ros_env.sh에 추가
echo "export GEMINI_API_KEY=your_api_key_here" >> ~/.ros_env.sh
```

### 빌드

```bash
cd ~/Ulsan-X/ulsan_ws

# wego_behaviour 먼저 빌드 (wego_voice가 waypoints.yaml 참조)
colcon build --packages-select wego_behaviour
colcon build --packages-select wego_voice
source install/setup.bash
```

---

## 실행

**로봇에서 실행** (스피커가 로봇에 있으므로 — domain 6/7). 사전 오디오 설정 불요:

```bash
export ROS_DOMAIN_ID=6        # LIMO 2는 7
source /opt/ros/humble/setup.bash
source ~/Ulsan-X/ulsan_ws/install/setup.bash
ros2 run wego_voice voice_node
```

> **오디오 출력**: `mpg123 -o pulse` + `PULSE_SINK`(`voice_params.yaml`의 `pulse_sink`)로 특정 싱크에 직접 출력 → 부팅마다 `pactl set-default-sink` 하던 수동 설정 제거.
> **싱크 확인**: `pactl list short sinks`로 이름 확인(기본 `alsa_output.platform-3510000.hda.hdmi-stereo` = 빌트인 디스플레이 HDMI). 다르면 `pulse_sink` 값 교체.
> **전제**: PulseAudio가 도는 사용자 세션에서 실행(로봇 데스크톱 세션 / `XDG_RUNTIME_DIR` 잡힌 SSH). `ros2 launch wego_voice voice_launch.py`로 띄우면 `voice_params.yaml`을 읽는다.

---

## 테스트 방법

### 전체 파이프라인 테스트

터미널 1 — 노드 실행:
```bash
source ~/Ulsan-X/activate_voice.sh
source ~/Ulsan-X/ulsan_ws/install/setup.bash
ros2 launch wego_voice voice_launch.py
```

터미널 2 — 토픽 모니터링:
```bash
source ~/Ulsan-X/ulsan_ws/install/setup.bash
ros2 topic echo /goal_destination
```

테스트 순서:
1. "hey jarvis" 발화 → 로그: "웨이크워드 감지" → TTS: "어디로 안내해드릴까요?"
2. "1강의실" 발화 → TTS: "1강의실로 안내해드릴게요." → `/goal_destination`에 `classroom_1` 수신 확인

### 컴포넌트 단위 테스트 (ROS2 없이)

```bash
# TTS 확인
python3 -c "from wego_voice.tts import TTS; TTS().speak('테스트입니다.')"

# NLU 확인
python3 -c "from wego_voice.nlu import extract_destination; print(extract_destination('1강의실 가고 싶어요'))"
```

---

## 동작 흐름 시나리오

노드 시작 후 사람이 로봇 앞에 섰을 때의 단계별 흐름.

```
1. 노드 시작
   → 모델 로딩 (faster-whisper 첫 실행 시 ~244MB 자동 다운로드)
   → 마이크 상시 감지 시작

2. 사람이 로봇 앞에서 말함
   → VAD: 목소리 감지 → 통과
   → on_duty: True 확인 → 통과
   → "hey jarvis" 발화
   → openWakeWord 감지 점수 0.5 초과 → 웨이크워드 감지

3. TTS 안내
   → "어디로 안내해드릴까요?" 출력
   → 재생 완료 후 오디오 큐 flush (에코 제거)

4. 발화 수집
   → 웨이크워드 직후 0.3초 버림
   → 사람: "1강의실 가고 싶어요"
   → 침묵 1.5초 지속 → 수집 종료

5. STT 실행
   → faster-whisper (CUDA) → "1강의실 가고 싶어요"

6. NLU 실행
   → "1강의실" 키워드 매칭 → classroom_1
   → wego_behaviour waypoints.yaml에 classroom_1 존재 확인

7. TTS 확정 안내 + /goal_destination 발행
   → "1강의실로 안내해드릴게요." 출력
   → wego_behaviour IdleState 수신
   → 로봇 1강의실로 출발
```

---

## 알려진 제한 및 향후 작업

| 항목 | 현재 | 향후 |
|------|------|------|
| Wake word | hey_jarvis (영어, 확정) | 커스텀 모델 필요 시 voice_params.yaml wakeword_model만 교체 |
| NLU | 키워드 매핑 + Gemini fallback | — |
| TTS | edge-tts (ko-KR-SunHiNeural) | Piper 로컬 TTS (오프라인 환경 대비) |
| YOLO 연동 | 미구현 | 사람 감지 시 안내 멘트 트리거 |

## 버그 및 미해결 문제 (2026-05-07)

### [BUG] VAD가 wakeword 감지를 간헐적으로 방해
- **증상**: "hey jarvis" 발화해도 웨이크워드 감지가 불안정함. threshold 0.1, VAD 0으로 낮춰도 재현됨.
- **원인**: VAD가 프레임 단위로 음성을 차단 → "hey jarvis"의 일부 프레임이 잘려 openWakeWord가 전체 단어를 못 봄.
- **해결 방향**: `voice_node.py`의 `_run()`에서 VAD 체크를 wakeword 감지 루프 밖으로 분리. wakeword 단계는 모든 프레임을 통과시키고, VAD는 발화 수집 단계에서만 사용.
- **상태**: 미수정

### [BUG] NLU 실패 후 TTS 재생 시 audio.flush() 누락
- **증상**: "죄송합니다, 다시 말씀해 주시겠어요?" TTS 재생 후 에코 오디오가 큐에 남음.
- **위치**: `voice_node.py` NLU 실패 분기 — `tts.speak(...)` 직후 `self._audio.flush()` 호출 필요.
- **상태**: 미수정

---

## 연동 구조

```
wego_coordinator  →  /on_duty        →  wego_voice  →  /goal_destination  →  wego_behaviour
```

`wego_coordinator`(노트북)가 어느 로봇이 응대 담당인지 결정하고,
`wego_voice`는 담당일 때만 웨이크워드를 처리해 불필요한 GPU 소모와 동시 응대를 방지한다.
