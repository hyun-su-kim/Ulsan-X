# VOICE-PIPELINE — 음성 처리 파이프라인

## 현재 설계 (v2, 2026-05-12 — DEC-023/024 반영)

목적지 결정을 음성 NLU가 아닌 **예약 DB 조회**로 확정. TTS는 체크인 완료 후 안내 멘트 출력에만 사용.

### 흐름

```
방문자가 태블릿 웹 UI(ulsan-visitor-ui)에서 체크인
  │  이름 + 전화번호 끝자리 입력 (HTTP only, rosbridge 없음)
  ▼
FastAPI(ulsan_reservation) 예약 DB 조회
  │  오늘 날짜 + 현재 시간대 예약 확인 → 배정 상담실 + 안내 멘트 확정 → mission PENDING
  ▼
wego_dispatcher (domain 5, 0.5s 폴링) → IDLE 로봇에 발행
  ├─ /speak_text       → wego_voice voice_node
  │     │  "{이름}님 {시간}시 상담 예약으로 {상담실}로 안내합니다."
  │     │  구현: edge-tts (Microsoft Neural TTS, ko-KR-SunHiNeural), 클라우드 합성
  │     │  출력 장치: mpg123 -a plughw:1,3 (로봇 HDMI 오디오, Jetson Orin)
  │     ▼  TTS 음성 출력
  └─ /goal_destination → wego_behaviour FSM → Nav2 navigate_to_pose / navigate_through_poses
```

> 음성 발행 경로: 목적지 결정은 예약 DB, TTS 트리거는 `/speak_text`(dispatcher→voice). voice_node는 DB를 직접 조회하지 않고 받은 문구를 합성만 한다 (DEC-024/027).

### TTS 선택 근거 (edge-tts)
- 별도 모델 설치 없이 `pip install edge-tts` 한 줄로 즉시 사용 가능
- Microsoft Neural TTS — 한국어 자연스러운 발음 품질
- 학원 안내 로봇 특성상 안내 멘트가 짧고 정형화돼 있어 응답 지연(~1s) 허용 가능
- 오프라인 대안(Piper)은 추후 개발 사항으로 보류

### 오디오 출력 장치 설정
- Jetson Orin NX 기본 ALSA 장치는 HDMI가 아님 → mpg123에 `-a` 장치 명시 필수
- 로봇 오디오 출력이 HDMI 경로(card 1, device 3)라 `plughw:1,3` 사용
- `voice_params.yaml`의 `audio_device` 파라미터로 변경 가능

---

## 폐기된 음성 인식 파이프라인 (VAD/Wakeword/STT/NLU) — DEC-024

초기 설계는 마이크 자유 발화로 목적지를 결정하는 STT/NLU 파이프라인이었으나 **전량 폐기**됨.

```
(폐기) 마이크 → VAD(Silero) → Wakeword("헤이 리모", openWakeWord)
              → STT(faster-whisper) → NLU(Gemini/Gemma-2B) → 목적지
```

**폐기 이유 (DEC-023/024)**:
- 예약 시스템 도입으로 목적지가 **예약 DB에서 확정** → STT/NLU 불필요
- 음성 인식 오류(오매핑/발화 실패) 제거 → 안내 정확도 100% 보장
- STT GPU 리소스 경합(YOLO 동시 가동 OOM 위험) 회피
- 따라서 `wego_voice`는 **TTS 발화 전용**(위 v2)으로 단순화. VAD/wakeword/STT/NLU 노드는 구현되지 않음.

> 관련 초기 검토(DEC-001 wakeword 모델, DEC-002 GPU OOM)는 DECISION-LOG에 히스토리로만 남김 — 현재 무효.
