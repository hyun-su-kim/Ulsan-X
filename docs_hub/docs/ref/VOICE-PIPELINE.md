# VOICE-PIPELINE — 음성 처리 파이프라인

## 현재 설계 (v2, 2026-05-12 — DEC-023/024 반영)

목적지 결정을 음성 NLU가 아닌 **예약 DB 조회**로 확정. TTS는 체크인 완료 후 안내 멘트 출력에만 사용.

### 흐름

```
방문자가 LIMO 터치 화면에서 체크인
  │  이름 + 전화번호 끝자리 입력
  ▼
예약 DB 조회
  │  오늘 날짜 + 현재 시간대 예약 확인 → 배정 상담실 반환
  ▼
TTS 안내 멘트
  │  "{이름}님 {시간}시 상담 예약으로 {상담실}로 안내합니다."
  │  구현: edge-tts (Microsoft Neural TTS, ko-KR-SunHiNeural)
  │  인터넷 연결 필요 — 클라우드 음성 합성
  ▼
/goal_destination 발행 → wego_behaviour FSM → Nav2 navigate_to_pose
```

### TTS 선택 근거 (edge-tts)
- 별도 모델 설치 없이 `pip install edge-tts` 한 줄로 즉시 사용 가능
- Microsoft Neural TTS — 한국어 자연스러운 발음 품질
- 학원 안내 로봇 특성상 안내 멘트가 짧고 정형화돼 있어 응답 지연(~1s) 허용 가능
- 오프라인 대안(Piper)은 추후 개발 사항으로 보류

---

## 추후 개발 사항 (v3 이후)

음성으로 방문자와 자유 대화하며 목적지를 결정하는 기능. 현재 v2에는 포함되지 않음.

### 목표 흐름

```
마이크 (상시)
  │
  ▼ VAD ──────── 사람 목소리 아니면 차단
  │ webrtcvad / Silero VAD
  │
  ▼ Wake-up ─── "헤이 리모" 감지
  │ openWakeWord (커스텀 모델 필요 여부 미결 → DEC-001)
  │
  ▼ STT ──────── 발화 텍스트 변환
  │ faster-whisper (small, CUDA)
  │
  ▼ LLM API ─── 자유 발화 의도 해석 → 목적지 결정
  │ Gemini API (Main) / Gemma-2B 로컬 (Backup)
  │
  ▼ TTS ──────── 응답 출력
    Piper ONNX (로컬, 오프라인) 또는 edge-tts
```

### 보류 이유
- 현재 시스템은 예약자 대상 안내 → 목적지가 DB에서 확정되므로 STT/NLU 불필요
- 음성 인식 오류(오매핑, 발화 실패) 없이 안내 정확도 100% 보장 가능
- STT + GPU 리소스 경합(YOLO 동시 가동 시 OOM 위험 → DEC-002) 회피
- 워크인 방문자(예약 없이 방문) 처리 방식이 미결정인 시점에서 구현하면 설계가 바뀔 수 있음

### 관련 미결 사항
- DEC-001: "헤이 리모" openWakeWord 커스텀 모델 학습 필요 여부
- DEC-002: Orin Nano GPU — YOLO + faster-whisper 동시 가동 OOM 위험
- 워크인 방문자 처리 방식 (DEC-023 미결 사항)
- TTS 오프라인 대안: Piper ONNX 한국어 모델 선택
