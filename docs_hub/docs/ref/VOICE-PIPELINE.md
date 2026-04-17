# VOICE-PIPELINE — 음성 처리 파이프라인

## 설계 철학
자원 관리 우선. 상위 레벨이 통과시켜야만 하위 레벨이 활성화됨.
항상 켜두는 건 VAD뿐. Whisper는 호출어 감지 후에만 깨어남.

---

## 파이프라인 6단계

```
마이크 (상시)
  │
  ▼ Level 1: VAD ──────────── 사람 목소리 아니면 차단
  │ Silero VAD
  │ CPU 경량, 상시 가동
  │
  ▼ Level 2: Wake-up ──────── "헤이 리모" 아니면 차단
  │ openWakeWord
  │ 커스텀 모델 필요 여부: 미결정 → DECISION-LOG DEC-001
  │
  ▼ Level 3: STT ──────────── 발화 텍스트 변환
  │ faster-whisper (small 모델)
  │ Orin Nano GPU (CUDA) 가속
  │ 호출어 감지 시에만 활성화
  │
  ▼ Level 4: NLU (Main) ───── 의도 해석
  │ ① If-else: "N강의실이 어디야?" 등 패턴 명확한 명령
  │ ② Gemini API: 모호한 문장, 복합 의도
  │ 네트워크 필요
  │
  ▼ Level 5: NLU (Backup) ─── 네트워크 단절 시 폴백
  │ Gemma-2B (Ollama, 로컬)
  │ Orin Nano에서 추론 — 성능 제약 있음
  │
  ▼ Level 6: TTS ──────────── 음성 응답 출력
    Piper (ONNX, 로컬)
    지연 최소화 목적, 오프라인 동작
```

---

## 단계별 상세

### Level 1: VAD (Silero VAD)
- **역할**: 소음과 사람 목소리 구분. CPU 낭비 방지용 문지기.
- **가동 조건**: 상시
- **출력**: `Bool` — 사람 목소리 감지 여부
- **리소스**: CPU only, 경량

### Level 2: Wake-up Word (openWakeWord)
- **역할**: "헤이 리모" 호출어 감지
- **가동 조건**: VAD가 사람 목소리 감지 시
- **출력**: `Bool` — 호출어 감지 여부
- **리소스**: CPU, 경량
- **미결 사항**: "헤이 리모" 커스텀 모델 필요 여부 (→ DEC-001)

### Level 3: STT (faster-whisper)
- **모델**: small (속도/정확도 균형)
- **가속**: CUDA (Orin Nano 내장 GPU)
- **가동 조건**: 호출어 감지 후 즉시 활성화
- **출력**: `String` — 발화 텍스트
- **리소스**: GPU — YOLO와 동시 가동 시 메모리 검토 필요 (→ DEC-002)

### Level 4: NLU (Main)
- **If-else 처리 예시**:
  - "1강의실 어디야" → 목적지: `room_1`
  - "상담실 가고 싶어" → 목적지: `counseling_room`
  - "화장실" → 목적지: `restroom`
- **Gemini API 처리**: 패턴 매칭 실패 시 클라우드 LLM으로 의도 파악
- **출력**: `wego_msgs/Intent` — `{ intent_type, destination, raw_text }`

### Level 5: NLU Backup (Gemma-2B / Ollama)
- **가동 조건**: Gemini API 타임아웃 or 네트워크 단절
- **성능 제약**: Orin Nano에서 추론 속도 느림 → 단순 의도만 처리
- **리소스**: CPU + GPU 혼용

### Level 6: TTS (Piper)
- **형식**: ONNX 모델, 완전 로컬 동작
- **지연 목표**: < 300ms (목표값, 검증 필요)
- **음성**: 한국어 모델 선택 필요

---

## YOLO 연동 흐름

```
카메라 (상시)
  → YOLOv8 사람 감지
    ├── 사람 있음 + 로봇 대기 중
    │   → 10~20s 주기로 "처음 방문이시면 헤이 리모라고 불러주세요" TTS
    └── 호출어 감지 시
        → 사람 방향(각도) 계산 → /cmd_vel로 로봇 회전
        → "어떤 도움을 드릴까요?" TTS
        → STT 활성화
```

---

## 리소스 사용 요약

| 레벨 | 상시/조건부 | CPU | GPU |
|------|------------|-----|-----|
| VAD | 상시 | 경량 | — |
| Wake-up | VAD 통과 시 | 경량 | — |
| STT | 호출어 감지 시 | 중 | CUDA |
| NLU Main | STT 완료 시 | 저 | — |
| NLU Backup | 네트워크 단절 시 | 고 | 혼용 |
| TTS | 응답 필요 시 | 중 | — |
| YOLO | 상시 | 중 | CUDA |

**주의**: STT + YOLO 동시 CUDA 사용 → Orin Nano GPU 메모리 제약 검토 필수 (→ DEC-002)
