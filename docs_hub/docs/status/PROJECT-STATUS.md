# AI 기반 학원 안내 로봇 — Project Status

## Current Phase
**Phase 2 완료 → Phase 3 진입 (행동 트리 + 음성 파이프라인)**
Fleet 통신·위치 공유·관제 UI 실기기 검증 완료 (2026-04-29). 유리 구간 간헐적 버벅임은 알려진 한계로 수용, 개발 완료 후 재검토.

---

## Active Tracks

| 트랙 | 상태 | 담당 패키지 |
|------|------|------------|
| 시스템 아키텍처 설계 | **완료** | — |
| 통신 환경 구성 (CycloneDDS + Domain Bridge) | **완료** | wego_bridge |
| 관제 UI (domain 5 위치 시각화) | **완료** | wego_ui |
| SLAM 지도 작성 | **완료** | wego (cartographer) |
| Nav2 경로 계획 & AMCL | **완료** | wego_2d_nav |
| Fleet 충돌 회피 (PeerObstacleLayer) | **완료** | ulsan_obstacle_layer |
| 행동 트리 최상단 관리 | planned | wego_behaviour (신규) |
| 음성 파이프라인 (VAD→Wake→STT→NLU→TTS) | planned | wego_voice (신규) |

---

## Execution Checklist

### 완료 — 환경 기반 구축
- [x] CycloneDDS 설치 및 `cyclonedds_peers.xml` 유니캐스트 설정 — done (2026-04-16), TS-001 참고
- [x] DOMAIN_ID 확정 — done (2026-04-16): 노트북=5, LIMO 1=6, LIMO 2=7
- [x] cyclonedds_peers.xml 실제 IP 입력 — done (2026-04-22): LIMO1=192.168.0.101, LIMO2=192.168.0.102, 노트북1=192.168.0.115, 노트북2=192.168.0.116
- [x] 멀티로봇 통신 설계 확정 — done (2026-04-21): DEC-011, DEC-012
- [x] `wego_bridge` 패키지 구현 + 실기기 통신 검증 — done (2026-04-22)
- [x] Cartographer SLAM 지도 작성 완료 — done (2026-04-28~29)
  - 유리 구간: 종이 부착으로 LiDAR 특징점 확보 (매핑 후 제거)
  - 복도 drift: 임시 장애물 배치 + 루프 주행(왕복) + `/constraint_list` loop closure 확인
  - 후처리: GIMP 노이즈 제거 + 유리문 구간 가상 벽 처리
- [x] 맵 파일 git 커밋 — 각 기기 `git pull`로 배포

---

### Phase 1 — 단일 LIMO 자율주행 완성 (현재 진행 중)

> LIMO 1대가 학원을 완벽하게 자율주행하는 것이 목표

- [x] `ulsan_obstacle_layer` 빌드 — LIMO ulsan_ws 전체 빌드 완료. `peer_valid_` 플래그로 상대 amcl_pose 수신 전까지 완전 no-op — 단독 주행에 영향 없음.
- [x] Nav2 전체 스택 실기기 테스트 — 목적지·홈 구간 정상 주행 확인 (2026-04-29)
- [x] AMCL 파라미터 튜닝 — `do_beamskip: true` 단일 수정. 파티클 수렴 정상 확인 (2026-04-29)
- [x] **유리 구간 유령 장애물** — Keepout Filter + DenoiseLayer 적용 완료 (2026-04-29)
  - 목적지·홈 구간 주행에 문제 없음 → 운용상 수용
  - 유리 회전문 통과는 LiDAR 물리 한계로 소프트웨어 완전 해결 불가 → **운용 정책: 유리 회전문 구간은 경로에서 제외**
- [ ] **ArUco 마커 기반 목적지 정차 보정** — 장시간 운영 시 누적 오차 리셋 (DEC-016)
  - 강의실, 상담실 등 각 목적지 벽에 마커 부착 (10cm × 10cm, DICT_4X4_50)
  - 도착 시 마커 감지 → `/initialpose` 보정 → 정확한 정차 위치 보장
  - 구현 계획: `docs/ref/ARUCO-LOCALIZER.md` 참고
- [ ] `waypoints.yaml` 작성 — 강의실, 상담실, 회의실 등 목적지 좌표 (Nav2로 실제 주행하며 기록)

---

### Phase 2 — 2대 Fleet 구성

> LIMO 2대가 서로를 인식하고 회피하며 독립적으로 주행

- [x] `ulsan_obstacle_layer` 실기기 검증 — 각 로봇 global costmap에 상대 amcl_pose LETHAL 원형 반영 확인 (2026-04-29)
- [x] `wego_bridge` 실운용 — 두 로봇 amcl_pose 노트북(domain 5) 수신 확인 (2026-04-29)
- [x] `wego_ui` 관제 GUI — 노트북 domain 5에서 지도 + 두 로봇 실시간 위치 마커 정상 시각화 (2026-04-29)

---

### Phase 3 — 핵심 기능 구현

#### 미션 제어
- [ ] `wego_behaviour` 패키지: **Yasmin FSM** 구현 (대기 / 안내 중 / 복귀 중) — DEC-014
- [ ] Nav2 BT 커스텀 노드: `VoiceTriggerCondition`, `PeerRobotBusyCondition` (C++)
- [ ] 중앙 코디네이터 (노트북): robot_status 구독 → on_duty 결정 — DEC-015
- [ ] Nav2 `navigate_to_pose` 액션 연동

#### 음성 파이프라인
- [ ] `wego_voice` 패키지: VAD + openWakeWord + faster-whisper (STT)
- [ ] NLU: 발화 키워드 → `waypoints.yaml` 목적지 매핑
- [ ] TTS (Piper)
- [ ] 음성 파이프라인 → FSM 연결

---

### Phase 4 — 완성도
- [ ] 초음파 센서 → local costmap range_sensor_layer 연동 (유리문 닫힘 감지 + 음성 대기) — 유리문 닫힘 시 경로 생성 불가 → TTS "유리문을 열어주세요" + WAIT 상태
- [ ] YOLO 사람 감지 → 방향 회전 + 안내 멘트
- [ ] NLU 백업: Gemma-2B (Ollama) 로컬 폴백
- [ ] 목적지 도달 후 "추가 용무 확인" 대화 흐름
- [ ] GPU 메모리 프로파일링 (YOLO + faster-whisper 동시 가동)
- [ ] 다국어 안내 검토
- [ ] **유리 구간 주행 버벅임 개선** — Keepout+DenoiseLayer 적용 후에도 간헐적 버벅임 잔존. 추가 해결책 탐색 (local costmap phantom 근본 억제 또는 경로 설계 개선)
- [ ] **2대 충돌 회피 완성도 개선** — 운용 중 간헐적 충돌 발생. 유추 원인: ① 네트워크 지연으로 상대 위치 업데이트 늦음 ② 양 로봇이 대칭으로 같은 방향 회피 → 교착. 정확한 원인 실기기 진단 후 해결

---

## Nav2 단독 주행 현황 (2026-04-29 기준)

### 정상 동작
- 복도·강의실 등 일반 구간 자율주행 정상
- AMCL 위치추정 정상 (RViz `/particlecloud` 파티클 수렴 확인)
- **목적지·홈 위치 주행 정상 — 운용 목적 달성**
- Keepout Filter (금지구역) + DenoiseLayer 적용 완료

### 확정된 한계 및 운용 정책

| 항목 | 내용 |
|------|------|
| 유리 회전문 통과 | LiDAR 물리 한계. 소프트웨어 완전 해결 불가. **경로에서 영구 제외** |
| Keepout Filter 적용 범위 | global costmap만 적용. local costmap phantom은 소거 불가. |
| 운용 전제 | 유리문은 항상 열린 상태 유지. 안내 주행 목적에 유리 회전문 통과 불필요. |

### 미해결 과제

| 문제 | 상태 |
|------|------|
| `waypoints.yaml` 미작성 | Phase 2 직후 진행 |
| AMCL 파라미터 미최적화 | 장시간 운영 시 drift 가능성 — 진행 중 |

> 상세 엔지니어링 판단 기록: `docs/ref/NAVIGATION.md` — "Nav2 주행 문제 해결 과정" 섹션

---

## 알려진 이슈 / 리스크

| 이슈 | 심각도 | 상태 |
|------|--------|------|
| Orin Nano GPU 메모리: YOLO + faster-whisper 동시 가동 시 OOM 가능성 | High | P2에서 프로파일링 예정 |
| openWakeWord "헤이 리모" 커스텀 모델 학습 필요 여부 | Medium | 미결정 |
| 두 로봇이 동시에 호출될 때 충돌 시나리오 | Medium | BT 설계 시 처리 예정 |
| Gemini API 응답 지연이 대화 흐름에 미치는 영향 | Low | 모니터링 |
